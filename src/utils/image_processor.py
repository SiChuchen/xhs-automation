"""
图片处理工具 - 小红书图片标准化
"""

import os
import logging
from typing import Tuple, Optional, List
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)


class ImageProcessor:
    """小红书图片处理器"""
    
    XHS_SPECS = {
        "portrait": {
            "ratio": (3, 4),
            "width": 1080,
            "height": 1440,
            "quality": 85,
            "format": "JPEG",
        },
        "landscape": {
            "ratio": (4, 3),
            "width": 1440,
            "height": 1080,
            "quality": 85,
            "format": "JPEG",
        },
        "square": {
            "ratio": (1, 1),
            "width": 1080,
            "height": 1080,
            "quality": 85,
            "format": "JPEG",
        },
    }
    
    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
    
    def __init__(self, spec: str = "portrait"):
        self.spec = self.XHS_SPECS.get(spec, self.XHS_SPECS["portrait"])
        self.target_ratio = self.spec["ratio"]
        self.target_width = self.spec["width"]
        self.target_height = self.spec["height"]
    
    def load_image(self, path: str) -> Image.Image:
        """加载图片"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"图片不存在: {path}")
        
        img = Image.open(path)
        
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        return img
    
    def resize_to_aspect(self, img: Image.Image) -> Image.Image:
        """
        按目标比例缩放图片
        
        策略: 先缩放到目标比例的边界，再裁剪
        """
        current_width, current_height = img.size
        current_ratio = current_width / current_height
        target_ratio = self.target_width / self.target_height
        
        if abs(current_ratio - target_ratio) < 0.01:
            return img.resize((self.target_width, self.target_height), Image.LANCZOS)
        
        if current_ratio > target_ratio:
            new_width = int(current_height * target_ratio)
            img = img.resize((new_width, current_height), Image.LANCZOS)
        else:
            new_height = int(current_width / target_ratio)
            img = img.resize((current_width, new_height), Image.LANCZOS)
        
        return img
    
    def crop_to_spec(self, img: Image.Image) -> Image.Image:
        """裁剪到目标规格"""
        width, height = img.size
        
        if width > self.target_width:
            left = (width - self.target_width) // 2
            img = img.crop((left, 0, left + self.target_width, height))
        
        if height > self.target_height:
            top = (height - self.target_height) // 2
            img = img.crop((0, top, width, top + self.target_height))
        
        if img.size != (self.target_width, self.target_height):
            img = img.resize((self.target_width, self.target_height), Image.LANCZOS)
        
        return img
    
    def compress(self, img: Image.Image, quality: int = None) -> Image.Image:
        """调整压缩质量"""
        if quality is None:
            quality = self.spec["quality"]
        
        self._compress_quality = quality
        return img
    
    def save(self, img: Image.Image, output_path: str, quality: int = None) -> str:
        """保存图片"""
        if quality is None:
            quality = self.spec["quality"]
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        img.save(
            output_path,
            format=self.spec["format"],
            quality=quality,
            optimize=True
        )
        
        file_size = os.path.getsize(output_path)
        
        if file_size > self.MAX_FILE_SIZE:
            logger.warning(f"图片仍超过 2MB: {file_size} bytes")
            img = self._reduce_quality(img, output_path)
        
        return output_path
    
    def _reduce_quality(self, img: Image.Image, output_path: str) -> Image.Image:
        """递归降低质量直到满足大小要求"""
        quality = self._compress_quality
        
        while quality > 50:
            quality -= 10
            img.save(
                output_path,
                format=self.spec["format"],
                quality=quality,
                optimize=True
            )
            
            if os.path.getsize(output_path) <= self.MAX_FILE_SIZE:
                break
        
        return img
    
    def validate_specs(self, img: Image.Image) -> dict:
        """验证图片规格"""
        width, height = img.size
        ratio = width / height
        
        return {
            "width": width,
            "height": height,
            "ratio": f"{ratio:.2f}",
            "target_ratio": f"{self.target_ratio[0]/self.target_ratio[1]:.2f}",
            "ratio_match": abs(ratio - self.target_ratio[0]/self.target_ratio[1]) < 0.01,
            "size_match": width == self.target_width and height == self.target_height,
        }
    
    def process_for_xhs(self, input_path: str, output_path: str = None) -> str:
        """
        完整处理流程
        
        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径
        
        Returns:
            处理后的图片路径
        """
        logger.info(f"开始处理图片: {input_path}")
        
        if output_path is None:
            p = Path(input_path)
            output_path = str(p.parent / f"{p.stem}_xhs{p.suffix}")
        
        img = self.load_image(input_path)
        
        img = self.resize_to_aspect(img)
        img = self.crop_to_spec(img)
        
        output_path = self.save(img, output_path)
        
        logger.info(f"图片处理完成: {output_path}")
        return output_path
    
    def batch_process(self, input_paths: List[str], output_dir: str = None) -> List[str]:
        """批量处理"""
        results = []
        
        for input_path in input_paths:
            try:
                if output_dir:
                    p = Path(input_path)
                    output_path = os.path.join(output_dir, f"{p.stem}_xhs{p.suffix}")
                else:
                    output_path = None
                
                result = self.process_for_xhs(input_path, output_path)
                results.append(result)
            except Exception as e:
                logger.error(f"处理失败 {input_path}: {e}")
                results.append(None)
        
        return results


def process_image_for_xhs(input_path: str, output_path: str = None, spec: str = "portrait") -> str:
    """便捷函数: 处理单张图片"""
    processor = ImageProcessor(spec)
    return processor.process_for_xhs(input_path, output_path)


def resize_image(input_path: str, output_path: str, width: int, height: int, quality: int = 85):
    """便捷函数: 调整图片大小"""
    img = Image.open(input_path)
    
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    img = img.resize((width, height), Image.LANCZOS)
    img.save(output_path, quality=quality, optimize=True)


def compress_image(input_path: str, output_path: str, quality: int = 85, max_size: int = None):
    """便捷函数: 压缩图片"""
    img = Image.open(input_path)
    
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    if max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    
    img.save(output_path, quality=quality, optimize=True)
