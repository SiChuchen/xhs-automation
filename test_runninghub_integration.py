#!/usr/bin/env python3
"""
测试RunningHub集成功能
"""

import os
import sys
import json
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_imports():
    """测试导入功能"""
    print("🧪 测试导入功能...")
    
    try:
        from scripts.runninghub_client import RunningHubClient
        print("✅ RunningHubClient 导入成功")
    except ImportError as e:
        print(f"❌ RunningHubClient 导入失败: {e}")
        return False
    
    try:
        from scripts.enhanced_image_manager import EnhancedImageManager
        print("✅ EnhancedImageManager 导入成功")
    except ImportError as e:
        print(f"❌ EnhancedImageManager 导入失败: {e}")
        return False
    
    try:
        # 测试修改后的主脚本导入
        from scripts.xhs_automation_monitored import CharacterPersona
        print("✅ CharacterPersona 导入成功")
    except ImportError as e:
        print(f"❌ CharacterPersona 导入失败: {e}")
        return False
    
    return True

def test_configs():
    """测试配置文件"""
    print("\n📋 测试配置文件...")
    
    config_files = [
        "/home/ubuntu/xhs-automation/config/publish_config.json",
        "/home/ubuntu/xhs-automation/config/runninghub_config.json"
    ]
    
    for config_file in config_files:
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"✅ {os.path.basename(config_file)} 加载成功")
                if "enabled" in config:
                    print(f"   启用状态: {config['enabled']}")
            except Exception as e:
                print(f"❌ {os.path.basename(config_file)} 加载失败: {e}")
        else:
            print(f"⚠️  {os.path.basename(config_file)} 不存在")
    
    return True

def test_character_persona():
    """测试CharacterPersona初始化"""
    print("\n👤 测试CharacterPersona初始化...")
    
    try:
        from scripts.xhs_automation_monitored import CharacterPersona
        
        config_path = "/home/ubuntu/xhs-automation/config/publish_config.json"
        soul_path = "/home/ubuntu/xhs-automation/config/soul.md"
        
        if not os.path.exists(soul_path):
            # 创建一个临时的soul文件
            with open(soul_path, 'w', encoding='utf-8') as f:
                f.write("# 林晓芯的灵魂\n\n理工科女大、效率控、技术宅、微社恐、逻辑严密")
        
        persona = CharacterPersona(config_path, soul_path)
        print(f"✅ CharacterPersona 初始化成功")
        print(f"   人物: {persona.character['name']}")
        print(f"   图片管理器: {'可用' if persona.image_manager else '不可用'}")
        
        if persona.image_manager:
            manager_type = persona.image_manager.__class__.__name__
            print(f"   管理器类型: {manager_type}")
            
            # 测试图片选择
            module, topic, tags = persona.get_random_topic()
            print(f"   测试话题: {module} - {topic}")
            
            # 注意：这里不会实际生成图片，只是测试选择逻辑
            image_path = persona.select_image(module, topic)
            if image_path:
                print(f"   图片选择: {os.path.basename(image_path) if image_path else '无图片'}")
            else:
                print(f"   图片选择: 无图片")
        
        return True
        
    except Exception as e:
        print(f"❌ CharacterPersona 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_runninghub_connection():
    """测试RunningHub连接（不实际生成图片）"""
    print("\n🌐 测试RunningHub连接...")
    
    try:
        from scripts.runninghub_client import RunningHubClient
        
        # 加载配置
        config_path = "/home/ubuntu/xhs-automation/config/runninghub_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if not config.get('enabled', False):
            print("⚠️  RunningHub在配置中已禁用，跳过连接测试")
            return True
        
        # 初始化客户端（但不实际调用API）
        client = RunningHubClient(
            consumer_api_key=config.get('consumer_api_key'),
            output_dir="/tmp/test_runninghub"
        )
        
        print("✅ RunningHub客户端初始化成功")
        print(f"   API类型: {'消费级' if client.is_consumer else '企业级'}")
        print(f"   单次成本: {client.cost_per_task}元")
        
        # 测试工作流文件加载
        try:
            workflow_data = client._load_workflow_json()
            print(f"✅ 工作流文件加载成功，包含 {len(workflow_data)} 个节点")
            
            # 测试节点查找
            node_id, field_name = client._find_text_node(workflow_data)
            print(f"✅ 文本节点查找成功: 节点 {node_id}, 字段 {field_name}")
            
        except Exception as e:
            print(f"⚠️  工作流测试失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ RunningHub连接测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("🚀 RunningHub集成测试开始")
    print("=" * 60)
    
    tests = [
        ("导入测试", test_imports),
        ("配置测试", test_configs),
        ("人物初始化测试", test_character_persona),
        ("RunningHub连接测试", test_runninghub_connection)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} 执行异常: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总:")
    
    all_passed = True
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {test_name}: {status}")
        if not success:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！集成准备就绪。")
        print("\n下一步:")
        print("1. 重启小红书自动化服务: systemctl restart xhs-automation")
        print("2. 监控日志: tail -f /home/ubuntu/xhs-automation/logs/automation.log")
        print("3. 测试实际生成（可选，会产生成本）")
    else:
        print("⚠️  部分测试失败，需要修复。")
        print("\n建议检查:")
        print("1. 文件权限和路径")
        print("2. Python依赖")
        print("3. 配置文件格式")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)