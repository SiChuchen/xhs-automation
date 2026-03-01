#!/usr/bin/env python3
"""
自定义发布脚本 - 支持自定义标题、内容和标签
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.xhs_automation_monitored import AutomationManager
from scripts.monitoring import MonitoringSystem

def custom_publish(title, content, tags=None, module="hot_topics"):
    """自定义发布"""
    print(f"📝 准备发布: {title}")
    
    # 初始化自动化系统
    automation = AutomationManager()
    
    # 检查登录状态
    if not automation.publisher.check_login_status():
        print("❌ 登录状态失效，请重新登录")
        return False
    
    # 生成图片提示词
    prompt = automation.persona._generate_image_prompt(module, title, content)
    print(f"🎨 图片提示词: {prompt}")
    
    # 生成图片
    print("🖼️  生成图片中...")
    image_path = automation.persona.image_manager.generate_image_with_prompt(module, title, prompt)
    if not image_path:
        print("❌ 图片生成失败")
        return False
    
    print(f"✅ 图片生成成功: {image_path}")
    
    # 准备标签
    if tags is None:
        tags = ["开学焦虑", "大学生活", "返校"]
    
    # 发布内容
    print("📤 发布中...")
    try:
        result = automation.publisher.publish_note(
            title=title,
            content=content,
            image_path=image_path,
            tags=tags,
            max_retries=3
        )
        
        if result.get("success"):
            print("✅ 发布成功!")
            return True
        else:
            print(f"❌ 发布失败: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ 发布异常: {e}")
        return False

def main():
    """主函数"""
    # 自定义内容
    title = "开学前夜舍不得家的心情谁懂"
    content = """过年有多开心，现在就有多不想开学😅

刚吃完最后一顿家里的饭我妈就开始念叨"在学校要好好吃饭 别省钱"我爸在旁边假装看电视 其实一直在偷看我

说实话 第一次这么不想开学
不是因为作业没写完
是总觉得过完这个年 好像又长大了一点

明年这时候就该实习了吧不知道还能不能在家过这么完整的年

姐妹们也是吗？都啥时候开学啊"""
    
    tags = ["开学焦虑", "大学生活", "返校"]
    
    print("=" * 50)
    print("📱 小红书自定义发布")
    print("=" * 50)
    print(f"标题: {title}")
    print(f"长度: {len(title)}字")
    print("-" * 50)
    print(f"内容:\n{content}")
    print("-" * 50)
    print(f"标签: {tags}")
    print("=" * 50)
    
    # 确认发布
    confirm = input("确认发布? (y/n): ").strip().lower()
    if confirm != 'y':
        print("取消发布")
        return
    
    # 执行发布
    success = custom_publish(title, content, tags)
    
    if success:
        print("🎉 发布完成!")
    else:
        print("❌ 发布失败")

if __name__ == "__main__":
    main()