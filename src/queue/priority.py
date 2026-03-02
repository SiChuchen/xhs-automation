"""
队列优先级调度模块
根据任务类型和时间窗口动态调整队列优先级
"""

import logging
import time
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass

from ..utils.timezone_utils import current_hour, now

logger = logging.getLogger(__name__)


@dataclass
class TimeWindow:
    """时间段配置"""
    name: str
    start_hour: int
    end_hour: int
    slow_priority: int
    fast_priority: int
    action: str  # suspend_publish / suspend_generation / balanced


class QueuePriorityScheduler:
    """队列优先级调度器"""
    
    DEFAULT_WINDOWS = [
        TimeWindow(
            name="night_prefill",
            start_hour=2,
            end_hour=6,
            slow_priority=1,
            fast_priority=10,
            action="suspend_publish"
        ),
        TimeWindow(
            name="evening_peak",
            start_hour=18,
            end_hour=22,
            slow_priority=10,
            fast_priority=1,
            action="suspend_generation"
        ),
        TimeWindow(
            name="daytime",
            start_hour=6,
            end_hour=18,
            slow_priority=5,
            fast_priority=5,
            action="balanced"
        ),
        TimeWindow(
            name="late_night",
            start_hour=22,
            end_hour=2,
            slow_priority=8,
            fast_priority=8,
            action="balanced"
        ),
    ]
    
    def __init__(self, windows: list = None):
        self.windows = windows or self.DEFAULT_WINDOWS
    
    def get_current_window(self) -> TimeWindow:
        """获取当前时间段"""
        current_hour_value = current_hour()
        
        for window in self.windows:
            if window.start_hour > window.end_hour:
                if current_hour_value >= window.start_hour or current_hour_value < window.end_hour:
                    return window
            else:
                if window.start_hour <= current_hour_value < window.end_hour:
                    return window
        
        return TimeWindow("default", 0, 24, 5, 5, "balanced")
    
    def should_suspend_publish(self) -> bool:
        """是否暂停发布"""
        window = self.get_current_window()
        return window.action == "suspend_publish"
    
    def should_suspend_generation(self) -> bool:
        """是否暂停生图"""
        window = self.get_current_window()
        return window.action == "suspend_generation"
    
    def get_queue_priority(self, queue: str) -> int:
        """获取队列优先级"""
        window = self.get_current_window()
        
        if queue == "slow":
            return window.slow_priority
        elif queue == "fast":
            return window.fast_priority
        else:
            return 5
    
    def get_status(self) -> Dict:
        """获取调度状态"""
        window = self.get_current_window()
        return {
            "current_window": window.name,
            "action": window.action,
            "slow_priority": window.slow_priority,
            "fast_priority": window.fast_priority,
            "timestamp": now().isoformat()
        }


class TaskRouter:
    """任务路由器 - 根据任务类型路由到对应队列"""
    
    SLOW_TASKS = {
        'generate_image',
        'llm_long_content',
        'comfyui_workflow',
        'runninghub_generate',
        'batch_generate',
    }
    
    FAST_TASKS = {
        'publish',
        'like',
        'comment',
        'collect',
        'favorite',
        'search',
        'unfavorite',
        'unlike',
    }
    
    def __init__(self, scheduler: QueuePriorityScheduler = None):
        self.scheduler = scheduler or QueuePriorityScheduler()
    
    def route(self, task_type: str, task_params: dict = None) -> str:
        """
        路由任务到队列
        
        Args:
            task_type: 任务类型
            task_params: 任务参数
        
        Returns:
            队列名称 (fast/normal/slow)
        """
        task_type = task_type.lower()
        
        # 检查时间窗口限制
        if task_type in {'publish', 'like', 'comment', 'collect'}:
            if self.scheduler.should_suspend_publish():
                logger.info(f"当前窗口 {self.scheduler.get_current_window().name} 暂停发布任务")
                return "suspended"
        
        if task_type in {'generate_image', 'comfyui_workflow', 'runninghub_generate'}:
            if self.scheduler.should_suspend_generation():
                logger.info(f"当前窗口 {self.scheduler.get_current_window().name} 暂停生图任务")
                return "suspended"
        
        # 正常路由
        if task_type in self.SLOW_TASKS:
            return 'slow'
        elif task_type in self.FAST_TASKS:
            return 'fast'
        else:
            return 'normal'
    
    def get_queue_for_task(self, task_name: str) -> str:
        """根据任务函数名获取队列"""
        name = task_name.lower()
        
        if 'image' in name or 'generate' in name or 'comfyui' in name or 'runninghub' in name:
            return 'slow'
        elif 'publish' in name or 'interact' in name or 'like' in name or 'comment' in name:
            return 'fast'
        else:
            return 'normal'


_global_scheduler = None
_global_router = None


def get_priority_scheduler() -> QueuePriorityScheduler:
    """获取全局优先级调度器"""
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = QueuePriorityScheduler()
    return _global_scheduler


def get_task_router() -> TaskRouter:
    """获取全局任务路由器"""
    global _global_router
    if _global_router is None:
        _global_router = TaskRouter()
    return _global_router
