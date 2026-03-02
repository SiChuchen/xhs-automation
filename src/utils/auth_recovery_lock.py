"""
鉴权恢复锁 - 防止并发恢复的全局锁
使用 diskcache 实现 TTL 防死锁
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

AUTH_RECOVERY_LOCK_KEY = "auth_recovering"
DEFAULT_LOCK_TTL = 300  # 5 minutes


class AuthRecoveryLock:
    """鉴权恢复锁 - 防止多 Worker 并发恢复"""
    
    def __init__(self, cache_dir: str = "data/locks", ttl: int = DEFAULT_LOCK_TTL):
        self.cache_dir = cache_dir
        self.ttl = ttl
        self._cache = None
        self._init_cache()
    
    def _init_cache(self):
        """初始化缓存"""
        try:
            from diskcache import Cache
            os.makedirs(self.cache_dir, exist_ok=True)
            self._cache = Cache(self.cache_dir)
            logger.info(f"鉴权恢复锁初始化: {self.cache_dir}, TTL={self.ttl}s")
        except ImportError:
            logger.warning("diskcache 未安装，使用内存锁")
            self._cache = {}
    
    def try_acquire(self) -> bool:
        """
        尝试获取锁
        
        Returns:
            True: 抢锁成功，负责执行恢复
            False: 已有其他 Worker 在执行恢复
        """
        if self._cache is None:
            self._init_cache()
        
        if isinstance(self._cache, dict):
            return self._memory_try_acquire()
        
        if self._cache.get(AUTH_RECOVERY_LOCK_KEY):
            logger.debug("鉴权恢复锁已被其他 Worker 持有")
            return False
        
        self._cache.set(AUTH_RECOVERY_LOCK_KEY, True, expire=self.ttl)
        logger.info("鉴权恢复锁获取成功")
        return True
    
    def _memory_try_acquire(self) -> bool:
        """内存锁实现（无 diskcache 时备用）"""
        import time
        import threading
        
        if hasattr(self, '_lock_acquired') and self._lock_acquired:
            if time.time() - self._lock_acquired_time < self.ttl:
                return False
        
        self._lock_acquired = True
        self._lock_acquired_time = time.time()
        return True
    
    def release(self):
        """释放锁"""
        if self._cache is None:
            return
        
        if isinstance(self._cache, dict):
            self._memory_release()
            return
        
        try:
            self._cache.delete(AUTH_RECOVERY_LOCK_KEY)
            logger.info("鉴权恢复锁已释放")
        except Exception as e:
            logger.warning(f"释放鉴权恢复锁失败: {e}")
    
    def _memory_release(self):
        """内存锁释放"""
        self._lock_acquired = False
        self._lock_acquired_time = 0
    
    def is_locked(self) -> bool:
        """检查锁状态"""
        if self._cache is None:
            return False
        
        if isinstance(self._cache, dict):
            return getattr(self, '_lock_acquired', False)
        
        return self._cache.get(AUTH_RECOVERY_LOCK_KEY) is not None


_lock_instance: Optional[AuthRecoveryLock] = None


def get_auth_lock() -> AuthRecoveryLock:
    """获取全局鉴权锁实例"""
    global _lock_instance
    if _lock_instance is None:
        _lock_instance = AuthRecoveryLock()
    return _lock_instance
