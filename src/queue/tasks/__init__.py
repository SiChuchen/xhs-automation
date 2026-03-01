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


@huey.task()
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


@huey.task()
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


@huey.task()
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


@huey.task()
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


@huey.task()
def cleanup_task(retention_days: int = 30) -> Dict[str, Any]:
    """
    清理任务
    
    Args:
        retention_days: 保留天数
    
    Returns:
        {"deleted": {"interactions": 100, "analytics": 50, "cache": 20}}
    """
    from ..database import get_database
    
    logger.info(f"开始清理任务: retention_days={retention_days}")
    
    try:
        db = get_database()
        deleted = db.cleanup_old_data(retention_days)
        db.checkpoint()
        
        logger.info(f"清理完成: {deleted}")
        return {"status": "success", "deleted": deleted}
        
    except Exception as e:
        logger.error(f"清理任务失败: {e}")
        return {"status": "failure", "error": str(e)}


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
