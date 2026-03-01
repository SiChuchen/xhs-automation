"""
异常检测器 + 熔断器
支持状态持久化
"""

import os
import json
import time
import logging
from typing import Dict, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AnomalyEvent:
    """异常事件"""
    event_type: str
    level: AlertLevel
    message: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


class CircuitState(Enum):
    """熔断状态"""
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断中
    HALF_OPEN = "half_open"  # 半开


class CircuitBreaker:
    """熔断器 (支持持久化)"""
    
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 2,
        state_file: Optional[str] = None,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.state_file = state_file
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
        
        # 启动时恢复状态
        if state_file and os.path.exists(state_file):
            self._load_state()
    
    def _get_state_data(self) -> Dict:
        """获取状态数据"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "half_open_calls": self.half_open_calls,
        }
    
    def _load_state(self):
        """从文件加载状态"""
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
            
            self.state = CircuitState(data.get("state", "closed"))
            self.failure_count = data.get("failure_count", 0)
            self.last_failure_time = data.get("last_failure_time", 0)
            self.half_open_calls = data.get("half_open_calls", 0)
            
            # 如果在熔断中，检查是否已过恢复时间
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    logger.info("熔断器从持久化恢复，进入半开状态")
                else:
                    logger.info(f"熔断器从持久化恢复，仍处于开启状态")
            
            logger.info(f"熔断器状态已恢复: {self.state.value}")
        except Exception as e:
            logger.warning(f"加载熔断器状态失败: {e}")
    
    def _save_state(self):
        """保存状态到文件"""
        if not self.state_file:
            return
        
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self._get_state_data(), f)
        except Exception as e:
            logger.warning(f"保存熔断器状态失败: {e}")
    
    def call(self, func: Callable, *args, **kwargs):
        """执行函数 (带熔断)"""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                logger.info("熔断器进入半开状态")
            else:
                raise Exception("熔断器已开启")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """成功回调"""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("熔断器关闭，恢复正常")
        else:
            self.failure_count = 0
        
        self._save_state()
    
    def _on_failure(self):
        """失败回调"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("半开状态失败，重新开启熔断")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"熔断器开启 (连续{self.failure_count}次失败)")
        
        self._save_state()
    
    def get_state(self) -> str:
        """获取状态"""
        return self.state.value


class AnomalyDetector:
    """异常检测器"""
    
    def __init__(self, callback: Optional[Callable] = None, state_dir: str = "data/risk"):
        self.callback = callback
        self.events: deque = deque(maxlen=100)
        self.state_dir = state_dir
        
        self.auth_failures = 0
        self.rate_limit_triggers = 0
        self.api_errors = 0
        
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # 确保目录存在
        os.makedirs(state_dir, exist_ok=True)
    
    def record_event(self, event: AnomalyEvent):
        """记录异常事件"""
        self.events.append(event)
        
        if event.level == AlertLevel.ERROR:
            if "auth" in event.event_type.lower():
                self.auth_failures += 1
            elif "rate_limit" in event.event_type.lower():
                self.rate_limit_triggers += 1
            elif "api" in event.event_type.lower():
                self.api_errors += 1
        
        logger.warning(f"异常事件: {event.event_type} - {event.message}")
        
        if self.callback:
            self.callback(event)
    
    def check_auth_failure(self) -> bool:
        """检查是否需要告警 (连续3次鉴权失败)"""
        recent_auth_failures = sum(
            1 for e in self.events
            if "auth" in e.event_type.lower() 
            and time.time() - e.timestamp < 300  # 5分钟内
        )
        
        if recent_auth_failures >= 3:
            self.record_event(AnomalyEvent(
                event_type="auth_failure_alert",
                level=AlertLevel.CRITICAL,
                message=f"连续 {recent_auth_failures} 次鉴权失败，Cookie 可能已失效",
                metadata={"count": recent_auth_failures}
            ))
            return True
        return False
    
    def check_rate_limit(self) -> bool:
        """检查是否触发限流"""
        recent_limits = sum(
            1 for e in self.events
            if "rate_limit" in e.event_type.lower()
            and time.time() - e.timestamp < 600  # 10分钟内
        )
        
        if recent_limits >= 3:
            self.record_event(AnomalyEvent(
                event_type="rate_limit_alert",
                level=AlertLevel.ERROR,
                message=f"10分钟内触发 {recent_limits} 次限流，建议降级",
                metadata={"count": recent_limits}
            ))
            return True
        return False
    
    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """获取熔断器"""
        if name not in self.circuit_breakers:
            state_file = os.path.join(self.state_dir, f"circuit_{name}.json")
            self.circuit_breakers[name] = CircuitBreaker(state_file=state_file)
        return self.circuit_breakers[name]
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "circuit_breakers": {
                name: cb.get_state() 
                for name, cb in self.circuit_breakers.items()
            },
            "recent_events": len(self.events),
            "auth_failures": self.auth_failures,
            "rate_limit_triggers": self.rate_limit_triggers,
            "api_errors": self.api_errors,
        }
    
    def reset(self):
        """重置"""
        self.auth_failures = 0
        self.rate_limit_triggers = 0
        self.api_errors = 0
        self.events.clear()
        for cb in self.circuit_breakers.values():
            cb.state = CircuitState.CLOSED
            cb.failure_count = 0


def get_anomaly_detector(callback: Optional[Callable] = None) -> AnomalyDetector:
    """获取异常检测器"""
    return AnomalyDetector(callback)
