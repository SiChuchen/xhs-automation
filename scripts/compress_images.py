#!/usr/bin/env python3
"""
图片压缩脚本 - 优化小红书图片上传
将大图片压缩到适合小红书发布的尺寸
"""

import os
import sys
from PIL import Image
import shutil

def compress_image(input_path, output_path, max_size_mb=2.0, max_dimension=1080):
    """
    压缩图片到指定大小和尺寸
    
    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径  
        max_size_mb: 最大文件大小（MB）
        max_dimension: 最大边长（像素）
    """
    try:
        # 打开图片
        img = Image.open(input_path)
        original_size = os.path.getsize(input_path) / (1024 * 1024)  # MB
        
        print(f"📷 处理图片: {os.path.basename(input_path)}")
        print(f"   原始尺寸: {img.size[0]}x{img.size[1]}")
        print(f"   原始大小: {original_size:.2f} MB")
        
        # 调整尺寸（保持长宽比）
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            new_width = int(img.size[0] * ratio)
            new_height = int(img.size[1] * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"   调整尺寸: {new_width}x{new_height}")
        
        # 转换为RGB模式（如果有透明通道）
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # 保存为JPEG（更小的文件大小）
        if input_path.lower().endswith('.png'):
            output_path = output_path.replace('.png', '.jpg')
        
        # 逐步降低质量直到满足大小要求
        quality = 85
        for q in range(quality, 40, -5):
            img.save(output_path, 'JPEG', quality=q, optimize=True)
            compressed_size = os.path.getsize(output_path) / (1024 * 1024)
            
            if compressed_size <= max_size_mb:
                print(f"   压缩成功: {compressed_size:.2f} MB (质量: {q}%)")
                print(f"   保存到: {output_path}")
                return True
        
        # 如果还是太大，强制压缩
        img.save(output_path, 'JPEG', quality=40, optimize=True)
        final_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"   强制压缩: {final_size:.2f} MB (质量: 40%)")
        print(f"   保存到: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ 压缩失败: {e}")
        return False

def compress_character_images():
    """压缩人物设定图片"""
    source_dir = "/home/ubuntu/character_design/photo"
    target_dir = "/tmp/xhs-official/images"
    
    if not os.path.exists(source_dir):
        print(f"❌ 源目录不存在: {source_dir}")
        return False
    
    os.makedirs(target_dir, exist_ok=True)
    
    success_count = 0
    for filename in os.listdir(source_dir):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            input_path = os.path.join(source_dir, filename)
            output_path = os.path.join(target_dir, filename)
            
            if compress_image(input_path, output_path):
                success_count += 1
    
    print(f"\n✅ 完成! 成功压缩 {success_count} 张图片")
    return success_count > 0

def test_compressed_images():
    """测试压缩后的图片"""
    image_dir = "/tmp/xhs-official/images"
    
    print("\n🧪 测试压缩后图片:")
    for filename in os.listdir(image_dir):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            path = os.path.join(image_dir, filename)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"   {filename}: {size_mb:.2f} MB")

def main():
    """主函数"""
    print("🖼️ 小红书图片压缩工具")
    print("=" * 50)
    
    # 压缩人物图片
    if not compress_character_images():
        print("❌ 图片压缩失败")
        sys.exit(1)
    
    # 显示结果
    test_compressed_images()
    
    print("\n📝 建议:")
    print("1. 小红书建议图片大小 < 10MB")
    print("2. 推荐尺寸: 1080x1440 像素")
    print("3. 格式: JPG/PNG")
    print("4. 竖屏比例效果最佳")

if __name__ == "__main__":
    # 安装依赖
    try:
        from PIL import Image
    except ImportError:
        print("⚠️ 需要安装Pillow库: pip install Pillow")
        sys.exit(1)
    
    main()