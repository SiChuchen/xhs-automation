"""
任务定义 - 自动化运营任务
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from ..huey_config import huey, EXPONENTIAL_BACKOFF, PRIORITY_NORMAL, slow_task
from huey import crontab

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


@huey.task(expires=TASK_TTL["publish"], queue="fast")
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
    from ..utils.task_state_machine import get_post_state_machine
    
    logger.info(f"开始发布笔记: {title}")
    db = get_database()
    sm = get_post_state_machine()
    
    try:
        # 1. 先添加待发布的 post 记录 (pending 状态)
        post_id = db.add_post(
            title=title,
            content=content,
            image_path=",".join(image_paths) if image_paths else None,
            tags=tags,
            topic=topic,
            status="pending"
        )
        
        # 2. 尝试抢占任务 (乐观锁 + TTL 防死锁)
        claim_result = sm.claim_post(post_id, timeout_minutes=15)
        
        if not claim_result.success:
            logger.warning(f"无法抢占发布任务: post_id={post_id}, reason={claim_result.reason}")
            return {
                "status": "failure", 
                "error": f"task_already_{claim_result.reason}",
                "post_id": post_id
            }
        
        # 3. 抢占成功，执行发布
        client = XHSClient()
        result = client.publish_note(
            title=title,
            content=content,
            image_paths=image_paths or [],
            tags=tags,
            topic=topic
        )
        
        if result.get("success"):
            xhs_post_id = result.get("post_id")
            db.update_post_status(post_id, "success", xhs_post_id)
            sm.complete_post(post_id)
            logger.info(f"笔记发布成功: {xhs_post_id}")
            return {"status": "success", "post_id": xhs_post_id}
        else:
            error_msg = result.get("error", "unknown")
            db.update_post_status(post_id, "failed")
            sm.fail_post(post_id, error_msg)
            return {"status": "failure", "error": error_msg}
            
    except Exception as e:
        logger.error(f"发布笔记失败: {e}")
        try:
            if 'post_id' in locals():
                sm.fail_post(post_id, str(e))
                db.update_post_status(post_id, "failed")
        except:
            pass
        return {"status": "failure", "error": str(e)}


@huey.task(expires=TASK_TTL["interact"], queue="fast")
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


@huey.task(expires=TASK_TTL["trending"], queue="normal")
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


@huey.task(expires=TASK_TTL["analyze"], queue="normal")
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


@huey.task(expires=TASK_TTL["cleanup"], queue="normal")
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


@huey.periodic_task(crontab(hour=3, minute=0))
def db_maintenance_task() -> Dict[str, Any]:
    """
    数据库维护任务 - 每天凌晨 3 点执行
    
    执行:
    - VACUUM 整理数据库碎片
    - PRAGMA wal_checkpoint(TRUNCATE) 清理 WAL 日志
    """
    from ..database import get_database
    
    logger.info("开始数据库维护任务")
    
    try:
        db = get_database()
        
        db.checkpoint()
        
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        
        cursor.execute("VACUUM")
        logger.info("VACUUM 执行完成")
        
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        logger.info("WAL checkpoint 执行完成")
        
        conn.close()
        
        db_size = db.get_db_size()
        
        logger.info(f"数据库维护完成, 当前大小: {db_size} bytes")
        return {"status": "success", "db_size": db_size}
        
    except Exception as e:
        logger.error(f"数据库维护任务失败: {e}")
        return {"status": "failure", "error": str(e)}


@slow_task(expires=7200)
def poll_comfyui_task(
    prompt_id: str,
    workflow_type: str = "comfyui",
    callback_task_id: int = None,
    poll_interval: int = 60,
    current_retry: int = 0,
    max_retries: int = 10
) -> Dict[str, Any]:
    """
    异步轮询 ComfyUI/RunningHub 任务状态
    
    任务链:
    1. 提交生图任务，获取 prompt_id
    2. 立即返回，释放 Worker
    3. 调度 poll_comfyui_task 延迟 60s 执行
    4. 检查状态:
       - 未完成: 再次入队延迟 60s
       - 完成: 触发下游图片处理
       - 失败: 记录错误
    
    Args:
        prompt_id: 任务ID
        workflow_type: 工作流类型 (comfyui/runninghub)
        callback_task_id: 回调任务ID
        poll_interval: 轮询间隔(秒)
        current_retry: 当前重试次数
        max_retries: 最大重试次数
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    
    from src.utils.comfyui_workflow import ComfyUIWorkflow, RunningHubWorkflow
    
    logger.info(f"轮询任务状态: prompt_id={prompt_id}, retry={current_retry}/{max_retries}")
    
    try:
        if workflow_type == "runninghub":
            workflow = RunningHubWorkflow()
        else:
            workflow = ComfyUIWorkflow()
        
        result = workflow.check_and_poll(
            prompt_id=prompt_id,
            callback_task_id=callback_task_id,
            poll_interval=poll_interval,
            current_retry=current_retry,
            max_retries=max_retries
        )
        
        if result["status"] == "completed":
            logger.info(f"任务完成: {prompt_id}")
            if callback_task_id:
                logger.info(f"触发回调任务: {callback_task_id}")
            return {"status": "completed", "result": result.get("result")}
        
        if result["status"] == "errored":
            logger.error(f"任务失败: {prompt_id}, error: {result.get('error')}")
            return {"status": "errored", "error": result.get("error")}
        
        if result.get("needs_reschedule"):
            next_retry = result.get("retry_count", current_retry + 1)
            logger.info(f"任务进行中，调度下一次轮询: {prompt_id}, next_retry={next_retry}")
            
            poll_comfyui_task.schedule(
                args=(prompt_id,),
                kwargs={
                    "workflow_type": workflow_type,
                    "callback_task_id": callback_task_id,
                    "poll_interval": poll_interval,
                    "current_retry": next_retry,
                    "max_retries": max_retries
                },
                delay=poll_interval
            )
            return {"status": "rescheduled", "next_retry": next_retry}
        
        return {"status": "max_retries_exceeded", "prompt_id": prompt_id}
    
    except Exception as e:
        logger.error(f"轮询任务异常: {e}")
        return {"status": "error", "error": str(e)}


@slow_task(expires=3600)
def submit_and_poll_image_task(
    workflow_params: Dict,
    workflow_type: str = "comfyui",
    image_callback_task_id: int = None,
    poll_interval: int = 60,
    max_retries: int = 10
) -> Dict[str, Any]:
    """
    提交生图任务并调度轮询（两步任务链）
    
    Step 1: 提交任务，获取 prompt_id
    Step 2: 调度 poll_comfyui_task 异步查询
    
    Args:
        workflow_params: 工作流参数字典
        workflow_type: 工作流类型
        image_callback_task_id: 图片处理完成后的回调任务ID
        poll_interval: 轮询间隔
        max_retries: 最大轮询次数
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    
    from src.utils.comfyui_workflow import ComfyUIWorkflow, RunningHubWorkflow
    
    logger.info(f"提交生图任务: workflow_type={workflow_type}")
    
    try:
        if workflow_type == "runninghub":
            workflow = RunningHubWorkflow()
        else:
            workflow = ComfyUIWorkflow()
        
        result = workflow.execute_and_schedule_poll(
            prompt=workflow_params,
            callback_task_id=image_callback_task_id,
            poll_interval=poll_interval,
            max_retries=max_retries
        )
        
        prompt_id = result["prompt_id"]
        logger.info(f"生图任务已提交: {prompt_id}, 调度轮询")
        
        poll_comfyui_task.schedule(
            args=(prompt_id,),
            kwargs={
                "workflow_type": workflow_type,
                "callback_task_id": image_callback_task_id,
                "poll_interval": poll_interval,
                "current_retry": 0,
                "max_retries": max_retries
            },
            delay=poll_interval
        )
        
        return {"status": "submitted", "prompt_id": prompt_id}
    
    except Exception as e:
        logger.error(f"提交生图任务失败: {e}")
        return {"status": "error", "error": str(e)}


def schedule_with_jitter(task_func, base_interval: int, jitter: int = 300):
    """
    带随机延迟的任务调度
    
    Args:
        task_func: 任务函数
        base_interval: 基础间隔(秒)
        jitter: 随机延迟范围(秒)
    """
    import random
    delay = base_interval + random.randint(0, jitter)
    return task_func.schedule(delay=delay)


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


@huey.periodic_task(crontab(hour=4, minute=0))
def db_backup_task() -> Dict[str, Any]:
    """
    数据库备份任务 - 每天凌晨 4 点执行
    
    1. 在线备份 SQLite 数据库
    2. 清理超过 7 天的旧备份
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    
    from src.database import get_database
    
    logger.info("开始数据库备份任务")
    
    try:
        db = get_database()
        result = db.backup_database(backup_dir="data/backups", retention_days=7)
        
        if "error" in result:
            logger.error(f"数据库备份失败: {result['error']}")
            return {"status": "failure", "error": result["error"]}
        
        logger.info(f"数据库备份完成: {result['backup_path']}, 清理旧备份: {result['cleaned']} 个")
        return {"status": "success", **result}
    
    except Exception as e:
        logger.error(f"数据库备份任务异常: {e}")
        return {"status": "error", "error": str(e)}


@huey.periodic_task(crontab(hour=9, minute=0))
def dlq_alert_task() -> Dict[str, Any]:
    """
    死信队列每日告警任务 - 每天早上 9 点执行
    
    检查过去 24 小时的失败任务，推送汇总告警到飞书
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    
    from src.database import get_database
    from src.integrations.feishu_client import send_message
    
    logger.info("开始死信队列告警任务")
    
    try:
        db = get_database()
        summary = db.get_failed_task_summary(hours=24)
        
        if summary["total"] == 0:
            logger.info("过去 24 小时无失败任务")
            return {"status": "success", "message": "no failed tasks"}
        
        task_lines = []
        for item in summary["by_task"]:
            task_lines.append(f"- {item['task_name']}: {item['count']} 次")
        
        message = f"""## 🔴 死信队列告警

过去 24 小时共有 **{summary['total']}** 个任务失败，其中 **{summary['unresolved']}** 个未解决:

{chr(10).join(task_lines)}

请及时处理！"""
        
        send_message(message)
        
        logger.info(f"死信队列告警已发送: {summary['total']} 个失败任务")
        return {"status": "success", "total": summary["total"], "unresolved": summary["unresolved"]}
    
    except Exception as e:
        logger.error(f"死信队列告警任务异常: {e}")
        return {"status": "error", "error": str(e)}
