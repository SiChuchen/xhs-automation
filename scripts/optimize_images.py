#!/usr/bin/env python3
"""
小红书图片优化工具
将图片优化到适合上传的尺寸和大小
支持批量处理、自动压缩、保持纵横比
"""

import os
import sys
import argparse
import json
from pathlib import Path
from PIL import Image
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 小红书推荐尺寸
XHS_SIZES = {
    '1920': (1920, 3840),   # 更大尺寸，用于高质量
    '1080': (1080, 1920),  # 竖版推荐
    '720': (720, 1280),     # 较小尺寸
    '原图': None            # 保持原尺寸但压缩
}

# 默认配置
DEFAULT_TARGET_SIZE = '1080'
DEFAULT_QUALITY = 95
MAX_FILE_SIZE_KB = 600  # 最大文件大小


def get_image_size(path: str) -> tuple:
    """获取图片尺寸"""
    try:
        with Image.open(path) as img:
            return img.size
    except Exception as e:
        logger.error(f"无法读取图片 {path}: {e}")
        return None


def calculate_new_size(original_size: tuple, target_width: int) -> tuple:
    """计算新的图片尺寸（保持纵横比）"""
    orig_width, orig_height = original_size
    if orig_width <= target_width:
        return original_size
    
    # 按比例缩放
    ratio = target_width / orig_width
    new_width = target_width
    new_height = int(orig_height * ratio)
    
    return (new_width, new_height)


def compress_image(input_path: str, output_path: str, target_size: str = '1080', 
                   quality: int = 85, max_iterations: int = 5) -> bool:
    """
    压缩图片到目标尺寸和大小
    
    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径
        target_size: 目标尺寸 ('1080', '720', '原图')
        quality: 初始质量 (1-100)
        max_iterations: 最大迭代次数（用于压缩文件大小）
    
    Returns:
        是否成功
    """
    try:
        # 打开图片
        with Image.open(input_path) as img:
            # 转换为 RGB（如果是 RGBA 或其他模式）
            if img.mode in ('RGBA', 'P', 'L'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode == 'RGBA':
                    rgb_img.paste(img, mask=img.split()[3])
                else:
                    rgb_img = img.convert('RGB')
                img = rgb_img
            
            # 计算目标尺寸
            target_width = XHS_SIZES.get(target_size, (1080, 1920))[0]
            if target_size == '原图':
                new_size = img.size
            else:
                new_size = calculate_new_size(img.size, target_width)
            
            # 调整尺寸
            if new_size != img.size:
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"调整尺寸: {img.size} -> {new_size}")
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 智能压缩：目标是 400-600KB
            current_quality = quality
            best_quality = current_quality
            best_size_kb = float('inf')
            
            for i in range(max_iterations):
                img.save(output_path, 'JPEG', quality=current_quality, optimize=True)
                
                # 检查文件大小
                file_size_kb = os.path.getsize(output_path) / 1024
                
                # 记录最佳结果
                if abs(file_size_kb - 500) < abs(best_size_kb - 500):
                    best_quality = current_quality
                    best_size_kb = file_size_kb
                
                # 如果文件大小在 400-600KB 范围内，接受
                if 400 <= file_size_kb <= 600:
                    logger.info(f"✅ 图片已优化: {output_path}")
                    logger.info(f"   尺寸: {new_size}, 质量: {current_quality}%, 大小: {file_size_kb:.1f}KB")
                    return True
                
                # 调整质量
                if file_size_kb > 600:
                    # 文件太大，降低质量
                    current_quality -= 15
                elif file_size_kb < 400:
                    # 文件太小，提高质量
                    current_quality += 5
                
                # 质量范围限制
                if current_quality < 30:
                    current_quality = 30
                if current_quality > 100:
                    current_quality = 100
                
                # 如果质量调整很小，跳出循环
                if i > 0 and abs(current_quality - best_quality) < 5:
                    break
            
            # 使用最佳质量保存
            if best_size_kb < float('inf'):
                img.save(output_path, 'JPEG', quality=best_quality, optimize=True)
                final_size_kb = os.path.getsize(output_path) / 1024
                logger.info(f"✅ 图片已优化: {output_path}")
                logger.info(f"   尺寸: {new_size}, 质量: {best_quality}%, 大小: {final_size_kb:.1f}KB")
                return True
            else:
                logger.error(f"❌ 图片压缩失败")
                return False
            
    except Exception as e:
        logger.error(f"❌ 图片压缩失败: {e}")
        return False


def process_directory(input_dir: str, output_dir: str = None, target_size: str = '1080',
                     quality: int = 85) -> dict:
    """
    批量处理目录中的所有图片
    
    Args:
        input_dir: 输入目录
        output_dir: 输出目录（默认为 input_dir + '_optimized'）
        target_size: 目标尺寸
        quality: 初始质量
    
    Returns:
        处理结果统计
    """
    input_path = Path(input_dir)
    if output_dir is None:
        output_dir = input_path.parent / f"{input_path.name}_optimized"
    else:
        output_dir = Path(output_dir)
    
    # 支持的图片格式
    supported_formats = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    
    # 查找所有图片
    images = []
    for ext in supported_formats:
        images.extend(input_path.glob(f"*{ext}"))
        images.extend(input_path.glob(f"*{ext.upper()}"))
    
    if not images:
        logger.warning(f"在 {input_dir} 中未找到图片文件")
        return {'success': 0, 'failed': 0}
    
    logger.info(f"找到 {len(images)} 个图片文件")
    
    # 处理每个图片
    success = 0
    failed = 0
    
    for img_path in images:
        # 生成输出路径
        output_path = output_dir / f"{img_path.stem}_{target_size}.jpg"
        
        logger.info(f"处理: {img_path.name} ...")
        
        if compress_image(str(img_path), str(output_path), target_size, quality):
            success += 1
        else:
            failed += 1
    
    result = {
        'success': success,
        'failed': failed,
        'total': len(images),
        'output_dir': str(output_dir)
    }
    
    logger.info(f"处理完成: 成功 {success}, 失败 {failed}")
    return result


def optimize_character_images(source_dir: str, output_dir: str = None) -> dict:
    """
    专门优化人物形象图片
    生成多个尺寸版本供不同场景使用
    """
    if output_dir is None:
        output_dir = Path(source_dir) / "optimized"
    else:
        output_dir = Path(output_dir)
    
    # 不同场景使用的尺寸
    scenarios = {
        '1080': '1080',   # 高清发布
        '720': '720',     # 备用
    }
    
    source_path = Path(source_dir)
    supported_formats = {'.jpg', '.jpeg', '.png'}
    
    images = []
    for ext in supported_formats:
        images.extend(source_path.glob(f"*{ext}"))
    
    total_success = 0
    
    for img_path in images:
        logger.info(f"优化人物图片: {img_path.name}")
        
        for scenario, size in scenarios.items():
            output_path = output_dir / f"{img_path.stem}_{size}.jpg"
            if compress_image(str(img_path), str(output_path), size, quality=85):
                total_success += 1
    
    return {
        'success': total_success,
        'scenarios': scenarios,
        'output_dir': str(output_dir)
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="小红书图片优化工具")
    parser.add_argument('input', help="输入图片或目录")
    parser.add_argument('-o', '--output', help="输出目录（可选）")
    parser.add_argument('-s', '--size', default=DEFAULT_TARGET_SIZE, 
                        choices=['1920', '1080', '720', '原图'],
                        help=f"目标尺寸 (默认: {DEFAULT_TARGET_SIZE})")
    parser.add_argument('-q', '--quality', type=int, default=DEFAULT_QUALITY,
                        help=f"初始质量 1-100 (默认: {DEFAULT_QUALITY})")
    parser.add_argument('--character', action='store_true',
                        help="优化人物图片（生成多尺寸版本）")
    parser.add_argument('--max-size', type=int, default=MAX_FILE_SIZE_KB,
                        help=f"最大文件大小 KB (默认: {MAX_FILE_SIZE_KB})")
    
    args = parser.parse_args()
    
    # 更新全局配置
    MAX_FILE_SIZE_KB = args.max_size
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        logger.error(f"输入路径不存在: {input_path}")
        sys.exit(1)
    
    if input_path.is_file():
        # 单文件处理
        if args.output:
            output_path = args.output
        else:
            output_path = input_path.parent / f"{input_path.stem}_{args.size}.jpg"
        
        success = compress_image(str(input_path), str(output_path), args.size, args.quality)
        sys.exit(0 if success else 1)
    
    elif input_path.is_dir():
        # 目录处理
        if args.character:
            result = optimize_character_images(str(input_path), args.output)
        else:
            result = process_directory(str(input_path), args.output, args.size, args.quality)
        
        print(f"\n📊 处理结果:")
        print(f"   成功: {result['success']}")
        print(f"   失败: {result.get('failed', 0)}")
        print(f"   输出目录: {result['output_dir']}")
        
        sys.exit(0)
