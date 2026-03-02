"""
小红书自动化运营核心模块
"""

# Database
from .database import XHSDatabase, get_database

# MCP Client (官方推荐协议)
from .mcp_client import XHSMCPClient, get_mcp_client

# Cache
from .cache.cache_manager import CacheManager, get_cache_manager
from .cache.bloom_filter import BloomFilter, InteractionDeduplicator

# Queue (import carefully to avoid circular imports)
# from .queue.huey_config import huey

# Processes
# from .main_process import MainProcess
# from .worker_process import WorkerProcess

__all__ = [
    # Database
    'XHSDatabase',
    'get_database',
    # MCP Client (官方推荐协议)
    'XHSMCPClient',
    'get_mcp_client',
    # Auto Interaction
    'AutoInteract',
    'run_auto_interact',
    # Cache
    'CacheManager',
    'get_cache_manager',
    'BloomFilter',
    'InteractionDeduplicator',
    # Queue
    'huey',
    # Processes
    'MainProcess',
    'WorkerProcess',
]
