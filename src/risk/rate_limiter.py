"""
令牌桶限流器 - 外部 API 调用限流
防止触发上游 Rate Limit 和成本失控
"""

import os
import time
import logging
import threading
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """限流配置"""
    max_tokens_per_day: int = 10000
    max_calls_per_minute: int = 60
    max_calls_per_hour: int = 1000
    burst_size: int = 10


@dataclass
class TokenBucket:
    """令牌桶"""
    capacity: int
    refill_rate: float
    tokens: float = field(default=0)
    last_refill: float = field(default_factory=time.time)


class TokenBucketRateLimiter:
    """令牌桶限流器"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.daily_tokens_used = 0
        self.daily_tokens_reset = self._get_next_reset()
        
        self.minute_calls: Dict[int, int] = {}
        self.hourly_calls: Dict[int, int] = {}
        
        self.bucket = TokenBucket(
            capacity=config.burst_size,
            refill_rate=config.max_calls_per_minute / 60.0,
            tokens=config.burst_size  # 初始满令牌
        )
        
        self._lock = threading.Lock()
    
    def _get_next_reset(self) -> datetime:
        """获取次日零点"""
        now = datetime.now()
        return datetime(now.year, now.month, now.day) + timedelta(days=1)
    
    def _refill_bucket(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self.bucket.last_refill
        new_tokens = elapsed * self.bucket.refill_rate
        
        self.bucket.tokens = min(
            self.bucket.capacity,
            self.bucket.tokens + new_tokens
        )
        self.bucket.last_refill = now
    
    def _cleanup_old_counts(self):
        """清理过期的计数"""
        now = datetime.now()
        current_minute = now.minute + now.hour * 60
        current_hour = now.hour
        
        self.minute_calls = {
            k: v for k, v in self.minute_calls.items()
            if k >= current_minute - 1
        }
        
        self.hourly_calls = {
            k: v for k, v in self.hourly_calls.items()
            if k >= current_hour - 1
        }
    
    def _check_daily_limit(self) -> bool:
        """检查每日限额"""
        if datetime.now() >= self.daily_tokens_reset:
            self.daily_tokens_used = 0
            self.daily_tokens_reset = self._get_next_reset()
        
        return self.daily_tokens_used < self.config.max_tokens_per_day
    
    def acquire(self, tokens: int = 1) -> tuple[bool, str]:
        """
        获取令牌
        
        Args:
            tokens: 需要的令牌数
        
        Returns:
            (是否允许, 原因)
        """
        with self._lock:
            # 检查每日限额
            if not self._check_daily_limit():
                return False, f"已达每日限额 ({self.config.max_tokens_per_day})"
            
            # 补充令牌
            self._refill_bucket()
            
            # 检查令牌是否足够
            if self.bucket.tokens < tokens:
                wait_time = (tokens - self.bucket.tokens) / self.bucket.refill_rate
                return False, f"令牌不足，需等待 {wait_time:.1f} 秒"
            
            # 消费令牌
            self.bucket.tokens -= tokens
            self.daily_tokens_used += tokens
            
            # 记录调用
            self._cleanup_old_counts()
            now = datetime.now()
            minute_key = now.minute + now.hour * 60
            hour_key = now.hour
            
            self.minute_calls[minute_key] = self.minute_calls.get(minute_key, 0) + 1
            self.hourly_calls[hour_key] = self.hourly_calls.get(hour_key, 0) + 1
            
            return True, ""
    
    def can_call(self) -> tuple[bool, str]:
        """检查是否可以调用"""
        self._cleanup_old_counts()
        
        now = datetime.now()
        minute_key = now.minute + now.hour * 60
        hour_key = now.hour
        
        # 检查每分钟限制
        if self.minute_calls.get(minute_key, 0) >= self.config.max_calls_per_minute:
            return False, f"已达每分钟调用上限 ({self.config.max_calls_per_minute})"
        
        # 检查每小时限制
        if self.hourly_calls.get(hour_key, 0) >= self.config.max_calls_per_hour:
            return False, f"已达每小时调用上限 ({self.config.max_calls_per_hour})"
        
        return self.acquire()
    
    def record_success(self, tokens: int = 1):
        """记录成功调用"""
        pass
    
    def record_failure(self, tokens: int = 1):
        """记录失败调用 (不消耗令牌)"""
        pass
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "daily_tokens": {
                "used": self.daily_tokens_used,
                "limit": self.config.max_tokens_per_day,
                "remaining": self.config.max_tokens_per_day - self.daily_tokens_used
            },
            "current_minute_calls": self.minute_calls.get(
                datetime.now().minute + datetime.now().hour * 60, 0
            ),
            "current_hour_calls": self.hourly_calls.get(datetime.now().hour, 0),
            "bucket_tokens": self.bucket.tokens
        }


class MultiAPIRateLimiter:
    """多 API 限流管理器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.limiters: Dict[str, TokenBucketRateLimiter] = {}
        self._load_configs()
    
    def _load_configs(self):
        """加载配置"""
        configs = {
            "openai": RateLimitConfig(
                max_tokens_per_day=50000,
                max_calls_per_minute=60,
                max_calls_per_hour=1000,
                burst_size=10
            ),
            "deepseek": RateLimitConfig(
                max_tokens_per_day=100000,
                max_calls_per_minute=120,
                max_calls_per_hour=2000,
                burst_size=20
            ),
            "runninghub": RateLimitConfig(
                max_tokens_per_day=500,
                max_calls_per_minute=10,
                max_calls_per_hour=100,
                burst_size=5
            ),
            "minimax": RateLimitConfig(
                max_tokens_per_day=100000,
                max_calls_per_minute=60,
                max_calls_per_hour=1000,
                burst_size=10
            )
        }
        
        for name, config in configs.items():
            self.limiters[name] = TokenBucketRateLimiter(config)
        
        logger.info(f"已加载 {len(configs)} 个 API 限流配置")
    
    def acquire(self, api_name: str, tokens: int = 1) -> tuple[bool, str]:
        """获取指定 API 的令牌"""
        if api_name not in self.limiters:
            logger.warning(f"未知 API: {api_name}，允许通过")
            return True, ""
        
        return self.limiters[api_name].acquire(tokens)
    
    def can_call(self, api_name: str) -> tuple[bool, str]:
        """检查是否可以调用指定 API"""
        if api_name not in self.limiters:
            return True, ""
        
        return self.limiters[api_name].can_call()
    
    def get_status(self, api_name: str) -> Dict:
        """获取 API 限流状态"""
        if api_name not in self.limiters:
            return {}
        return self.limiters[api_name].get_status()
    
    def get_all_status(self) -> Dict:
        """获取所有 API 限流状态"""
        return {
            api_name: limiter.get_status()
            for api_name, limiter in self.limiters.items()
        }


_global_limiter = None

def get_rate_limiter(config_dir: str = "config") -> MultiAPIRateLimiter:
    """获取全局限流器"""
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = MultiAPIRateLimiter(config_dir)
    return _global_limiter
