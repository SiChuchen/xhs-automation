"""
内容哈希状态机 - 防重发机制
基于内容 MD5 哈希确保一篇内容只提交给 MCP 一次
"""

import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ContentState(Enum):
    """内容状态"""
    PENDING = "pending"           # 待处理
    PROCESSING = "processing"     # 正在发送给 MCP
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消


class ContentHashStateMachine:
    """内容哈希状态机 - 确保内容只发布一次"""
    
    def __init__(self, db_path: str = "data/xhs_automation.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS content_hash_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT UNIQUE NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending',
                    title TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    mcp_response TEXT,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_content_hash 
                ON content_hash_state(content_hash)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_state 
                ON content_hash_state(state)
            """)
            conn.commit()
    
    @contextmanager
    def _get_conn(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def compute_content_hash(self, content: str, title: str = "", image_paths: Optional[List[str]] = None) -> str:
        """
        计算内容哈希
        
        Args:
            content: 正文内容
            title: 标题
            image_paths: 图片路径列表
        
        Returns:
            MD5 哈希值
        """
        hash_components = [
            content,
            title,
            "|".join(sorted(image_paths or []))
        ]
        hash_str = "||".join(hash_components)
        return hashlib.md5(hash_str.encode('utf-8')).hexdigest()
    
    def can_publish(self, content_hash: str) -> tuple[bool, str, Optional[Dict]]:
        """
        检查是否可以发布
        
        Returns:
            (can_publish, reason, existing_record)
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM content_hash_state WHERE content_hash = ?",
                (content_hash,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return True, "new_content", None
            
            state = row['state']
            
            if state == ContentState.COMPLETED.value:
                return False, f"already_published", dict(row)
            
            if state == ContentState.PROCESSING.value:
                age = time.time() - row['updated_at']
                if age > 600:  # 超过10分钟，认为可能卡住
                    return True, "stale_processing", dict(row)
                return False, f"processing_{int(age)}s", dict(row)
            
            if state == ContentState.FAILED.value:
                if row['retry_count'] < 3:
                    return True, "retry_allowed", dict(row)
                return False, "max_retries_exceeded", dict(row)
            
            return True, f"state_{state}", dict(row)
    
    def mark_pending(self, content_hash: str, title: str = "", metadata: Optional[Dict[str, Any]] = None) -> bool:
        """标记为待处理"""
        now = time.time()
        
        with self._get_conn() as conn:
            try:
                conn.execute("""
                    INSERT INTO content_hash_state 
                    (content_hash, state, title, created_at, updated_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    content_hash,
                    ContentState.PENDING.value,
                    title[:100] if title else "",
                    now,
                    now,
                    json.dumps(metadata or {}, ensure_ascii=False)
                ))
                conn.commit()
                logger.info(f"内容哈希标记为 pending: {content_hash[:16]}...")
                return True
            except sqlite3.IntegrityError:
                logger.warning(f"内容哈希已存在: {content_hash[:16]}...")
                return False
    
    def mark_processing(self, content_hash: str) -> bool:
        """标记为处理中"""
        now = time.time()
        
        with self._get_conn() as conn:
            affected = conn.execute("""
                UPDATE content_hash_state 
                SET state = ?, updated_at = ?
                WHERE content_hash = ? AND state IN (?, ?, ?)
            """, (
                ContentState.PROCESSING.value,
                now,
                content_hash,
                ContentState.PENDING.value,
                ContentState.FAILED.value,
                ContentState.PENDING.value  # 重复检查
            ))
            conn.commit()
            
            if affected.rowcount > 0:
                logger.info(f"内容哈希标记为 processing: {content_hash[:16]}...")
                return True
            return False
    
    def mark_completed(self, content_hash: str, mcp_response: str = "") -> bool:
        """标记为已完成"""
        now = time.time()
        
        with self._get_conn() as conn:
            affected = conn.execute("""
                UPDATE content_hash_state 
                SET state = ?, updated_at = ?, mcp_response = ?
                WHERE content_hash = ?
            """, (
                ContentState.COMPLETED.value,
                now,
                mcp_response[:5000] if mcp_response else "",
                content_hash
            ))
            conn.commit()
            
            if affected.rowcount > 0:
                logger.info(f"内容哈希标记为 completed: {content_hash[:16]}...")
                return True
            return False
    
    def mark_failed(self, content_hash: str, error_message: str) -> bool:
        """标记为失败"""
        now = time.time()
        
        with self._get_conn() as conn:
            affected = conn.execute("""
                UPDATE content_hash_state 
                SET state = ?, updated_at = ?, error_message = ?, 
                    retry_count = retry_count + 1
                WHERE content_hash = ?
            """, (
                ContentState.FAILED.value,
                now,
                error_message[:500],
                content_hash
            ))
            conn.commit()
            
            if affected.rowcount > 0:
                logger.warning(f"内容哈希标记为 failed: {content_hash[:16]}... error: {error_message[:50]}")
                return True
            return False
    
    def get_status(self, content_hash: str) -> Optional[Dict]:
        """获取内容状态"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM content_hash_state WHERE content_hash = ?",
                (content_hash,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def cleanup_old_records(self, days: int = 30) -> int:
        """清理旧记录"""
        cutoff = time.time() - (days * 86400)
        
        with self._get_conn() as conn:
            cursor = conn.execute("""
                DELETE FROM content_hash_state 
                WHERE state IN (?, ?) AND updated_at < ?
            """, (
                ContentState.COMPLETED.value,
                ContentState.CANCELLED.value,
                cutoff
            ))
            conn.commit()
            
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"清理了 {deleted} 条旧记录")
            
            return deleted
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT state, COUNT(*) as count 
                FROM content_hash_state 
                GROUP BY state
            """)
            
            stats = {row['state']: row['count'] for row in cursor.fetchall()}
            
            cursor = conn.execute("SELECT COUNT(*) as total FROM content_hash_state")
            stats['total'] = cursor.fetchone()['total']
            
            return stats


class ContentDeduplicator:
    """内容去重器 - 整合哈希状态机和布隆过滤器"""
    
    def __init__(self, db_path: str = "data/xhs_automation.db", cache_dir: str = "data/cache"):
        self.state_machine = ContentHashStateMachine(db_path)
        
        try:
            from src.cache.bloom_filter import BloomFilter
            bloom_path = f"{cache_dir}/content_bloom.bin"
            self.bloom = BloomFilter(capacity=100000, error_rate=0.001, filepath=bloom_path)
            self.use_bloom = True
        except Exception as e:
            logger.warning(f"布隆过滤器初始化失败: {e}")
            self.use_bloom = False
    
    def check_and_mark(self, content: str, title: str = "", 
                       image_paths: Optional[List[str]] = None) -> tuple[bool, str, Optional[Dict]]:
        """
        检查内容是否可发布并标记
        
        Returns:
            (can_publish, reason, existing_record)
        """
        content_hash = self.state_machine.compute_content_hash(content, title, image_paths)
        
        if self.use_bloom:
            if content_hash in self.bloom:
                can_publish, reason, record = self.state_machine.can_publish(content_hash)
                if not can_publish:
                    return False, reason, record
        
        can_publish, reason, record = self.state_machine.can_publish(content_hash)
        
        if can_publish:
            self.state_machine.mark_pending(content_hash, title)
            if self.use_bloom:
                self.bloom.add(content_hash)
        
        return can_publish, reason, record
    
    def mark_completed(self, content: str, title: str = "", 
                       image_paths: Optional[List[str]] = None, mcp_response: str = "") -> bool:
        """标记为已完成"""
        content_hash = self.state_machine.compute_content_hash(content, title, image_paths)
        return self.state_machine.mark_completed(content_hash, mcp_response)
    
    def mark_failed(self, content: str, title: str = "", 
                    image_paths: Optional[List[str]] = None, error: str = "") -> bool:
        """标记为失败"""
        content_hash = self.state_machine.compute_content_hash(content, title, image_paths)
        return self.state_machine.mark_failed(content_hash, error)
    
    def mark_processing(self, content: str, title: str = "", 
                        image_paths: Optional[List[str]] = None) -> bool:
        """标记为处理中"""
        content_hash = self.state_machine.compute_content_hash(content, title, image_paths)
        return self.state_machine.mark_processing(content_hash)


_global_deduplicator = None


def get_content_deduplicator() -> ContentDeduplicator:
    """获取全局内容去重器"""
    global _global_deduplicator
    if _global_deduplicator is None:
        _global_deduplicator = ContentDeduplicator()
    return _global_deduplicator
