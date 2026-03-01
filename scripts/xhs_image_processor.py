#!/usr/bin/env python3
"""
小红书图片处理器 - 确保图片符合平台要求
1. 竖屏比例 (1080x1440 推荐)
2. 合适大小 (< 2MB)
3. 正确格式 (JPG)
"""

import os
from PIL import Image

class XiaohongshuImageProcessor:
    """小红书图片处理器"""
    
    def __init__(self, max_size_mb=2.0, target_width=1080, target_height=1440):
        self.max_size_mb = max_size_mb
        self.target_width = target_width
        self.target_height = target_height
        self.aspect_ratio = target_width / target_height  # 0.75 (竖屏)
    
    def process_image(self, input_path, output_path):
        """
        处理图片以适应小红书要求
        
        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径
            
        Returns:
            bool: 是否成功
        """
        try:
            print(f"📷 处理图片: {os.path.basename(input_path)}")
            
            # 打开图片
            img = Image.open(input_path)
            original_size = os.path.getsize(input_path) / (1024 * 1024)
            print(f"   原始尺寸: {img.size[0]}x{img.size[1]}")
            print(f"   原始大小: {original_size:.2f} MB")
            
            # 1. 转换为RGB（移除透明通道）
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 2. 计算目标尺寸（保持内容，适应竖屏）
            processed = self._fit_to_vertical(img)
            
            # 3. 保存为JPG（逐步调整质量）
            quality = 90
            success = False
            
            for q in range(quality, 40, -10):
                processed.save(output_path, 'JPEG', quality=q, optimize=True)
                final_size = os.path.getsize(output_path) / (1024 * 1024)
                
                if final_size <= self.max_size_mb:
                    print(f"   处理完成: {final_size:.2f} MB (质量: {q}%)")
                    print(f"   最终尺寸: {processed.size[0]}x{processed.size[1]}")
                    success = True
                    break
            
            if not success:
                # 强制压缩
                processed.save(output_path, 'JPEG', quality=40, optimize=True)
                final_size = os.path.getsize(output_path) / (1024 * 1024)
                print(f"   强制压缩: {final_size:.2f} MB (质量: 40%)")
                print(f"   最终尺寸: {processed.size[0]}x{processed.size[1]}")
                success = True
            
            if success:
                print(f"   ✅ 保存到: {output_path}")
            else:
                print(f"   ❌ 处理失败")
            
            return success
            
        except Exception as e:
            print(f"❌ 处理失败: {e}")
            return False
    
    def _fit_to_vertical(self, img):
        """将图片适配到竖屏画布"""
        img_width, img_height = img.size
        img_aspect = img_width / img_height
        
        # 目标画布
        canvas = Image.new('RGB', (self.target_width, self.target_height), (245, 245, 245))
        
        # 计算缩放和位置
        if img_aspect > self.aspect_ratio:
            # 图片更宽，按宽度缩放
            new_width = self.target_width
            new_height = int(self.target_width / img_aspect)
            x = 0
            y = (self.target_height - new_height) // 2
        else:
            # 图片更高，按高度缩放
            new_height = self.target_height
            new_width = int(self.target_height * img_aspect)
            x = (self.target_width - new_width) // 2
            y = 0
        
        # 缩放图片
        resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 粘贴到画布中心
        canvas.paste(resized, (x, y))
        
        return canvas
    
    def process_character_images(self):
        """处理人物设定图片"""
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
                
                # 生成输出文件名（保持原名但改为.jpg）
                name_without_ext = os.path.splitext(filename)[0]
                output_filename = f"{name_without_ext}_vertical.jpg"
                output_path = os.path.join(target_dir, output_filename)
                
                if self.process_image(input_path, output_path):
                    success_count += 1
        
        print(f"\n✅ 完成! 成功处理 {success_count} 张图片")
        return success_count > 0

def main():
    """主函数"""
    print("🖼️ 小红书图片处理器 - 竖屏优化版")
    print("=" * 50)
    
    processor = XiaohongshuImageProcessor()
    
    # 处理人物图片
    if not processor.process_character_images():
        print("❌ 图片处理失败")
        return
    
    # 显示结果
    print("\n📊 处理后的图片:")
    image_dir = "/tmp/xhs-official/images"
    for filename in sorted(os.listdir(image_dir)):
        if 'vertical' in filename.lower():
            path = os.path.join(image_dir, filename)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            
            with Image.open(path) as img:
                print(f"   {filename}: {img.size[0]}x{img.size[1]}, {size_mb:.2f} MB")

if __name__ == "__main__":
    main()