"""
频率控制器 - 智能调控互动频率
根据账号权重动态调整
"""

import time
import logging
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class ActionLimit:
    """动作限制配置"""
    max_daily: int = 20
    max_hourly: int = 5
    min_interval: float = 10.0
    max_interval: float = 60.0


@dataclass
class AccountProfile:
    """账号画像"""
    weight: float = 1.0
    daily_limits: Dict[str, ActionLimit] = field(default_factory=lambda: {
        "like": ActionLimit(max_daily=20, max_hourly=5),
        "collect": ActionLimit(max_daily=10, max_hourly=3),
        "comment": ActionLimit(max_daily=10, max_hourly=3),
    })
    risk_level: str = "normal"


class FrequencyController:
    """频率控制器"""
    
    DEFAULT_LIMITS = {
        "like": ActionLimit(max_daily=20, max_hourly=5, min_interval=10, max_interval=60),
        "collect": ActionLimit(max_daily=10, max_hourly=3, min_interval=30, max_interval=120),
        "comment": ActionLimit(max_daily=10, max_hourly=3, min_interval=60, max_interval=180),
    }
    
    def __init__(self, account_profile: Optional[AccountProfile] = None):
        self.account_profile = account_profile or AccountProfile()
        self.action_history: Dict[str, deque] = {
            action: deque(maxlen=1000) for action in ["like", "collect", "comment"]
        }
        self.last_action_time: Dict[str, float] = {}
    
    def can_perform_action(self, action: str) -> tuple[bool, str]:
        """
        检查是否可以执行动作
        
        Returns:
            (是否允许, 原因)
        """
        if action not in self.action_history:
            return True, ""
        
        limits = self._get_limits(action)
        now = time.time()
        today = datetime.now().date()
        
        # 检查每日限制
        today_count = sum(
            1 for t in self.action_history[action]
            if datetime.fromtimestamp(t).date() == today
        )
        
        if today_count >= limits.max_daily:
            return False, f"已达每日上限 ({limits.max_daily})"
        
        # 检查每小时限制
        hour_ago = now - 3600
        hour_count = sum(1 for t in self.action_history[action] if t > hour_ago)
        
        if hour_count >= limits.max_hourly:
            return False, f"已达每小时上限 ({limits.max_hourly})"
        
        # 检查间隔时间
        if action in self.last_action_time:
            elapsed = now - self.last_action_time[action]
            if elapsed < limits.min_interval:
                wait_time = limits.min_interval - elapsed
                return False, f"需等待 {wait_time:.1f} 秒"
        
        return True, ""
    
    def record_action(self, action: str):
        """记录动作"""
        now = time.time()
        self.action_history[action].append(now)
        self.last_action_time[action] = now
        
        logger.debug(f"记录动作: {action}")
    
    def get_wait_time(self, action: str) -> float:
        """获取建议等待时间"""
        limits = self._get_limits(action)
        
        if action in self.last_action_time:
            elapsed = time.time() - self.last_action_time[action]
            return max(0, limits.min_interval - elapsed)
        
        return 0
    
    def get_random_interval(self, action: str) -> float:
        """获取随机间隔时间"""
        limits = self._get_limits(action)
        import random
        return random.uniform(limits.min_interval, limits.max_interval)
    
    def _get_limits(self, action: str) -> ActionLimit:
        """获取动作限制"""
        profile_limits = self.account_profile.daily_limits.get(action)
        if profile_limits:
            return profile_limits
        return self.DEFAULT_LIMITS.get(action, ActionLimit())
    
    def get_status(self) -> Dict:
        """获取当前状态"""
        today = datetime.now().date()
        status = {}
        
        for action in self.action_history:
            today_count = sum(
                1 for t in self.action_history[action]
                if datetime.fromtimestamp(t).date() == today
            )
            limits = self._get_limits(action)
            
            status[action] = {
                "today_count": today_count,
                "daily_limit": limits.max_daily,
                "last_action": datetime.fromtimestamp(self.last_action_time[action]).isoformat() 
                              if action in self.last_action_time else None,
            }
        
        return status


class AdaptiveFrequencyController(FrequencyController):
    """自适应频率控制器"""
    
    def __init__(self, account_profile: Optional[AccountProfile] = None):
        super().__init__(account_profile)
        self.failure_count = 0
        self.success_count = 0
        self.cooldown_until: float = 0
    
    def record_success(self):
        """记录成功"""
        self.success_count += 1
        self.failure_count = 0
    
    def record_failure(self):
        """记录失败"""
        self.failure_count += 1
        self.success_count = 0
        
        # 连续失败3次，进入冷却
        if self.failure_count >= 3:
            self.cooldown_until = time.time() + 300  # 5分钟冷却
            logger.warning("连续失败3次，进入冷却模式")
    
    def can_perform_action(self, action: str) -> tuple[bool, str]:
        """检查是否可以执行动作 (带冷却)"""
        # 检查冷却时间
        if time.time() < self.cooldown_until:
            wait = self.cooldown_until - time.time()
            return False, f"冷却中，还需等待 {wait:.0f} 秒"
        
        return super().can_perform_action(action)
    
    def adjust_limits(self, risk_multiplier: float):
        """根据风险调整限制"""
        for action, limits in self.DEFAULT_LIMITS.items():
            limits.max_daily = int(limits.max_daily * risk_multiplier)
            limits.max_hourly = int(limits.max_hourly * risk_multiplier)
        
        logger.info(f"调整频率限制: multiplier={risk_multiplier}")


def get_frequency_controller(account_weight: float = 1.0) -> AdaptiveFrequencyController:
    """获取频率控制器"""
    profile = AccountProfile(weight=account_weight)
    return AdaptiveFrequencyController(profile)
