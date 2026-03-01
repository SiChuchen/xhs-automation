"""
Huey 任务队列配置
使用 SQLite 作为后端存储
支持多队列隔离: fast / normal / slow
"""

import os
from huey import RedisHuey, SqliteHuey, MemoryHuey

# 配置选择
HUEY_BACKEND = os.environ.get("HUEY_BACKEND", "sqlite")

# 队列定义
QUEUES = {
    "fast": "快速任务队列 - MCP交互、评论点赞",
    "normal": "普通任务队列 - 数据处理、内容生成",
    "slow": "慢速任务队列 - RunningHub/ComfyUI生图"
}

# 默认队列
DEFAULT_QUEUE = "normal"

if HUEY_BACKEND == "redis":
    huey = RedisHuey(
        'xhs-automation',
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        password=os.environ.get("REDIS_PASSWORD"),
    )
elif HUEY_BACKEND == "sqlite":
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                          "data", "huey.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    huey = SqliteHuey(filename=db_path)
else:
    huey = MemoryHuey()

# 任务配置
HUEY_CONFIG = {
    "immediate": HUEY_BACKEND == "memory",
    "utc": True,
    "always_eager": os.environ.get("HUEY_EAGER", "false").lower() == "true",
}

# 指数退避配置
EXPONENTIAL_BACKOFF = {
    "max_retries": 5,
    "intervals": [60, 180, 600, 1800, 3600],  # 1m, 3m, 10m, 30m, 1h
}

# 任务优先级 (数值越小优先级越高)
PRIORITY_HIGH = 1
PRIORITY_NORMAL = 5
PRIORITY_LOW = 10


def get_queue(name: str = DEFAULT_QUEUE):
    """
    获取指定队列的 Huey 实例
    
    Args:
        name: 队列名称 (fast/normal/slow)
    
    Returns:
        Huey instance
    """
    if name not in QUEUES:
        name = DEFAULT_QUEUE
    return huey


def route_task(task_type: str) -> str:
    """
    根据任务类型路由到对应队列
    
    Args:
        task_type: 任务类型
    
    Returns:
        队列名称
    """
    slow_tasks = {
        'generate_image',
        'llm_long_content',
        'comfyui_workflow',
        'runninghub_generate'
    }
    
    fast_tasks = {
        'publish',
        'like',
        'comment',
        'collect',
        'favorite',
        'search',
        'alert',
        'health_check'
    }
    
    if task_type in slow_tasks:
        return 'slow'
    elif task_type in fast_tasks:
        return 'fast'
    else:
        return 'normal'


# 便捷的任务装饰器
def fast_task(*args, **kwargs):
    """快速任务装饰器 - 用于 MCP 交互类任务"""
    return huey.task(*args, queue='fast', **kwargs)

def normal_task(*args, **kwargs):
    """普通任务装饰器 - 用于一般任务"""
    return huey.task(*args, queue='normal', **kwargs)

def slow_task(*args, **kwargs):
    """慢速任务装饰器 - 用于生图等耗时任务"""
    return huey.task(*args, queue='slow', **kwargs)
