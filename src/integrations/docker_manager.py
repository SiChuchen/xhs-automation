"""
Docker 容器管理器
MCP 容器生命周期监控与自动重启
"""

import os
import time
import json
import logging
import subprocess
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ContainerStatus(Enum):
    """容器状态"""
    RUNNING = "running"
    STOPPED = "stopped"
    RESTARTING = "restarting"
    EXITED = "exited"
    DEAD = "dead"
    UNKNOWN = "unknown"


@dataclass
class ContainerInfo:
    """容器信息"""
    name: str
    status: ContainerStatus
    uptime: int
    restarts: int
    health: str


class DockerManager:
    """Docker 容器管理器"""
    
    def __init__(self, docker_path: str = "docker"):
        self.docker_path = docker_path
    
    def _run_command(self, args: List[str], timeout: int = 30) -> tuple:
        """执行 Docker 命令"""
        try:
            result = subprocess.run(
                [self.docker_path] + args,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"Docker 命令超时: {' '.join(args)}")
            return -1, "", "timeout"
        except FileNotFoundError:
            logger.error("Docker 命令未找到")
            return -1, "", "docker not found"
    
    def container_status(self, name: str) -> ContainerStatus:
        """获取容器状态"""
        code, stdout, _ = self._run_command(["inspect", "--format={{.State.Status}}", name])
        
        if code != 0:
            return ContainerStatus.UNKNOWN
        
        status = stdout.strip().lower()
        
        try:
            return ContainerStatus(status)
        except ValueError:
            return ContainerStatus.UNKNOWN
    
    def get_container_info(self, name: str) -> Optional[ContainerInfo]:
        """获取容器详细信息"""
        code, stdout, _ = self._run_command([
            "inspect", "--format={{json .State}}", name
        ])
        
        if code != 0:
            return None
        
        try:
            state = json.loads(stdout)
            
            return ContainerInfo(
                name=name,
                status=ContainerStatus(state.get("Status", "unknown")),
                uptime=int(time.time() - state.get("StartedAt", "").timestamp()) if state.get("StartedAt") else 0,
                restarts=state.get("RestartCount", 0),
                health=state.get("Health", {}).get("Status", "none")
            )
        except (json.JSONDecodeError, AttributeError):
            return None
    
    def restart_container(self, name: str, wait_seconds: int = 10) -> bool:
        """重启容器"""
        logger.warning(f"正在重启容器: {name}")
        
        code, _, stderr = self._run_command(["restart", name])
        
        if code != 0:
            logger.error(f"重启容器失败: {stderr}")
            return False
        
        time.sleep(wait_seconds)
        
        new_status = self.container_status(name)
        if new_status == ContainerStatus.RUNNING:
            logger.info(f"容器重启成功: {name}")
            return True
        
        logger.error(f"容器重启后状态异常: {new_status}")
        return False
    
    def stop_container(self, name: str) -> bool:
        """停止容器"""
        code, _, stderr = self._run_command(["stop", name])
        
        if code != 0:
            logger.error(f"停止容器失败: {stderr}")
            return False
        
        return True
    
    def start_container(self, name: str) -> bool:
        """启动容器"""
        code, _, stderr = self._run_command(["start", name])
        
        if code != 0:
            logger.error(f"启动容器失败: {stderr}")
            return False
        
        return True
    
    def get_container_logs(self, name: str, lines: int = 50) -> str:
        """获取容器日志"""
        code, stdout, _ = self._run_command(["logs", "--tail", str(lines), name])
        return stdout
    
    def list_containers(self, filter_name: str = None) -> List[str]:
        """列出容器"""
        args = ["ps", "--format", "{{.Names}}"]
        
        if filter_name:
            args.extend(["--filter", f"name={filter_name}"])
        
        code, stdout, _ = self._run_command(args)
        
        if code != 0:
            return []
        
        return [c.strip() for c in stdout.split("\n") if c.strip()]


class MCPContainerMonitor:
    """MCP 容器监控器"""
    
    def __init__(
        self,
        container_name: str = "xiaohongshu-mcp",
        failure_threshold: int = 5,
        check_interval: int = 60,
        docker_manager: DockerManager = None
    ):
        self.container_name = container_name
        self.failure_threshold = failure_threshold
        self.check_interval = check_interval
        
        self.docker = docker_manager or DockerManager()
        
        self.failure_count = 0
        self.last_check_time = 0
        self.is_restarting = False
    
    def check_health(self) -> bool:
        """检查容器健康状态"""
        status = self.docker.container_status(self.container_name)
        
        if status == ContainerStatus.RUNNING:
            self.failure_count = 0
            return True
        
        self.failure_count += 1
        logger.warning(
            f"容器健康检查失败: {self.container_name}, "
            f"status={status.value}, failure_count={self.failure_count}"
        )
        
        return False
    
    def check_and_restart(self) -> Dict:
        """检查并自动重启"""
        result = {
            "action": "none",
            "success": False,
            "details": {}
        }
        
        if self.is_restarting:
            result["action"] = "restarting"
            return result
        
        is_healthy = self.check_health()
        
        if not is_healthy and self.failure_count >= self.failure_threshold:
            result["action"] = "restart"
            result["details"]["failure_count"] = self.failure_count
            
            self.is_restarting = True
            
            success = self.docker.restart_container(self.container_name)
            
            result["success"] = success
            
            if success:
                self.failure_count = 0
                logger.info(f"容器自动重启成功: {self.container_name}")
            else:
                logger.error(f"容器自动重启失败: {self.container_name}")
            
            self.is_restarting = False
        
        return result
    
    def get_status(self) -> Dict:
        """获取监控状态"""
        info = self.docker.get_container_info(self.container_name)
        
        return {
            "container_name": self.container_name,
            "status": info.status.value if info else "unknown",
            "failure_count": self.failure_count,
            "is_restarting": self.is_restarting,
            "uptime": info.uptime if info else 0,
            "restarts": info.restarts if info else 0,
        }
    
    def get_logs(self, lines: int = 100) -> str:
        """获取容器日志"""
        return self.docker.get_container_logs(self.container_name, lines)


def create_mcp_monitor(
    container_name: str = "xiaohongshu-mcp",
    failure_threshold: int = 5
) -> MCPContainerMonitor:
    """创建 MCP 容器监控器"""
    return MCPContainerMonitor(
        container_name=container_name,
        failure_threshold=failure_threshold
    )
