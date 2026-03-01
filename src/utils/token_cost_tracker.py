"""
Token 成本追踪模块
追踪 LLM 调用的 token 使用量和成本
"""

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token 使用记录"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    @property
    def cost(self) -> float:
        return 0.0


@dataclass
class LLMCallRecord:
    """LLM 调用记录"""
    id: Optional[int] = None
    timestamp: float = field(default_factory=time.time)
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    duration_ms: int = 0
    status: str = "success"
    error_message: str = ""
    session_id: str = ""
    prompt_preview: str = ""


class TokenCostTracker:
    """Token 成本追踪器"""
    
    DEFAULT_PRICING = {
        "gpt-4": {"prompt": 0.03, "completion": 0.06},
        "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
        "gpt-3.5-turbo": {"prompt": 0.001, "completion": 0.002},
        "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
        "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
        "deepseek-chat": {"prompt": 0.00014, "completion": 0.00028},
        "deepseek-coder": {"prompt": 0.00014, "completion": 0.00028},
        "abab6.5s-chat": {"prompt": 0.001, "completion": 0.001},
    }
    
    def __init__(self, db_path: str = "data/xhs_automation.db", pricing: Optional[Dict[str, Dict[str, float]]] = None):
        self.db_path = db_path
        self.pricing = {**self.DEFAULT_PRICING, **(pricing or {})}
        self._init_db()
        
        self._session_stats = defaultdict(lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost": 0.0,
            "calls": 0
        })
    
    def _init_db(self):
        """初始化数据库表"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    cost REAL DEFAULT 0,
                    duration_ms INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'success',
                    error_message TEXT,
                    session_id TEXT,
                    prompt_preview TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON llm_token_usage(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session 
                ON llm_token_usage(session_id)
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
    
    def _get_model_price(self, model: str) -> Dict[str, float]:
        """获取模型价格"""
        model_lower = model.lower()
        
        for pricing_model, price in self.pricing.items():
            if pricing_model in model_lower:
                return price
        
        return {"prompt": 0.001, "completion": 0.002}
    
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """计算成本"""
        price = self._get_model_price(model)
        
        prompt_cost = (prompt_tokens / 1_000_000) * price["prompt"]
        completion_cost = (completion_tokens / 1_000_000) * price["completion"]
        
        return prompt_cost + completion_cost
    
    def record_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int,
        session_id: str = "",
        prompt_preview: str = "",
        status: str = "success",
        error_message: str = ""
    ) -> LLMCallRecord:
        """
        记录 LLM 调用
        
        Returns:
            LLMCallRecord
        """
        total_tokens = prompt_tokens + completion_tokens
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)
        
        record = LLMCallRecord(
            timestamp=time.time(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
            session_id=session_id,
            prompt_preview=prompt_preview[:200] if prompt_preview else ""
        )
        
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO llm_token_usage 
                (timestamp, model, prompt_tokens, completion_tokens, total_tokens, 
                 cost, duration_ms, status, error_message, session_id, prompt_preview)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.timestamp,
                record.model,
                record.prompt_tokens,
                record.completion_tokens,
                record.total_tokens,
                record.cost,
                record.duration_ms,
                record.status,
                record.error_message,
                record.session_id,
                record.prompt_preview
            ))
            conn.commit()
        
        self._session_stats[session_id]["prompt_tokens"] += prompt_tokens
        self._session_stats[session_id]["completion_tokens"] += completion_tokens
        self._session_stats[session_id]["total_cost"] += cost
        self._session_stats[session_id]["calls"] += 1
        
        logger.debug(
            f"LLM 调用记录: model={model}, tokens={total_tokens}, "
            f"cost=${cost:.6f}, duration={duration_ms}ms"
        )
        
        return record
    
    def get_daily_usage(self, days: int = 7) -> List[Dict]:
        """获取每日使用统计"""
        cutoff = time.time() - (days * 86400)
        
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT 
                    date(timestamp, 'unixepoch', 'localtime') as day,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost,
                    COUNT(*) as calls
                FROM llm_token_usage
                WHERE timestamp > ? AND status = 'success'
                GROUP BY day
                ORDER BY day DESC
            """, (cutoff,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_model_usage(self, days: int = 30) -> Dict[str, Dict]:
        """获取各模型使用统计"""
        cutoff = time.time() - (days * 86400)
        
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT 
                    model,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost,
                    COUNT(*) as calls
                FROM llm_token_usage
                WHERE timestamp > ? AND status = 'success'
                GROUP BY model
                ORDER BY total_cost DESC
            """, (cutoff,))
            
            return {row['model']: dict(row) for row in cursor.fetchall()}
    
    def get_session_stats(self, session_id: str) -> Dict:
        """获取会话统计"""
        return dict(self._session_stats.get(session_id, {}))
    
    def get_total_cost(self, days: int = 30) -> float:
        """获取总成本"""
        cutoff = time.time() - (days * 86400)
        
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT SUM(cost) as total FROM llm_token_usage
                WHERE timestamp > ? AND status = 'success'
            """, (cutoff,))
            
            result = cursor.fetchone()
            return result['total'] if result and result['total'] else 0.0
    
    def get_total_tokens(self, days: int = 30) -> int:
        """获取总 Token 数"""
        cutoff = time.time() - (days * 86400)
        
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT SUM(total_tokens) as total FROM llm_token_usage
                WHERE timestamp > ? AND status = 'success'
            """, (cutoff,))
            
            result = cursor.fetchone()
            return result['total'] if result and result['total'] else 0
    
    def get_cost_summary(self, days: int = 30) -> Dict:
        """获取成本摘要"""
        daily = self.get_daily_usage(days)
        models = self.get_model_usage(days)
        
        total_cost = sum(day['total_cost'] for day in daily)
        total_tokens = sum(day['total_tokens'] for day in daily)
        total_calls = sum(day['calls'] for day in daily)
        
        return {
            "period_days": days,
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "total_calls": total_calls,
            "avg_cost_per_call": total_cost / total_calls if total_calls > 0 else 0,
            "avg_tokens_per_call": total_tokens / total_calls if total_calls > 0 else 0,
            "daily": daily,
            "by_model": models
        }
    
    def cleanup_old_records(self, days: int = 90) -> int:
        """清理旧记录"""
        cutoff = time.time() - (days * 86400)
        
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM llm_token_usage WHERE timestamp < ?",
                (cutoff,)
            )
            conn.commit()
            
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"清理了 {deleted} 条 Token 使用记录")
            
            return deleted


class TokenBudgetController:
    """Token 预算控制器"""
    
    def __init__(self, daily_budget: float = 10.0, monthly_budget: float = 100.0):
        self.daily_budget = daily_budget
        self.monthly_budget = monthly_budget
        self.tracker = TokenCostTracker()
    
    def can_make_call(self, estimated_cost: float = 0.001) -> tuple[bool, str]:
        """检查是否可以发起调用"""
        daily_cost = sum(day['total_cost'] for day in self.tracker.get_daily_usage(1))
        
        if daily_cost + estimated_cost > self.daily_budget:
            return False, f"daily_budget_exceeded: ${daily_cost:.4f} / ${self.daily_budget:.2f}"
        
        monthly_cost = self.tracker.get_total_cost(30)
        
        if monthly_cost + estimated_cost > self.monthly_budget:
            return False, f"monthly_budget_exceeded: ${monthly_cost:.4f} / ${self.monthly_budget:.2f}"
        
        return True, "ok"
    
    def get_remaining_budget(self) -> Dict:
        """获取剩余预算"""
        daily_cost = sum(day['total_cost'] for day in self.tracker.get_daily_usage(1))
        monthly_cost = self.tracker.get_total_cost(30)
        
        return {
            "daily": {
                "budget": self.daily_budget,
                "spent": daily_cost,
                "remaining": self.daily_budget - daily_cost
            },
            "monthly": {
                "budget": self.monthly_budget,
                "spent": monthly_cost,
                "remaining": self.monthly_budget - monthly_cost
            }
        }


_global_tracker = None
_global_budget_controller = None


def get_token_cost_tracker() -> TokenCostTracker:
    """获取全局 Token 成本追踪器"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = TokenCostTracker()
    return _global_tracker


def get_budget_controller(daily_budget: float = 10.0, monthly_budget: float = 100.0) -> TokenBudgetController:
    """获取全局预算控制器"""
    global _global_budget_controller
    if _global_budget_controller is None:
        _global_budget_controller = TokenBudgetController(daily_budget, monthly_budget)
    return _global_budget_controller
