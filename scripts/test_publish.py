#!/usr/bin/env python3
"""测试发布功能"""

import sys
import os
import json
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class SimplePublisher:
    """简单发布测试"""
    
    def __init__(self):
        self.base_url = "http://localhost:18060"
        self.api_url = f"{self.base_url}/api/v1"
    
    def check_login(self):
        """检查登录状态"""
        try:
            response = requests.get(f"{self.api_url}/login/status", timeout=30)
            data = response.json()
            print(f"登录状态: {data}")
            return data.get('success', False)
        except Exception as e:
            print(f"检查登录失败: {e}")
            return False
    
    def publish_test(self):
        """发布测试内容"""
        # 使用人设相关的内容
        title = "【自动化测试】林晓芯的技术日常"
        content = """大家好，我是林晓芯（杨枝甘露椰果红豆）～

这是自动化发布系统的测试内容，验证人物设定与内容生成的整合效果。

作为计算机专业的学生，日常就是和各种代码、工具打交道。今天测试一下自动化发布流程，后续会分享更多技术干货和效率工具！

#理工科女大 #自动化测试 #技术日常
"""
        image_path = "/images/001原画.png"
        
        payload = {
            "title": title,
            "content": content,
            "images": [image_path],
            "tags": ["#自动化测试", "#技术日常", "#计算机专业", "#效率工具"]
        }
        
        print(f"发布内容:")
        print(f"标题: {title}")
        print(f"图片: {image_path}")
        print(f"标签: {payload['tags']}")
        
        try:
            response = requests.post(
                f"{self.api_url}/publish",
                json=payload,
                timeout=120
            )
            data = response.json()
            print(f"发布响应: {data}")
            return data
        except Exception as e:
            print(f"发布失败: {e}")
            return {"success": False, "error": str(e)}

def main():
    """主函数"""
    print("🧪 开始发布测试...")
    
    publisher = SimplePublisher()
    
    # 检查登录
    if not publisher.check_login():
        print("❌ 登录状态无效，请检查cookies")
        return
    
    print("✅ 登录状态正常")
    
    # 执行发布
    result = publisher.publish_test()
    
    if result.get('success'):
        print("🎉 发布测试成功!")
        print(f"   帖子ID: {result.get('data', {}).get('post_id', 'Unknown')}")
    else:
        print(f"❌ 发布测试失败: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()