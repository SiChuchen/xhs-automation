#!/usr/bin/env python3
"""测试监控模块"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.monitoring import MonitoringSystem

def test_monitoring():
    """测试监控系统"""
    print("🧪 测试监控系统...")
    
    # 初始化监控系统
    monitor = MonitoringSystem()
    
    print("1. 测试Cookie状态检查...")
    cookie_status = monitor.check_cookie_status()
    print(f"   Cookie状态: {cookie_status}")
    
    print("\n2. 测试系统状态检查...")
    system_status = monitor.check_system_status()
    print(f"   服务状态: {system_status['checks'].get('service_status', {}).get('active', False)}")
    print(f"   Docker状态: {system_status['checks'].get('docker_container', {}).get('running', False)}")
    
    print("\n3. 测试存储管理...")
    storage_result = monitor.manage_storage()
    print(f"   清理结果: {storage_result}")
    
    print("\n4. 测试Webhook发送（测试消息）...")
    # 测试发送消息（Webhook可能未配置）
    success = monitor.send_alert(
        "监控系统测试",
        "这是一条测试消息，验证监控系统是否正常工作。",
        "info"
    )
    print(f"   Webhook发送: {'成功' if success else '失败（可能未配置）'}")
    
    print("\n5. 运行全面检查...")
    full_result = monitor.run_comprehensive_check()
    print(f"   全面检查完成")
    
    print("\n✅ 监控系统测试完成")
    return True

if __name__ == "__main__":
    try:
        test_monitoring()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)