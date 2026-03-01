"""
图片处理工具 - 小红书图片标准化
"""

import os
import time
import logging
import numpy as np
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


try:
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    logger.warning("imagehash 未安装，pHash 功能不可用")


class ImageAntiFingerprint:
    """图片抗指纹处理 - 防止 AI 生成图片被平台检测"""
    
    def __init__(self, hash_db_path: str = "data/cache/image_hashes.json"):
        self.hash_db_path = hash_db_path
        self.hash_db = {}
        self._load_hash_db()
    
    def _load_hash_db(self):
        """加载哈希数据库"""
        if not os.path.exists(self.hash_db_path):
            return
        
        try:
            import json
            with open(self.hash_db_path, 'r') as f:
                self.hash_db = json.load(f)
            logger.info(f"已加载 {len(self.hash_db)} 个图片哈希")
        except Exception as e:
            logger.warning(f"加载哈希数据库失败: {e}")
    
    def _save_hash_db(self):
        """保存哈希数据库"""
        try:
            import json
            os.makedirs(os.path.dirname(self.hash_db_path), exist_ok=True)
            with open(self.hash_db_path, 'w') as f:
                json.dump(self.hash_db, f)
        except Exception as e:
            logger.warning(f"保存哈希数据库失败: {e}")
    
    def compute_phash(self, image_path: str) -> str:
        """计算 pHash 感知哈希"""
        if not IMAGEHASH_AVAILABLE:
            return ""
        
        try:
            img = Image.open(image_path)
            phash = imagehash.phash(img)
            return str(phash)
        except Exception as e:
            logger.error(f"计算 pHash 失败: {e}")
            return ""
    
    def is_duplicate(self, new_hash: str, threshold: int = 5) -> bool:
        """检查是否与已有图片重复"""
        if not new_hash or new_hash in self.hash_db:
            return True
        
        for existing_hash in self.hash_db.keys():
            if self._hash_distance(new_hash, existing_hash) <= threshold:
                return True
        
        return False
    
    def _hash_distance(self, hash1: str, hash2: str) -> int:
        """计算两个哈希的海明距离"""
        if len(hash1) != len(hash2):
            return 999
        
        distance = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
        return distance
    
    def add_to_db(self, image_path: str, hash_value: str = None):
        """将图片添加到哈希数据库"""
        if not hash_value:
            hash_value = self.compute_phash(image_path)
        
        if hash_value:
            self.hash_db[hash_value] = {
                "path": image_path,
                "timestamp": time.time()
            }
            self._save_hash_db()
    
    def remove_exif(self, image_path: str, output_path: str = None) -> str:
        """
        清理 EXIF 元数据
        
        去除 AI 软件标记等敏感信息
        """
        img = Image.open(image_path)
        
        data = list(img.getdata())
        img_without_exif = Image.new(img.mode, img.size)
        img_without_exif.putdata(data)
        
        if output_path is None:
            output_path = image_path
        
        img_without_exif.save(output_path, img.format or "JPEG")
        logger.info(f"已清理 EXIF: {output_path}")
        
        return output_path
    
    def add_noise(self, image_path: str, output_path: str = None, 
                  noise_level: float = 2.0) -> str:
        """
        注入高频噪声
        
        添加肉眼不可见的高频噪声，改变图片数字指纹
        """
        import numpy as np
        
        img = Image.open(image_path)
        
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        img_array = np.array(img, dtype=np.float32)
        
        noise = np.random.normal(0, noise_level, img_array.shape)
        noisy_img = np.clip(img_array + noise, 0, 255).astype(np.uint8)
        
        result = Image.fromarray(noisy_img)
        
        if output_path is None:
            output_path = image_path
        
        result.save(output_path, quality=95)
        logger.info(f"已注入噪声: {output_path}, level={noise_level}")
        
        return output_path
    
    def adjust_channels(self, image_path: str, output_path: str = None,
                       r_adj: float = 1.0, g_adj: float = 1.0, b_adj: float = 1.0) -> str:
        """
        微调 RGB 通道
        
        轻微调整各通道值，改变图片指纹
        """
        import numpy as np
        
        img = Image.open(image_path)
        
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        img_array = np.array(img, dtype=np.float32)
        
        img_array[:, :, 0] = np.clip(img_array[:, :, 0] * r_adj, 0, 255)
        img_array[:, :, 1] = np.clip(img_array[:, :, 1] * g_adj, 0, 255)
        img_array[:, :, 2] = np.clip(img_array[:, :, 2] * b_adj, 0, 255)
        
        result = Image.fromarray(img_array.astype(np.uint8))
        
        if output_path is None:
            output_path = image_path
        
        result.save(output_path, quality=95)
        logger.info(f"已调整通道: {output_path}")
        
        return output_path
    
    def process(self, image_path: str, output_path: str = None,
                remove_exif: bool = True, add_noise: bool = True) -> str:
        """
        完整抗指纹处理流程
        """
        if output_path is None:
            p = Path(image_path)
            output_path = str(p.parent / f"{p.stem}_anti{p.suffix}")
        
        temp_path = output_path
        
        if remove_exif:
            temp_path = self.remove_exif(image_path, output_path)
        
        if add_noise:
            temp_path = self.add_noise(temp_path)
        
        hash_value = self.compute_phash(output_path)
        
        if self.is_duplicate(hash_value):
            logger.warning(f"检测到重复图片: {image_path}")
            hash_value = self.compute_phash(image_path) + "_modified"
        
        self.add_to_db(output_path, hash_value)
        
        return output_path


def process_anti_fingerprint(input_path: str, output_path: str = None) -> str:
    """便捷函数: 抗指纹处理"""
    processor = ImageAntiFingerprint()
    return processor.process(input_path, output_path)


def verify_image(path: str) -> tuple[bool, str]:
    """
    校验图片完整性
    
    Args:
        path: 图片路径
    
    Returns:
        (is_valid, error_message)
    """
    if not os.path.exists(path):
        return False, "file_not_found"
    
    try:
        with Image.open(path) as img:
            img.verify()
        return True, "ok"
    except Exception as e:
        logger.warning(f"图片校验失败: {path}, error: {e}")
        return False, str(e)


def crop_to_34_ratio(img: Image.Image) -> Image.Image:
    """
    居中裁剪为 3:4 比例
    
    Args:
        img: PIL Image 对象
    
    Returns:
        裁剪后的 Image 对象
    """
    width, height = img.size
    target_ratio = 3 / 4
    
    current_ratio = width / height
    
    if abs(current_ratio - target_ratio) < 0.01:
        return img
    
    if current_ratio > target_ratio:
        new_width = int(height * target_ratio)
        left = (width - new_width) // 2
        img = img.crop((left, 0, left + new_width, height))
    else:
        new_height = int(width / target_ratio)
        top = (height - new_height) // 2
        img = img.crop((0, top, width, top + new_height))
    
    return img


def adaptive_compress(img: Image.Image, max_size_kb: int = 1024) -> Image.Image:
    """
    自适应压缩图片
    
    Args:
        img: PIL Image 对象
        max_size_kb: 最大文件大小 (KB)
    
    Returns:
        压缩后的 Image 对象
    """
    import io
    
    max_bytes = max_size_kb * 1024
    quality = 95
    
    while quality > 50:
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        if len(buffer.getvalue()) <= max_bytes:
            break
        quality -= 5
    
    return img


def process_and_verify_image(
    input_path: str,
    output_path: str = None,
    target_size: tuple = (1080, 1440),
    max_size_kb: int = 1024
) -> tuple[bool, str]:
    """
    综合处理图片: 校验 + 3:4裁剪 + 压缩
    
    Args:
        input_path: 输入图片路径
        output_path: 输出路径 (默认覆盖原图)
        target_size: 目标尺寸 (默认 1080x1440)
        max_size_kb: 最大文件大小 (KB)
    
    Returns:
        (success, message)
    """
    if output_path is None:
        output_path = input_path
    
    try:
        is_valid, error = verify_image(input_path)
        if not is_valid:
            return False, f"verify_failed: {error}"
        
        with Image.open(input_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            img = crop_to_34_ratio(img)
            
            if img.size != target_size:
                img = img.resize(target_size, Image.LANCZOS)
            
            img = adaptive_compress(img, max_size_kb)
            
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            img.save(output_path, format='JPEG', quality=85, optimize=True)
        
        final_size = os.path.getsize(output_path) / 1024
        logger.info(f"图片处理完成: {output_path}, size={final_size:.1f}KB")
        return True, f"ok, size={final_size:.1f}KB"
    
    except Exception as e:
        logger.error(f"图片处理失败: {input_path}, error: {e}")
        return False, str(e)
