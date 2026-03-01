"""
布隆过滤器 - 用于去重
基于 Python bitarray 实现
"""

import hashlib
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from bitarray import bitarray
    BITARRAY_AVAILABLE = True
except ImportError:
    BITARRAY_AVAILABLE = False


class BloomFilter:
    """布隆过滤器 - 内存高效的去重工具"""
    
    def __init__(self, capacity: int = 1000000, error_rate: float = 0.001, filepath: Optional[str] = None):
        """
        初始化布隆过滤器
        
        Args:
            capacity: 预期存储数量
            error_rate: 期望的误判率
            filepath: 持久化文件路径
        """
        self.capacity = capacity
        self.error_rate = error_rate
        
        # 计算最优参数 (m/n * ln2 ≈ 0.693)
        num_bits = max(1000, int(-capacity * 1.44 * (error_rate ** 2))) if error_rate > 0 else int(capacity * 10)
        self.num_bits = max(10, num_bits)
        self.num_hashes = max(1, int(self.num_bits / capacity * 0.693))
        
        self.filepath = filepath
        self.num_bits = num_bits
        
        if BITARRAY_AVAILABLE:
            self.bit_array = bitarray(num_bits)
            if filepath and os.path.exists(filepath):
                self._load()
            else:
                self.bit_array.setall(0)
        else:
            self.bit_array = [False] * num_bits
        
        self._count = 0
        logger.info(f"布隆过滤器初始化: capacity={capacity}, error_rate={error_rate}, bits={num_bits}, hashes={self.num_hashes}")
    
    def _hashes(self, item: str):
        """生成多个哈希值"""
        hash1 = int(hashlib.md5(item.encode()).hexdigest(), 16)
        hash2 = int(hashlib.sha256(item.encode()).hexdigest(), 16)
        
        for i in range(self.num_hashes):
            yield (hash1 + i * hash2) % self.num_bits
    
    def add(self, item: str) -> bool:
        """
        添加元素
        
        Returns:
            True 如果是新元素, False 如果已存在(可能误判)
        """
        if self.contains(item):
            return False
        
        for idx in self._hashes(item):
            self.bit_array[idx] = True
        self._count += 1
        
        if self._count % 10000 == 0:
            self._save()
        
        return True
    
    def contains(self, item: str) -> bool:
        """检查元素是否存在"""
        for idx in self._hashes(item):
            if not self.bit_array[idx]:
                return False
        return True
    
    def __contains__(self, item: str) -> bool:
        return self.contains(item)
    
    def __len__(self) -> int:
        return self._count
    
    def _save(self):
        """保存到文件"""
        if not self.filepath:
            return
        
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            if BITARRAY_AVAILABLE:
                with open(self.filepath, 'wb') as f:
                    self.bit_array.tofile(f)
            logger.info(f"布隆过滤器已保存: {self.filepath}")
        except Exception as e:
            logger.warning(f"保存布隆过滤器失败: {e}")
    
    def _load(self):
        """从文件加载"""
        if not self.filepath or not os.path.exists(self.filepath):
            return
        
        try:
            if BITARRAY_AVAILABLE:
                with open(self.filepath, 'rb') as f:
                    self.bit_array = bitarray()
                    self.bit_array.fromfile(f)
            logger.info(f"布隆过滤器已加载: {self.filepath}, count={self._count}")
        except Exception as e:
            logger.warning(f"加载布隆过滤器失败: {e}")
    
    def close(self):
        """关闭并保存"""
        self._save()


class InteractionDeduplicator:
    """互动去重器 - 使用布隆过滤器"""
    
    def __init__(self, cache_dir: str = "data/cache"):
        os.makedirs(cache_dir, exist_ok=True)
        
        bloom_path = os.path.join(cache_dir, "interaction_bloom.bin")
        self.bloom = BloomFilter(capacity=500000, error_rate=0.001, filepath=bloom_path)
        logger.info("互动去重器初始化完成")
    
    def check_and_mark(self, post_id: str, action: str) -> bool:
        """
        检查是否已互动并标记
        
        Returns:
            True 如果可以互动, False 如果已互动过
        """
        key = f"{post_id}:{action}"
        return self.bloom.add(key)
    
    def has_interacted(self, post_id: str, action: str = None) -> bool:
        """检查是否已互动"""
        if action:
            key = f"{post_id}:{action}"
            return key in self.bloom
        else:
            return any(f"{post_id}:{a}" in self.bloom for a in ['like', 'collect', 'comment'])
    
    def close(self):
        """关闭"""
        self.bloom.close()
