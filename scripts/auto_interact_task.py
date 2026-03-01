#!/usr/bin/env python3
"""
小红书自动互动定时任务
每日运行自动互动任务（评论、点赞、收藏）
"""

import os
import sys
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.auto_interact import AutoInteract

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    config_path = "config/auto_interact_config.json"
    
    if not os.path.exists(config_path):
        logger.error(f"配置文件不存在: {config_path}")
        return 1
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    if not config.get('enabled', False):
        logger.info("自动互动已禁用")
        return 0
    
    logger.info("开始执行自动互动任务...")
    
    auto_interact = AutoInteract(config)
    result = auto_interact.run_daily_task()
    
    logger.info(f"互动任务完成: {result}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
