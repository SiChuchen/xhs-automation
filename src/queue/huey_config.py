"""
Huey 任务队列配置
使用 SQLite 作为后端存储
"""

import os
from huey import RedisHuey, SqliteHuey, MemoryHuey

# 配置选择
# 使用 SQLite 作为后端 (推荐，用于无 Redis 环境)
# 使用 Redis 作为后端 (需要额外服务)
# 使用 MemoryHuey 用于测试

HUEY_BACKEND = os.environ.get("HUEY_BACKEND", "sqlite")

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

# 任务优先级
PRIORITY_HIGH = 1
PRIORITY_NORMAL = 5
PRIORITY_LOW = 10
