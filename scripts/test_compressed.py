#!/usr/bin/env python3
"""测试压缩图片的发布功能"""

import sys
import os
import requests
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_publish_compressed():
    """测试压缩图片发布"""
    api_url = "http://localhost:18060/api/v1"
    
    # 使用压缩后的图片
    title = "【图片压缩测试】林晓芯的技术日常"
    content = """大家好，我是林晓芯（杨枝甘露椰果红豆）～

测试压缩图片后的发布效果。原始图片5MB+，压缩后仅0.1MB左右，上传速度应该会快很多！

作为计算机专业学生，优化和效率是我们的日常。连图片上传也要追求极致效率～

#技术测试 #图片优化 #效率控 #计算机专业
"""
    
    # 尝试使用压缩后的图片
    image_path = "/images/001原画.jpg"
    
    payload = {
        "title": title,
        "content": content,
        "images": [image_path],
        "tags": ["#技术测试", "#图片优化", "#效率控", "#计算机专业"]
    }
    
    print(f"📤 发布测试 - 压缩图片")
    print(f"   标题: {title}")
    print(f"   图片: {image_path}")
    print(f"   大小: 约0.1MB (压缩后)")
    
    try:
        # 先检查登录
        status_resp = requests.get(f"{api_url}/login/status", timeout=30)
        status_data = status_resp.json()
        print(f"   登录状态: {status_data.get('success', False)}")
        
        # 发布
        response = requests.post(
            f"{api_url}/publish",
            json=payload,
            timeout=120
        )
        data = response.json()
        
        print(f"   发布结果: {data}")
        
        if data.get('success'):
            print("✅ 测试成功!")
            return True
        else:
            print(f"❌ 测试失败: {data.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

if __name__ == "__main__":
    print("🧪 开始压缩图片发布测试...")
    success = test_publish_compressed()
    
    if success:
        print("\n🎉 压缩图片发布测试通过!")
        print("   说明: 图片压缩方案有效，可以继续自动化流程")
    else:
        print("\n⚠️  压缩图片发布测试失败")
        print("   可能需要进一步优化图片处理")