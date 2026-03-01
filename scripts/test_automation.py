#!/usr/bin/env python3
"""测试自动化脚本功能"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.xhs_automation import CharacterPersona

def test_persona():
    """测试人物设定类"""
    config_path = "/home/ubuntu/xhs-automation/config/publish_config.json"
    soul_path = "/home/ubuntu/xhs-automation/config/soul.md"
    
    print("🧪 测试人物设定类...")
    persona = CharacterPersona(config_path, soul_path)
    
    print(f"✅ 人物: {persona.character['name']} ({persona.character['nickname']})")
    print(f"✅ 专业: {persona.character['major']}")
    print(f"✅ 性格: {persona.character['personality']}")
    
    # 测试内容生成
    print("\n🧪 测试内容生成...")
    for _ in range(3):
        module, topic, tags = persona.get_random_topic()
        title, content = persona.generate_content(module, topic)
        image = persona.select_image(module)
        
        print(f"\n模块: {module}")
        print(f"话题: {topic}")
        print(f"标题: {title}")
        print(f"内容预览: {content[:100]}...")
        print(f"图片: {image}")
        print(f"标签: {tags[:3]}")
        print("-" * 50)
    
    print("\n✅ 测试完成!")

if __name__ == "__main__":
    test_persona()