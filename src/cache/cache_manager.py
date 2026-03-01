"""
缓存管理器 - 使用 diskcache
"""

import os
import logging
from typing import Any, Optional
from datetime import timedelta

logger = logging.getLogger(__name__)

try:
    from diskcache import Cache
    DISKCACHE_AVAILABLE = True
except ImportError:
    DISKCACHE_AVAILABLE = False
    logger.warning("diskcache 未安装，将使用简单内存缓存")


class SimpleMemoryCache:
    """简单内存缓存 (diskcache 不可用时的降级方案)"""
    
    def __init__(self, *args, **kwargs):
        self._cache = {}
    
    def get(self, key, default=None):
        return self._cache.get(key, default)
    
    def set(self, key, value, expire=None):
        self._cache[key] = value
    
    def delete(self, key):
        self._cache.pop(key, None)
    
    def clear(self):
        self._cache.clear()
    
    def exists(self, key):
        return key in self._cache
    
    def close(self):
        pass


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, cache_dir: str = "data/cache", size_limit: int = 1073741824):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录
            size_limit: 最大缓存大小 (bytes), 默认 1GB
        """
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_dir = cache_dir
        
        if DISKCACHE_AVAILABLE:
            self.cache = Cache(cache_dir, size_limit=size_limit)
            logger.info(f"缓存管理器初始化 (diskcache): {cache_dir}")
        else:
            self.cache = SimpleMemoryCache()
            logger.warning("使用简单内存缓存 (diskcache 未安装)")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存"""
        try:
            return self.cache.get(key, default)
        except Exception as e:
            logger.warning(f"缓存获取失败: {e}")
            return default
    
    def set(self, key: str, value: Any, expire: Optional[int] = None):
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            expire: 过期时间(秒)
        """
        try:
            if expire:
                from diskcache import ETAG_RE
                self.cache.set(key, value, expire=expire)
            else:
                self.cache.set(key, value)
        except Exception as e:
            logger.warning(f"缓存设置失败: {e}")
    
    def delete(self, key: str):
        """删除缓存"""
        try:
            self.cache.delete(key)
        except Exception as e:
            logger.warning(f"缓存删除失败: {e}")
    
    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            return self.cache.exists(key)
        except Exception as e:
            return False
    
    def clear(self):
        """清空缓存"""
        try:
            self.cache.clear()
            logger.info("缓存已清空")
        except Exception as e:
            logger.warning(f"清空缓存失败: {e}")
    
    def close(self):
        """关闭缓存"""
        try:
            self.cache.close()
        except Exception:
            pass


class SearchCacheManager:
    """搜索结果缓存管理器"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.default_ttl = 3600 * 6  # 6小时
    
    def _make_key(self, keyword: str, platform: str = "xiaohongshu") -> str:
        return f"search:{platform}:{keyword}"
    
    def get_search_results(self, keyword: str, platform: str = "xiaohongshu") -> Optional[list]:
        """获取缓存的搜索结果"""
        key = self._make_key(keyword, platform)
        return self.cache.get(key)
    
    def set_search_results(self, keyword: str, results: list, platform: str = "xiaohongshu", ttl: Optional[int] = None):
        """缓存搜索结果"""
        key = self._make_key(keyword, platform)
        self.cache.set(key, results, ttl or self.default_ttl)
    
    def invalidate_search(self, keyword: str, platform: str = "xiaohongshu"):
        """使搜索缓存失效"""
        key = self._make_key(keyword, platform)
        self.cache.delete(key)


class TrendingCacheManager:
    """热搜缓存管理器"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.ttl = 1800  # 30分钟
    
    def _make_key(self, platform: str) -> str:
        return f"trending:{platform}"
    
    def get_trending(self, platform: str) -> Optional[list]:
        """获取缓存的热搜"""
        key = self._make_key(platform)
        return self.cache.get(key)
    
    def set_trending(self, platform: str, topics: list):
        """缓存热搜"""
        key = self._make_key(platform)
        self.cache.set(key, topics, self.ttl)


_global_cache_manager = None

def get_cache_manager(cache_dir: str = "data/cache") -> CacheManager:
    """获取全局缓存管理器"""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = CacheManager(cache_dir)
    return _global_cache_manager
