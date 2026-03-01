"""
审计日志 - 操作轨迹记录
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler


class AuditLogger:
    """审计日志"""
    
    def __init__(self, log_dir: str = "logs/audit", retention_days: int = 90):
        self.log_dir = log_dir
        self.retention_days = retention_days
        
        os.makedirs(log_dir, exist_ok=True)
        
        self.logger = logging.getLogger("xhs_audit")
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = TimedRotatingFileHandler(
                os.path.join(log_dir, "audit.log"),
                when="midnight",
                interval=1,
                backupCount=retention_days,
                encoding="utf-8"
            )
            handler.suffix = "%Y-%m-%d"
            
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log(
        self,
        action: str,
        target: str,
        status: str,
        details: Optional[Dict] = None,
        user: str = "system"
    ):
        """
        记录操作
        
        Args:
            action: 操作类型 (login, publish, like, collect, comment, etc.)
            target: 目标 (post_id, user_id, etc.)
            status: 状态 (success, failure, blocked)
            details: 详情
            user: 用户
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user": user,
            "action": action,
            "target": target,
            "status": status,
            "details": details or {}
        }
        
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))
    
    def log_login(self, status: str, details: Optional[Dict] = None):
        """记录登录"""
        self.log("login", "xhs_account", status, details)
    
    def log_publish(self, post_id: str, status: str, details: Optional[Dict] = None):
        """记录发布"""
        self.log("publish", post_id, status, details)
    
    def log_interaction(
        self,
        action: str,
        target_post: str,
        status: str,
        details: Optional[Dict] = None
    ):
        """记录互动"""
        self.log(f"interaction_{action}", target_post, status, details)
    
    def log_api_call(
        self,
        api_name: str,
        status: str,
        duration_ms: float,
        details: Optional[Dict] = None
    ):
        """记录 API 调用"""
        self.log(
            "api_call",
            api_name,
            status,
            {**(details or {}), "duration_ms": duration_ms}
        )
    
    def log_security_event(
        self,
        event_type: str,
        details: Optional[Dict] = None
    ):
        """记录安全事件"""
        self.log("security", event_type, "alert", details)
    
    def log_config_change(self, key: str, old_value: Any, new_value: Any):
        """记录配置变更"""
        self.log(
            "config_change",
            key,
            "success",
            {"old": str(old_value), "new": str(new_value)}
        )


class HealthChecker:
    """健康检查"""
    
    def __init__(self, db=None, cache=None):
        self.db = db
        self.cache = cache
    
    def check_health(self) -> Dict:
        """检查健康状态"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "checks": {}
        }
        
        # 检查数据库
        if self.db:
            try:
                self.db.get_posts(limit=1)
                results["checks"]["database"] = "ok"
            except Exception as e:
                results["checks"]["database"] = f"error: {e}"
                results["status"] = "unhealthy"
        
        # 检查缓存
        if self.cache:
            try:
                self.cache.get("health_check")
                results["checks"]["cache"] = "ok"
            except Exception as e:
                results["checks"]["cache"] = f"error: {e}"
        
        return results
    
    def get_metrics(self) -> Dict:
        """获取指标"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
        }
        
        if self.db:
            try:
                db_size = self.db.get_db_size()
                metrics["db_size_bytes"] = db_size
            except:
                pass
        
        return metrics


_global_audit_logger = None

def get_audit_logger(log_dir: str = "logs/audit") -> AuditLogger:
    """获取全局审计日志"""
    global _global_audit_logger
    if _global_audit_logger is None:
        _global_audit_logger = AuditLogger(log_dir)
    return _global_audit_logger
