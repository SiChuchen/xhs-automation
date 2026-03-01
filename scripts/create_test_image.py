#!/usr/bin/env python3
"""
创建测试用竖屏图片 - 小红书推荐尺寸1080x1440
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_vertical_test_image(output_path, width=1080, height=1440):
    """创建竖屏测试图片"""
    # 创建新图片
    img = Image.new('RGB', (width, height), color=(70, 130, 180))  # 钢蓝色背景
    
    draw = ImageDraw.Draw(img)
    
    # 添加简单文字
    try:
        # 尝试加载字体
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    except:
        font = ImageFont.load_default()
    
    # 添加居中文字
    text = "林晓芯\n测试图片\n1080×1440"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    draw.text((x, y), text, font=font, fill=(255, 255, 255), align='center')
    
    # 保存为高质量JPG
    img.save(output_path, 'JPEG', quality=90, optimize=True)
    
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ 创建测试图片: {output_path}")
    print(f"   尺寸: {width}x{height}")
    print(f"   大小: {size_mb:.2f} MB")
    
    return True

def create_simple_color_image(output_path, width=1080, height=1440):
    """创建纯色简单图片"""
    # 渐变色
    img = Image.new('RGB', (width, height))
    
    for y in range(height):
        # 从上到下的渐变
        r = int(100 + (y / height) * 100)
        g = int(150 + (y / height) * 80)
        b = int(200 + (y / height) * 50)
        
        for x in range(width):
            img.putpixel((x, y), (r, g, b))
    
    # 保存
    img.save(output_path, 'JPEG', quality=85, optimize=True)
    
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ 创建纯色图片: {output_path}")
    print(f"   尺寸: {width}x{height}")
    print(f"   大小: {size_mb:.2f} MB")
    
    return True

if __name__ == "__main__":
    # 创建目录
    os.makedirs("/tmp/xhs-official/images", exist_ok=True)
    
    print("🖼️ 创建小红书测试图片")
    print("=" * 50)
    
    # 创建竖屏测试图片
    test1_path = "/tmp/xhs-official/images/test_vertical.jpg"
    create_vertical_test_image(test1_path)
    
    # 创建纯色图片
    test2_path = "/tmp/xhs-official/images/test_simple.jpg"
    create_simple_color_image(test2_path)
    
    print("\n📊 所有测试图片:")
    for filename in os.listdir("/tmp/xhs-official/images"):
        if filename.startswith("test_"):
            path = os.path.join("/tmp/xhs-official/images", filename)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"   {filename}: {size_mb:.2f} MB")