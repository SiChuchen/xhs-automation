"""
告警系统 - 飞书 Webhook
"""

import os
import time
import logging
import requests
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AlertMessage:
    """告警消息"""
    title: str
    content: str
    level: AlertLevel = AlertLevel.INFO
    extra: Optional[Dict] = None


class FeishuWebhook:
    """飞书 Webhook"""
    
    def __init__(self, webhook_url: str = None, secret: str = None):
        self.webhook_url = webhook_url or os.environ.get("FEISHU_WEBHOOK_URL")
        self.secret = secret or os.environ.get("FEISHU_WEBHOOK_SECRET")
        self.enabled = bool(self.webhook_url)
        
        if not self.enabled:
            logger.warning("飞书告警未配置")
    
    def send(self, message: AlertMessage) -> bool:
        """
        发送告警
        
        Returns:
            是否发送成功
        """
        if not self.enabled:
            logger.debug(f"告警 (未发送): {message.title}")
            return True
        
        try:
            payload = self._build_payload(message)
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"飞书告警发送成功: {message.title}")
                return True
            else:
                logger.error(f"飞书告警发送失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"飞书告警发送异常: {e}")
            return False
    
    def _build_payload(self, message: AlertMessage) -> Dict:
        """构建消息体"""
        color_map = {
            AlertLevel.INFO: "grey",
            AlertLevel.WARNING: "orange",
            AlertLevel.ERROR: "red",
            AlertLevel.CRITICAL: "red",
        }
        
        card = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🔔 {message.title}"
                },
                "template": color_map.get(message.level, "grey")
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "plain_text",
                        "content": message.content
                    }
                }
            ]
        }
        
        if message.extra:
            extra_elements = []
            for key, value in message.extra.items():
                extra_elements.append({
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "plain_text",
                                "content": f"**{key}**: {value}"
                            }
                        }
                    ]
                })
            card["elements"].extend(extra_elements)
        
        card["elements"].append({
            "tag": "div",
            "text": {
                "tag": "plain_text",
                "content": f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S')}"
            }
        })
        
        return {"msg_type": "interactive", "card": card}


class AlertManager:
    """告警管理器"""
    
    def __init__(self, webhook_url: str = None):
        self.feishu = FeishuWebhook(webhook_url)
        self.alert_history: List[AlertMessage] = []
        self.cooldown_seconds = 300  # 同一类型告警冷却时间
    
    def alert(
        self,
        title: str,
        content: str,
        level: AlertLevel = AlertLevel.INFO,
        extra: Optional[Dict] = None,
        force: bool = False
    ):
        """
        发送告警
        
        Args:
            title: 标题
            content: 内容
            level: 级别
            extra: 额外信息
            force: 强制发送 (忽略冷却)
        """
        # 检查冷却
        if not force:
            if self._in_cooldown(title):
                logger.debug(f"告警冷却中: {title}")
                return
        
        message = AlertMessage(title=title, content=content, level=level, extra=extra)
        
        if self.feishu.send(message):
            self.alert_history.append(message)
    
    def _in_cooldown(self, title: str) -> bool:
        """检查是否在冷却期"""
        if not self.alert_history:
            return False
        
        last_alert = self.alert_history[-1]
        if last_alert.title == title:
            elapsed = time.time() - (getattr(last_alert, 'timestamp', None) or 0)
            return elapsed < self.cooldown_seconds
        
        return False
    
    def auth_failure_alert(self, count: int):
        """鉴权失败告警"""
        self.alert(
            title="🚨 账号异常 - Cookie 失效",
            content=f"连续 {count} 次鉴权失败，Cookie 可能已过期，需要重新登录",
            level=AlertLevel.CRITICAL,
            extra={
                "失败次数": str(count),
                "建议操作": "重新获取 cookies.json"
            }
        )
    
    def rate_limit_alert(self, count: int):
        """限流告警"""
        self.alert(
            title="⚠️ 触发限流",
            content=f"10分钟内触发 {count} 次限流，系统已自动降级",
            level=AlertLevel.ERROR,
            extra={
                "触发次数": str(count),
                "建议操作": "降低互动频率"
            }
        )
    
    def system_error_alert(self, error: str):
        """系统错误告警"""
        self.alert(
            title="❌ 系统错误",
            content=f"系统发生错误: {error}",
            level=AlertLevel.ERROR
        )
    
    def daily_summary(self, stats: Dict):
        """每日摘要"""
        self.alert(
            title="📊 每日运营摘要",
            content=f"""昨日运营数据:
- 点赞: {stats.get('likes', 0)}
- 收藏: {stats.get('collects', 0)}
- 评论: {stats.get('comments', 0)}
- 发布: {stats.get('publishes', 0)}""",
            level=AlertLevel.INFO,
            force=True
        )


_global_alert_manager = None

def get_alert_manager(webhook_url: str = None) -> AlertManager:
    """获取全局告警管理器"""
    global _global_alert_manager
    if _global_alert_manager is None:
        _global_alert_manager = AlertManager(webhook_url)
    return _global_alert_manager
