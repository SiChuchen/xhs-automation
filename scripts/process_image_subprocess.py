#!/usr/bin/env python3
"""
图片处理子进程 - 独立进程处理图片，避免内存碎片化
"""

import sys
import json
import io
from PIL import Image


def process_image(
    input_path: str,
    output_path: str,
    target_size: tuple = None,
    max_size_kb: int = 500
) -> dict:
    """
    处理图片 - 在子进程中执行
    
    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径
        target_size: 目标尺寸 (width, height)
        max_size_kb: 最大文件大小 KB
    
    Returns:
        {"success": bool, "message": str, "size": int}
    """
    try:
        with Image.open(input_path) as img:
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            
            if target_size:
                img = img.resize(target_size, Image.LANCZOS)
            
            quality = 95
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            
            while output.tell() > max_size_kb * 1024 and quality > 50:
                output = io.BytesIO()
                quality -= 5
                img.save(output, format='JPEG', quality=quality, optimize=True)
            
            with open(output_path, 'wb') as f:
                f.write(output.getvalue())
        
        size = 0
        if __import__('os').path.exists(output_path):
            size = __import__('os').path.getsize(output_path)
        
        return {
            "success": True,
            "message": "ok",
            "size": size
        }
    
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "size": 0
        }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            params = json.loads(sys.argv[1])
            result = process_image(**params)
            print(json.dumps(result))
        except Exception as e:
            print(json.dumps({"success": False, "message": str(e), "size": 0}))
    else:
        print(json.dumps({"success": False, "message": "no params", "size": 0}))
