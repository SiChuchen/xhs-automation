#!/usr/bin/env python3
"""
Phase 1 验收测试
测试乐观锁状态机 + 图片处理功能
"""

import os
import sys
import time
import sqlite3
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.task_state_machine import (
    OptimisticLockStateMachine, 
    PostStateMachine, 
    InteractionStateMachine,
    TaskStatus
)
from src.utils.image_processor import (
    verify_image,
    crop_to_34_ratio,
    adaptive_compress,
    process_and_verify_image
)


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def add(self, name: str, passed: bool, message: str = ""):
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append(f"{status}: {name} {message}")
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def print_summary(self):
        print("\n" + "="*60)
        print("Phase 1 验收测试结果")
        print("="*60)
        for r in self.results:
            print(r)
        print("-"*60)
        print(f"总计: {self.passed} 通过, {self.failed} 失败")
        print("="*60)
        return self.failed == 0


def setup_test_db(db_path: str = ":memory:"):
    """创建测试数据库"""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            status TEXT DEFAULT 'pending',
            locked_at TEXT,
            updated_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_post_id TEXT,
            action TEXT,
            status TEXT DEFAULT 'pending',
            locked_at TEXT,
            updated_at REAL
        )
    """)
    conn.commit()
    return conn


def test_optimistic_lock_concurrent() -> TestResult:
    """测试1: 乐观锁并发抢占"""
    result = TestResult()
    
    # 使用临时文件数据库
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        conn = setup_test_db(db_path)
        
        # 插入测试数据
        conn.execute("INSERT INTO posts (title, status) VALUES ('test post', 'pending')")
        conn.commit()
        post_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        sm = PostStateMachine(db_path)
        
        # Worker1 抢占
        claim1 = sm.claim_post(post_id)
        result.add("Worker1 首次抢占成功", claim1.success, f"(reason={claim1.reason})")
        
        # Worker2 尝试抢占 (应该失败)
        claim2 = sm.claim_post(post_id)
        result.add("Worker2 并发抢占失败", not claim2.success, f"(reason={claim2.reason})")
        
        # Worker1 完成
        sm.complete_post(post_id)
        
        # Worker3 再次尝试 (应该成功，因为已完成)
        conn.execute("UPDATE posts SET status = 'pending' WHERE id = ?", (post_id,))
        conn.commit()
        claim3 = sm.claim_post(post_id)
        result.add("完成后可重新抢占", claim3.success, f"(reason={claim3.reason})")
        
        conn.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    return result


def test_ttl_timeout() -> TestResult:
    """测试2: TTL 超时释放"""
    result = TestResult()
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        conn = setup_test_db(db_path)
        
        # 插入测试数据 - 模拟20分钟前锁定的任务 (使用Unix timestamp)
        old_timestamp = time.time() - (20 * 60)  # 20分钟前
        conn.execute("INSERT INTO posts (title, status, locked_at) VALUES ('test post', 'processing', ?)", 
                     (old_timestamp,))
        conn.commit()
        post_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        sm = PostStateMachine(db_path)
        
        # 尝试抢占超时任务 (应该成功)
        claim = sm.claim_post(post_id, timeout_minutes=15)
        result.add("超时任务可重新抢占", claim.success, f"(reason={claim.reason})")
        
        # 尝试抢占未超时任务 (应该失败)
        conn.execute("UPDATE posts SET locked_at = ? WHERE id = ?", 
                     (time.time(), post_id))
        conn.commit()
        
        claim2 = sm.claim_post(post_id, timeout_minutes=15)
        result.add("未超时任务不可抢占", not claim2.success, f"(reason={claim2.reason})")
        
        conn.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    return result


def test_image_verify() -> TestResult:
    """测试3: 图片校验功能"""
    result = TestResult()
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        valid_path = os.path.join(tmpdir, "valid.jpg")
        invalid_path = os.path.join(tmpdir, "invalid.jpg")
        
        # 创建有效图片
        img = Image.new('RGB', (100, 100), color='red')
        img.save(valid_path, 'JPEG')
        
        is_valid, msg = verify_image(valid_path)
        result.add("有效图片校验通过", is_valid, f"({msg})")
        
        # 创建无效/损坏图片
        with open(invalid_path, 'wb') as f:
            f.write(b'not an image')
        
        is_valid2, msg2 = verify_image(invalid_path)
        result.add("损坏图片检测失败", not is_valid2, f"({msg2})")
    
    return result


def test_image_crop_compress() -> TestResult:
    """测试4: 图片裁剪 + 压缩"""
    result = TestResult()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建非 3:4 比例图片
        input_path = os.path.join(tmpdir, "input.jpg")
        output_path = os.path.join(tmpdir, "output.jpg")
        
        img = Image.new('RGB', (800, 600), color='blue')  # 4:3 比例
        img.save(input_path, 'JPEG')
        
        # 测试裁剪
        img = Image.open(input_path)
        cropped = crop_to_34_ratio(img)
        
        width, height = cropped.size
        ratio = width / height
        result.add("3:4 裁剪比例正确", abs(ratio - 0.75) < 0.01, 
                   f"(实际比例={ratio:.2f})")
        
        # 测试综合处理
        success, msg = process_and_verify_image(
            input_path, 
            output_path,
            target_size=(1080, 1440),
            max_size_kb=500
        )
        
        result.add("综合处理成功", success, f"({msg})")
        
        if success:
            output_size = os.path.getsize(output_path) / 1024
            result.add("输出文件小于限制", output_size < 500, f"({output_size:.1f}KB)")
            
            output_img = Image.open(output_path)
            result.add("输出尺寸正确", output_img.size == (1080, 1440), 
                       f"({output_img.size})")
    
    return result


def test_interaction_state_machine() -> TestResult:
    """测试5: 互动状态机"""
    result = TestResult()
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        conn = setup_test_db(db_path)
        
        # 插入测试数据
        conn.execute("INSERT INTO interactions (target_post_id, action, status) VALUES ('post123', 'like', 'pending')")
        conn.commit()
        interaction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        sm = InteractionStateMachine(db_path)
        
        # 第一次抢占
        claim1 = sm.claim_interaction(interaction_id)
        result.add("互动任务抢占成功", claim1.success)
        
        # 第二次抢占 (应该失败)
        claim2 = sm.claim_interaction(interaction_id)
        result.add("重复互动抢占失败", not claim2.success)
        
        conn.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    return result


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Phase 1 验收测试开始")
    print("="*60 + "\n")
    
    all_results = TestResult()
    
    # 测试1: 乐观锁并发
    print("[1/5] 测试乐观锁并发抢占...")
    r1 = test_optimistic_lock_concurrent()
    all_results.results.extend(r1.results)
    all_results.passed += r1.passed
    all_results.failed += r1.failed
    
    # 测试2: TTL 超时
    print("[2/5] 测试 TTL 超时释放...")
    r2 = test_ttl_timeout()
    all_results.results.extend(r2.results)
    all_results.passed += r2.passed
    all_results.failed += r2.failed
    
    # 测试3: 图片校验
    print("[3/5] 测试图片校验...")
    r3 = test_image_verify()
    all_results.results.extend(r3.results)
    all_results.passed += r3.passed
    all_results.failed += r3.failed
    
    # 测试4: 图片裁剪压缩
    print("[4/5] 测试图片裁剪+压缩...")
    r4 = test_image_crop_compress()
    all_results.results.extend(r4.results)
    all_results.passed += r4.passed
    all_results.failed += r4.failed
    
    # 测试5: 互动状态机
    print("[5/5] 测试互动状态机...")
    r5 = test_interaction_state_machine()
    all_results.results.extend(r5.results)
    all_results.passed += r5.passed
    all_results.failed += r5.failed
    
    # 输出结果
    success = all_results.print_summary()
    
    if success:
        print("\n🎉 Phase 1 验收通过!")
        return 0
    else:
        print("\n❌ Phase 1 验收失败，请检查失败的测试项")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
