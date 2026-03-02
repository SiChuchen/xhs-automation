"""
任务状态机 - 乐观锁 + TTL 防死锁
确保任务只被执行一次，防止重复发布/互动
"""

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from ..utils.timezone_utils import now as get_now

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ClaimResult:
    """抢占结果"""
    success: bool
    task_id: int
    reason: str
    previous_status: Optional[str] = None


class OptimisticLockStateMachine:
    """乐观锁状态机 - 带 TTL 防死锁"""
    
    DEFAULT_TIMEOUT_MINUTES = 15
    
    def __init__(self, db_path: str = "data/xhs_automation.db"):
        self.db_path = db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """确保表存在"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _task_lock_meta (
                    table_name TEXT PRIMARY KEY,
                    has_locked_at INTEGER DEFAULT 0,
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            conn.commit()
    
    @contextmanager
    def _get_conn(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _check_and_add_locked_at(self, conn, table_name: str):
        """检查并添加 locked_at 字段"""
        cursor = conn.execute(
            "SELECT has_locked_at FROM _task_lock_meta WHERE table_name = ?",
            (table_name,)
        )
        row = cursor.fetchone()
        
        if not row or not row['has_locked_at']:
            cursor = conn.execute(
                "PRAGMA table_info({})".format(table_name)
            )
            columns = {row['name'] for row in cursor.fetchall()}
            
            if 'locked_at' not in columns:
                conn.execute(
                    "ALTER TABLE {} ADD COLUMN locked_at TEXT".format(table_name)
                )
                logger.info(f"表 {table_name} 已添加 locked_at 字段")
            
            conn.execute(
                "INSERT OR REPLACE INTO _task_lock_meta (table_name, has_locked_at) VALUES (?, 1)",
                (table_name,)
            )
            conn.commit()
    
    def claim(
        self,
        table_name: str,
        task_id: int,
        timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES
    ) -> ClaimResult:
        """
        抢占任务（乐观锁 + TTL 防死锁）
        
        Args:
            table_name: 表名 (posts/interactions)
            task_id: 任务 ID
            timeout_minutes: 超时时间（分钟）
        
        Returns:
            ClaimResult: 抢占结果
        """
        self._ensure_tables()
        
        now = time.time()  # Unix timestamp
        
        with self._get_conn() as conn:
            self._check_and_add_locked_at(conn, table_name)
            
            cursor = conn.execute(
                f"SELECT status, locked_at FROM {table_name} WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return ClaimResult(
                    success=False,
                    task_id=task_id,
                    reason="task_not_found"
                )
            
            current_status = row['status']
            locked_at = row['locked_at']
            
            can_claim = False
            
            if current_status == TaskStatus.PENDING.value:
                can_claim = True
            elif current_status == TaskStatus.PROCESSING.value:
                if locked_at:
                    try:
                        lock_time = float(locked_at)
                        elapsed = now - lock_time
                        timeout_seconds = timeout_minutes * 60
                        if elapsed > timeout_seconds:
                            can_claim = True
                            logger.warning(
                                f"任务 {task_id} processing 状态超过 {timeout_minutes} 分钟，"
                                f"允许重新抢占 (elapsed={elapsed:.0f}s)"
                            )
                    except (ValueError, TypeError):
                        can_claim = True
                else:
                    can_claim = True
            
            if not can_claim:
                return ClaimResult(
                    success=False,
                    task_id=task_id,
                    reason=f"status_{current_status}",
                    previous_status=current_status
                )
            
            time_check = int(timeout_minutes * 60)  # 转换为秒
            cutoff_time = now - time_check
            
            affected = conn.execute(f"""
                UPDATE {table_name}
                SET status = ?, locked_at = ?, updated_at = ?
                WHERE id = ? AND (
                    status = ? 
                    OR (status = ? AND locked_at < ?)
                )
            """, (
                TaskStatus.PROCESSING.value,
                now,
                now,
                task_id,
                TaskStatus.PENDING.value,
                TaskStatus.PROCESSING.value,
                cutoff_time
            ))
            conn.commit()
            
            if affected.rowcount > 0:
                logger.info(f"成功抢占任务: {table_name}.{task_id}")
                return ClaimResult(
                    success=True,
                    task_id=task_id,
                    reason="claimed",
                    previous_status=current_status
                )
            else:
                return ClaimResult(
                    success=False,
                    task_id=task_id,
                    reason="concurrent_claim_failed",
                    previous_status=current_status
                )
    
    def release(
        self,
        table_name: str,
        task_id: int,
        new_status: str = TaskStatus.PENDING.value
    ) -> bool:
        """
        释放任务锁
        
        Args:
            table_name: 表名
            task_id: 任务 ID
            new_status: 新状态 (completed/failed/pending)
        
        Returns:
            是否成功
        """
        now = time.time()
        
        with self._get_conn() as conn:
            affected = conn.execute(f"""
                UPDATE {table_name}
                SET status = ?, locked_at = NULL, updated_at = ?
                WHERE id = ?
            """, (
                new_status,
                now,
                task_id
            ))
            conn.commit()
            
            return affected.rowcount > 0
    
    def complete(self, table_name: str, task_id: int) -> bool:
        """标记任务完成"""
        return self.release(table_name, task_id, TaskStatus.COMPLETED.value)
    
    def fail(self, table_name: str, task_id: int, error: str = "") -> bool:
        """标记任务失败"""
        with self._get_conn() as conn:
            conn.execute(f"""
                UPDATE {table_name}
                SET status = ?, locked_at = NULL, error_message = ?, updated_at = ?
                WHERE id = ?
            """, (
                TaskStatus.FAILED.value,
                error[:500] if error else "",
                get_now().timestamp(),
                task_id
            ))
            conn.commit()
            return True
    
    def get_status(self, table_name: str, task_id: int) -> Optional[Dict]:
        """获取任务状态"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {table_name} WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def cleanup_stale_locks(self, table_name: str, timeout_hours: int = 24) -> int:
        """清理过期的锁（运维用）"""
        cutoff = (get_now() - timedelta(hours=timeout_hours)).isoformat()
        
        with self._get_conn() as conn:
            cursor = conn.execute(f"""
                UPDATE {table_name}
                SET status = ?, locked_at = NULL
                WHERE status = ? AND locked_at < ?
            """, (
                TaskStatus.FAILED.value,
                TaskStatus.PROCESSING.value,
                cutoff
            ))
            conn.commit()
            
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"清理了 {deleted} 个过期锁")
            
            return deleted


class PostStateMachine(OptimisticLockStateMachine):
    """笔记发布状态机"""
    
    def __init__(self, db_path: str = "data/xhs_automation.db"):
        super().__init__(db_path)
        self.table_name = "posts"
    
    def claim_post(self, post_id: int, timeout_minutes: int = 15) -> ClaimResult:
        """抢占发布任务"""
        return self.claim(self.table_name, post_id, timeout_minutes)
    
    def complete_post(self, post_id: int) -> bool:
        """标记发布完成"""
        return self.complete(self.table_name, post_id)
    
    def fail_post(self, post_id: int, error: str = "") -> bool:
        """标记发布失败"""
        return self.fail(self.table_name, post_id, error)


class InteractionStateMachine(OptimisticLockStateMachine):
    """互动状态机"""
    
    def __init__(self, db_path: str = "data/xhs_automation.db"):
        super().__init__(db_path)
        self.table_name = "interactions"
    
    def claim_interaction(self, interaction_id: int, timeout_minutes: int = 15) -> ClaimResult:
        """抢占互动任务"""
        return self.claim(self.table_name, interaction_id, timeout_minutes)
    
    def complete_interaction(self, interaction_id: int) -> bool:
        """标记互动完成"""
        return self.complete(self.table_name, interaction_id)
    
    def fail_interaction(self, interaction_id: int, error: str = "") -> bool:
        """标记互动失败"""
        return self.fail(self.table_name, interaction_id, error)


_global_post_sm = None
_global_interaction_sm = None


def get_post_state_machine() -> PostStateMachine:
    """获取全局笔记状态机"""
    global _global_post_sm
    if _global_post_sm is None:
        _global_post_sm = PostStateMachine()
    return _global_post_sm


def get_interaction_state_machine() -> InteractionStateMachine:
    """获取全局互动状态机"""
    global _global_interaction_sm
    if _global_interaction_sm is None:
        _global_interaction_sm = InteractionStateMachine()
    return _global_interaction_sm
