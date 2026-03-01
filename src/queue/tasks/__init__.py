"""
任务定义 - 自动化运营任务
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from .huey_config import huey, EXPONENTIAL_BACKOFF, PRIORITY_NORMAL

logger = logging.getLogger(__name__)


class TaskStatus:
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"


def retry_with_backoff(task_func):
    """指数退避装饰器"""
    def wrapper(*args, **kwargs):
        max_retries = EXPONENTIAL_BACKOFF["max_retries"]
        intervals = EXPONENTIAL_BACKOFF["intervals"]
        
        for attempt in range(max_retries):
            try:
                return task_func(*args, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = intervals[attempt]
                    logger.warning(f"任务失败，{wait_time}秒后重试 ({attempt+1}/{max_retries}): {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"任务重试次数耗尽: {e}")
                    raise
    return wrapper


# 任务 TTL 配置 (秒)
TASK_TTL = {
    "publish": 86400,      # 发布任务: 24小时
    "interact": 43200,     # 互动任务: 12小时 (时效性强)
    "trending": 3600,     # 热搜任务: 1小时
    "analyze": 7200,      # 分析任务: 2小时
    "cleanup": 3600,      # 清理任务: 1小时
}

# 任务过期检查
def is_task_expired(task_created_at: float, ttl: int) -> bool:
    """检查任务是否已过期"""
    return (time.time() - task_created_at) > ttl


@huey.task(expires=TASK_TTL["publish"])
def publish_note_task(title: str, content: str, image_paths: list = None, 
                      tags: list = None, topic: str = None) -> Dict[str, Any]:
    """
    发布笔记任务
    
    Args:
        title: 标题
        content: 内容
        image_paths: 图片路径列表
        tags: 标签列表
        topic: 话题
    
    Returns:
        {"status": "success", "post_id": "xxx"} 或 {"status": "failure", "error": "xxx"}
    """
    from ..xhs_api_client import XHSClient
    from ..database import get_database
    
    logger.info(f"开始发布笔记: {title}")
    db = get_database()
    
    try:
        client = XHSClient()
        
        # 调用发布 API
        result = client.publish_note(
            title=title,
            content=content,
            image_paths=image_paths or [],
            tags=tags,
            topic=topic
        )
        
        if result.get("success"):
            post_id = result.get("post_id")
            db.add_post(
                title=title,
                content=content,
                image_path=",".join(image_paths) if image_paths else None,
                tags=tags,
                topic=topic,
                post_id=post_id,
                status="success"
            )
            logger.info(f"笔记发布成功: {post_id}")
            return {"status": "success", "post_id": post_id}
        else:
            db.add_post(title=title, content=content, status="failure")
            return {"status": "failure", "error": result.get("error")}
            
    except Exception as e:
        logger.error(f"发布笔记失败: {e}")
        db.add_post(title=title, content=content, status="failure")
        return {"status": "failure", "error": str(e)}


@huey.task(expires=TASK_TTL["interact"])
def auto_interact_task(keywords: list = None, max_likes: int = 10, 
                       max_comments: int = 5, max_collects: int = 5) -> Dict[str, Any]:
    """
    自动互动任务
    
    Args:
        keywords: 关键词列表
        max_likes: 最大点赞数
        max_comments: 最大评论数
        max_collects: 最大收藏数
    
    Returns:
        {"likes": 8, "comments": 3, "collects": 2, "errors": []}
    """
    from ..auto_interact import AutoInteractor
    
    logger.info(f"开始自动互动任务: keywords={keywords}")
    
    try:
        interactor = AutoInteractor()
        results = interactor.run_interactions(
            keywords=keywords,
            max_likes=max_likes,
            max_comments=max_comments,
            max_collects=max_collects
        )
        
        logger.info(f"互动任务完成: {results}")
        return {"status": "success", **results}
        
    except Exception as e:
        logger.error(f"互动任务失败: {e}")
        return {"status": "failure", "error": str(e)}


@huey.task(expires=TASK_TTL["trending"])
def fetch_trending_task(platforms: list = None) -> Dict[str, Any]:
    """
    获取热搜任务
    
    Args:
        platforms: 平台列表 ["weibo", "xiaohongshu"]
    
    Returns:
        {"weibo": [...], "xiaohongshu": [...], "timestamp": "..."}
    """
    from ..trending_fetcher import fetch_all_trending
    
    logger.info(f"开始获取热搜: platforms={platforms}")
    
    try:
        results = fetch_all_trending(platforms=platforms)
        logger.info(f"热搜获取完成: {list(results.keys())}")
        return {"status": "success", **results}
        
    except Exception as e:
        logger.error(f"获取热搜失败: {e}")
        return {"status": "failure", "error": str(e)}


@huey.task(expires=TASK_TTL["analyze"])
def analyze_post_task(post_id: str) -> Dict[str, Any]:
    """
    分析帖子数据任务
    
    Args:
        post_id: 小红书帖子 ID
    
    Returns:
        {"likes": 100, "collects": 20, "comments": 5, "shares": 2}
    """
    from ..xhs_api_client import XHSClient
    from ..database import get_database
    
    logger.info(f"开始分析帖子: {post_id}")
    db = get_database()
    
    try:
        client = XHSClient()
        analytics = client.get_note_stats(post_id)
        
        if analytics:
            db.add_post_analytics(
                post_id=post_id,
                likes=analytics.get("likes", 0),
                collects=analytics.get("collects", 0),
                comments=analytics.get("comments", 0),
                shares=analytics.get("shares", 0)
            )
            logger.info(f"帖子分析完成: {post_id}")
            return {"status": "success", **analytics}
        else:
            return {"status": "failure", "error": "无法获取帖子数据"}
            
    except Exception as e:
        logger.error(f"分析帖子失败: {e}")
        return {"status": "failure", "error": str(e)}


@huey.task(expires=TASK_TTL["cleanup"])
def cleanup_task(retention_days: int = 30) -> Dict[str, Any]:
    """
    清理任务 - 扩展版
    
    Args:
        retention_days: 保留天数
    
    Returns:
        {"deleted": {...}, "storage_freed": "xxx MB"}
    """
    from ..database import get_database
    import os
    import glob
    
    logger.info(f"开始清理任务: retention_days={retention_days}")
    
    deleted = {}
    storage_freed = 0
    
    try:
        db = get_database()
        deleted.update(db.cleanup_old_data(retention_days))
        db.checkpoint()
        
        images_dir = "images"
        if os.path.exists(images_dir):
            freed = cleanup_old_images(images_dir, retention_days=7)
            deleted["old_images"] = freed["count"]
            storage_freed += freed["size"]
        
        logs_dir = "logs"
        if os.path.exists(logs_dir):
            freed = cleanup_old_logs(logs_dir, retention_days=30)
            deleted["old_logs"] = freed["count"]
            storage_freed += freed["size"]
        
        cache_dir = "data/cache"
        if os.path.exists(cache_dir):
            freed = cleanup_cache_files(cache_dir)
            deleted["cache_files"] = freed["count"]
            storage_freed += freed["size"]
        
        logger.info(f"清理完成: {deleted}, 释放空间: {storage_freed} bytes")
        return {"status": "success", "deleted": deleted, "storage_freed": storage_freed}
        
    except Exception as e:
        logger.error(f"清理任务失败: {e}")
        return {"status": "failure", "error": str(e)}


def cleanup_old_images(images_dir: str, retention_days: int = 7) -> Dict:
    """
    清理过期图片
    
    策略: 
    - 删除发布成功超过 7 天的原始图片
    - 保留 _xhs 后缀的处理后图片
    """
    import time
    from pathlib import Path
    
    now = time.time()
    retention_seconds = retention_days * 24 * 3600
    
    count = 0
    freed_size = 0
    
    if not os.path.exists(images_dir):
        return {"count": 0, "size": 0}
    
    for root, dirs, files in os.walk(images_dir):
        for file in files:
            filepath = os.path.join(root, file)
            
            if "_xhs" in file:
                continue
            
            try:
                mtime = os.path.getmtime(filepath)
                if now - mtime > retention_seconds:
                    size = os.path.getsize(filepath)
                    os.remove(filepath)
                    count += 1
                    freed_size += size
            except Exception as e:
                logger.warning(f"删除图片失败: {filepath}, {e}")
    
    logger.info(f"清理过期图片: {count} 个, 释放 {freed_size} bytes")
    return {"count": count, "size": freed_size}


def cleanup_old_logs(logs_dir: str, retention_days: int = 30) -> Dict:
    """清理过期日志文件"""
    import time
    import gzip
    
    now = time.time()
    retention_seconds = retention_days * 24 * 3600
    
    count = 0
    freed_size = 0
    
    if not os.path.exists(logs_dir):
        return {"count": 0, "size": 0}
    
    for root, dirs, files in os.walk(logs_dir):
        for file in files:
            filepath = os.path.join(root, file)
            
            try:
                mtime = os.path.getmtime(filepath)
                if now - mtime > retention_seconds:
                    size = os.path.getsize(filepath)
                    os.remove(filepath)
                    count += 1
                    freed_size += size
            except Exception as e:
                logger.warning(f"删除日志失败: {filepath}, {e}")
    
    logger.info(f"清理过期日志: {count} 个, 释放 {freed_size} bytes")
    return {"count": count, "size": freed_size}


def cleanup_cache_files(cache_dir: str) -> Dict:
    """清理缓存文件 (简单的 LRU)"""
    import time
    
    count = 0
    freed_size = 0
    
    if not os.path.exists(cache_dir):
        return {"count": 0, "size": 0}
    
    files = []
    for f in os.listdir(cache_dir):
        filepath = os.path.join(cache_dir, f)
        if os.path.isfile(filepath):
            files.append((filepath, os.path.getmtime(filepath), os.path.getsize(filepath)))
    
    if len(files) > 1000:
        files.sort(key=lambda x: x[1])
        
        for filepath, mtime, size in files[:-500]:
            try:
                os.remove(filepath)
                count += 1
                freed_size += size
            except Exception as e:
                logger.warning(f"删除缓存失败: {filepath}, {e}")
    
    logger.info(f"清理缓存文件: {count} 个, 释放 {freed_size} bytes")
    return {"count": count, "size": freed_size}


# 定时任务调度
class TaskScheduler:
    """任务调度器"""
    
    @staticmethod
    def schedule_publish(content: Dict[str, Any], delay: int = 0):
        """调度发布任务"""
        if delay > 0:
            import schedule
            schedule.every().day.at("09:00").do(
                publish_note_task.schedule, 
                **(content if isinstance(content, dict) else {"title": content})
            )
        else:
            publish_note_task.schedule(content)
    
    @staticmethod
    def schedule_interaction(interval_hours: int = 6):
        """调度互动任务"""
        auto_interact_task.schedule(args=[], 
                                   kwargs={"max_likes": 15, "max_comments": 10, "max_collects": 5})
    
    @staticmethod
    def schedule_trending_fetch(interval_hours: int = 1):
        """调度热搜获取"""
        fetch_trending_task.schedule()
    
    @staticmethod
    def schedule_cleanup(interval_hours: int = 24):
        """调度清理任务"""
        cleanup_task.schedule(args=[30])
