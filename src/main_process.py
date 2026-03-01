#!/usr/bin/env python3
"""
主控进程 (Main Process)
负责系统初始化、配置加载、定时任务触发、任务队列调度
"""

import os
import sys
import time
import logging
import signal
import schedule
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.queue.huey_config import huey
from src.queue.tasks import (
    auto_interact_task,
    fetch_trending_task,
    cleanup_task,
    TaskScheduler
)
from src.database import get_database
from src.cache.cache_manager import get_cache_manager


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/main.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MainProcess:
    """主控进程"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.running = True
        self.db = None
        self.cache = None
        
    def initialize(self):
        """初始化系统"""
        logger.info("=" * 50)
        logger.info("主控进程启动")
        logger.info("=" * 50)
        
        # 初始化数据库
        db_path = self.config.get("db_path", "data/xhs_data.db")
        self.db = get_database(db_path)
        
        # 初始化缓存
        cache_dir = self.config.get("cache_dir", "data/cache")
        self.cache = get_cache_manager(cache_dir)
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("系统初始化完成")
        
    def _signal_handler(self, signum, frame):
        """信号处理"""
        logger.info(f"收到信号 {signum}，正在关闭...")
        self.running = False
        
    def schedule_tasks(self):
        """调度定时任务"""
        # 热搜获取 - 每小时一次
        schedule.every().hour.do(self._schedule_trending_fetch)
        
        # 自动互动 - 每6小时一次
        schedule.every(6).hours.do(self._schedule_interaction)
        
        # 清理任务 - 每天凌晨3点
        schedule.every().day.at("03:00").do(self._schedule_cleanup)
        
        # 内容发布 - 每天早上9点 (示例)
        # schedule.every().day.at("09:00").do(self._schedule_publish)
        
        logger.info("定时任务已调度")
        
    def _schedule_trending_fetch(self):
        """调度热搜获取"""
        try:
            task = fetch_trending_task.schedule()
            logger.info(f"已调度热搜获取任务: {task.id}")
        except Exception as e:
            logger.error(f"调度热搜任务失败: {e}")
            
    def _schedule_interaction(self):
        """调度互动任务"""
        try:
            keywords = self.config.get("keywords", ["编程", "效率", "AI工具"])
            task = auto_interact_task.schedule(args=[keywords])
            logger.info(f"已调度互动任务: {task.id}")
        except Exception as e:
            logger.error(f"调度互动任务失败: {e}")
            
    def _schedule_cleanup(self):
        """调度清理任务"""
        try:
            task = cleanup_task.schedule(args=[30])
            logger.info(f"已调度清理任务: {task.id}")
        except Exception as e:
            logger.error(f"调度清理任务失败: {e}")
            
    def run(self):
        """运行主循环"""
        self.initialize()
        self.schedule_tasks()
        
        logger.info("主控进程进入主循环")
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"主循环异常: {e}")
                time.sleep(5)
                
        logger.info("主控进程已停止")
        
    def stop(self):
        """停止主进程"""
        self.running = False
        if self.cache:
            self.cache.close()
        logger.info("主控进程资源已释放")


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="小红书自动化 - 主控进程")
    parser.add_argument("--config", type=str, help="配置文件路径")
    parser.add_argument("--db-path", type=str, default="data/xhs_data.db", help="数据库路径")
    parser.add_argument("--cache-dir", type=str, default="data/cache", help="缓存目录")
    parser.add_argument("--keywords", nargs="+", default=["编程", "效率", "AI工具"], help="互动关键词")
    
    args = parser.parse_args()
    
    config = {
        "db_path": args.db_path,
        "cache_dir": args.cache_dir,
        "keywords": args.keywords
    }
    
    process = MainProcess(config)
    process.run()


if __name__ == "__main__":
    main()
