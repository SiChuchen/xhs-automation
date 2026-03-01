#!/usr/bin/env python3
"""测试发布时间抖动功能"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import datetime
import random
import time

def test_jitter_calculation():
    """测试抖动时间计算逻辑"""
    print("🧪 测试发布时间抖动计算...")
    
    # 模拟当前时间
    now = datetime.datetime.now(datetime.timezone.utc).astimezone()
    print(f"当前时间: {now}")
    
    # 模拟最佳时间中心点（比如09:00）
    best_center = now.replace(hour=9, minute=0, second=0, microsecond=0)
    print(f"最佳时间中心点: {best_center}")
    
    # 计算窗口结束时间
    window_end = best_center + datetime.timedelta(minutes=30)
    print(f"窗口结束时间: {window_end}")
    
    # 模拟不同场景
    test_cases = [
        ("当前时间在中心点之前", best_center - datetime.timedelta(minutes=20)),
        ("当前时间在中心点之后", best_center + datetime.timedelta(minutes=10)),
        ("当前时间接近窗口结束", window_end - datetime.timedelta(minutes=5)),
        ("当前时间超出窗口", window_end + datetime.timedelta(minutes=5)),
    ]
    
    for desc, current_time in test_cases:
        print(f"\n{desc}: {current_time}")
        remaining_seconds = (window_end - current_time).total_seconds()
        print(f"  剩余窗口秒数: {remaining_seconds:.0f}")
        
        if remaining_seconds > 0:
            max_jitter = min(1800, remaining_seconds)
            print(f"  最大抖动秒数: {max_jitter:.0f}")
            if max_jitter > 0:
                # 模拟多次随机选择
                jitters = [random.randint(0, int(max_jitter)) for _ in range(5)]
                print(f"  随机抖动示例: {jitters}")
            else:
                print("  无法添加抖动（剩余窗口时间不足）")
        else:
            print("  已超出窗口，不应用抖动")
    
    print("\n✅ 抖动计算逻辑测试完成")

def test_integration():
    """测试与AutomationManager集成"""
    print("\n🔗 测试与AutomationManager集成...")
    
    try:
        from scripts.xhs_automation_monitored import AutomationManager
        
        # 创建管理器实例
        manager = AutomationManager()
        
        # 模拟设置最佳时间中心点
        now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        manager.best_time_center = now.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # 计算抖动
        window_end = manager.best_time_center + datetime.timedelta(minutes=30)
        remaining_seconds = (window_end - now).total_seconds()
        
        print(f"最佳时间中心点: {manager.best_time_center}")
        print(f"窗口结束时间: {window_end}")
        print(f"当前时间: {now}")
        print(f"剩余窗口秒数: {remaining_seconds:.0f}")
        
        if remaining_seconds > 0:
            max_jitter = min(1800, remaining_seconds)
            print(f"最大抖动秒数: {max_jitter:.0f}")
            if max_jitter > 0:
                jitter = random.randint(0, int(max_jitter))
                print(f"本次随机抖动: {jitter}秒 ({jitter/60:.1f}分钟)")
            else:
                print("剩余窗口时间不足，跳过抖动")
        else:
            print("已超出窗口，不应用抖动")
        
        print("\n✅ 集成测试完成")
        
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("📅 发布时间抖动功能测试")
    print("=" * 50)
    
    # 设置随机种子以便重现
    random.seed(42)
    
    test_jitter_calculation()
    test_integration()
    
    print("\n🎯 功能要点总结:")
    print("1. 抖动范围: 0-1800秒 (0-30分钟)")
    print("2. 应用条件: 仅在最佳时间窗口内发布时应用")
    print("3. 限制: 不会超出剩余窗口时间")
    print("4. 随机性: 每次发布随机选择延迟时间")
    print("5. 效果: 消除机器定时痕迹，模拟人类行为")