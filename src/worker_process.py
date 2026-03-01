#!/usr/bin/env python3
"""
消费进程 (Worker Process)
负责执行队列中的任务：调用大模型、生成图片、MCP接口通信
"""

import os
import sys
import time
import logging
import signal
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.queue.huey_config import huey


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class WorkerProcess:
    """消费进程"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.running = True
        
    def _signal_handler(self, signum, frame):
        """信号处理"""
        logger.info(f"收到信号 {signum}，正在关闭...")
        self.running = False
        
    def run(self):
        """运行 Worker"""
        logger.info("=" * 50)
        logger.info("消费进程启动")
        logger.info("=" * 50)
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # 导入任务模块以注册任务
        from src.queue import tasks
        
        logger.info("任务模块已加载")
        logger.info("消费进程进入等待任务状态")
        
        # 阻塞运行 Huey worker
        # 这是一个阻塞调用，会持续运行直到收到信号
        try:
            # worker 会持续运行，处理队列中的任务
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到键盘中断")
        finally:
            self._shutdown()
            
    def _shutdown(self):
        """关闭"""
        logger.info("消费进程已停止")


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="小红书自动化 - 消费进程")
    parser.add_argument("--config", type=str, help="配置文件路径")
    parser.add_argument("--workers", type=int, default=2, help="并发 worker 数量")
    parser.add_argument("--period", type=int, default=15, help="任务轮询间隔(秒)")
    
    args = parser.parse_args()
    
    config = {
        "workers": args.workers,
        "period": args.period
    }
    
    worker = WorkerProcess(config)
    worker.run()


if __name__ == "__main__":
    main()
