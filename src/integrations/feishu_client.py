"""
飞书客户端 - OAuth 2.0 + 双向交互
支持消息推送、事件回调、卡片交互
"""

import os
import json
import time
import hmac
import hashlib
import logging
import requests
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    """飞书事件类型"""
    USER_AT_MESSAGE = "user_at_message"
    MESSAGE_CREATED = "message_created"
    MESSAGE_RECEIVED = "im.message.message_received"
    CARD_CALLBACK = "card_callback"


@dataclass
class FeishuConfig:
    """飞书配置"""
    app_id: str
    app_secret: str
    verification_token: str = ""
    encrypt_key: str = ""
    callback_url: str = ""


class FeishuClient:
    """飞书 API 客户端"""
    
    BASE_URL = "https://open.feishu.cn"
    TOKEN_EXPIRE_SECONDS = 7200  # 2小时
    
    def __init__(self, config: FeishuConfig = None):
        self.config = config
        self._tenant_token = None
        self._token_expires_at = 0
        self._token_lock = False
        
        self.callback_handlers: Dict[str, Callable] = {}
    
    @classmethod
    def from_env(cls) -> "FeishuClient":
        """从环境变量创建"""
        config = FeishuConfig(
            app_id=os.environ.get("FEISHU_APP_ID", ""),
            app_secret=os.environ.get("FEISHU_APP_SECRET", ""),
            verification_token=os.environ.get("FEISHU_VERIFICATION_TOKEN", ""),
            encrypt_key=os.environ.get("FEISHU_ENCRYPT_KEY", "")
        )
        return cls(config)
    
    def _get_tenant_token(self, force_refresh: bool = False) -> str:
        """获取 tenant_access_token (带缓存)"""
        if not force_refresh and self._tenant_token:
            if time.time() < self._token_expires_at - 300:
                return self._tenant_token
        
        if not self.config:
            raise ValueError("请配置飞书应用凭证")
        
        url = f"{self.BASE_URL}/open-apis/auth/v3/tenant_access_token/internal"
        
        data = {
            "app_id": self.config.app_id,
            "app_secret": self.config.app_secret
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") == 0:
                self._tenant_token = result["tenant_access_token"]
                self._token_expires_at = time.time() + self.TOKEN_EXPIRE_SECONDS
                logger.info("tenant_access_token 已刷新")
                return self._tenant_token
            else:
                logger.error(f"获取 token 失败: {result}")
                raise Exception(f"获取 token 失败: {result.get('msg')}")
                
        except requests.RequestException as e:
            logger.error(f"请求失败: {e}")
            raise
    
    def _get_headers(self) -> Dict:
        """获取请求头"""
        token = self._get_tenant_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def send_message(
        self,
        receive_id_type: str,
        receive_id: str,
        content: str,
        msg_type: str = "text"
    ) -> Dict:
        """发送消息"""
        url = f"{self.BASE_URL}/open-apis/im/v1/messages"
        
        params = {
            "receive_id_type": receive_id_type
        }
        
        data = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps({"text": content}) if msg_type == "text" else content
        }
        
        try:
            response = requests.post(url, params=params, json=data, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") == 0:
                logger.info(f"消息发送成功: {result.get('data', {}).get('message_id')}")
                return result
            else:
                logger.error(f"发送消息失败: {result}")
                return result
                
        except requests.RequestException as e:
            logger.error(f"发送消息失败: {e}")
            raise
    
    def send_text(self, receive_id: str, text: str, receive_id_type: str = "open_id") -> Dict:
        """发送文本消息"""
        return self.send_message(receive_id_type, receive_id, text, "text")
    
    def send_image(self, receive_id: str, image_key: str, receive_id_type: str = "open_id") -> Dict:
        """发送图片消息"""
        content = json.dumps({"image_key": image_key})
        return self.send_message(receive_id_type, receive_id, content, "image")
    
    def send_interactive_card(
        self,
        receive_id: str,
        card_template: Dict,
        receive_id_type: str = "open_id"
    ) -> Dict:
        """发送交互卡片"""
        content = json.dumps(card_template)
        return self.send_message(receive_id_type, receive_id, content, "interactive")
    
    def create_card_message(self, card_config: Dict) -> Dict:
        """创建卡片消息"""
        return {
            "config": {
                "wide_screen_mode": card_config.get("wide_screen", True)
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": card_config.get("title", "")
                },
                "template": card_config.get("template", "blue")
            },
            "elements": card_config.get("elements", [])
        }
    
    def send_qr_code_card(
        self,
        receive_id: str,
        title: str,
        qr_code_url: str,
        instruction: str = "请扫码登录"
    ) -> Dict:
        """发送二维码卡片"""
        card = self.create_card_message({
            "title": title,
            "template": "warning",
            "elements": [
                {
                    "tag": "img",
                    "img_url": {
                        "tag": "external",
                        "url": qr_code_url
                    },
                    "alt": {"tag": "plain_text", "content": "二维码"}
                },
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": instruction}
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "我已扫码"},
                            "type": "primary",
                            "action_id": "confirm_scan"
                        }
                    ]
                }
            ]
        })
        return self.send_interactive_card(receive_id, card)
    
    def upload_image(self, image_path: str) -> str:
        """上传图片"""
        url = f"{self.BASE_URL}/open-apis/im/v1/images"
        
        with open(image_path, 'rb') as f:
            files = {'image': f}
            data = {
                "image_type": "message",
                "image": (os.path.basename(image_path), f, "image/jpeg")
            }
            headers = self._get_headers()
            headers.pop("Content-Type", None)
            
            response = requests.post(url, files=files, data=data, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") == 0:
                return result["data"]["image_key"]
            else:
                raise Exception(f"上传图片失败: {result}")
    
    def register_callback_handler(self, event_type: str, handler: Callable):
        """注册事件回调处理函数"""
        self.callback_handlers[event_type] = handler
        logger.info(f"已注册事件处理器: {event_type}")
    
    def handle_callback(self, event_data: Dict) -> Any:
        """处理回调事件"""
        event_type = event_data.get("type")
        challenge = event_data.get("challenge")
        
        if challenge:
            return challenge
        
        if event_type in self.callback_handlers:
            handler = self.callback_handlers[event_type]
            return handler(event_data.get("event", {}))
        
        logger.warning(f"未处理的事件: {event_type}")
        return None
    
    def verify_signature(self, timestamp: str, sign: str, raw_body: str) -> bool:
        """验证签名"""
        if not self.config or not self.config.encrypt_key:
            return True
        
        sign_str = timestamp + raw_body
        hmac_obj = hmac.new(
            self.config.encrypt_key.encode(),
            sign_str.encode(),
            hashlib.sha256
        )
        expected_sign = hmac_obj.hexdigest()
        
        return hmac.compare_digest(sign, expected_sign)
    
    def get_user_info(self, user_id: str, id_type: str = "open_id") -> Dict:
        """获取用户信息"""
        url = f"{self.BASE_URL}/open-apis/contact/v3/users/{user_id}"
        
        params = {"user_id_type": id_type}
        
        try:
            response = requests.get(url, params=params, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"获取用户信息失败: {e}")
            return {}


class FeishuBot:
    """飞书机器人"""
    
    def __init__(self, client: FeishuClient, receive_id: str):
        self.client = client
        self.receive_id = receive_id
    
    def alert(self, title: str, content: str, level: str = "warning"):
        """发送告警"""
        template = "warning" if level == "warning" else "danger"
        
        card = self.client.create_card_message({
            "title": f"🔔 {title}",
            "template": template,
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": content}
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"🕐 {time.strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                }
            ]
        })
        
        return self.client.send_interactive_card(self.receive_id, card)
    
    def request_action(self, title: str, instruction: str, action_id: str) -> Dict:
        """请求用户操作"""
        card = self.client.create_card_message({
            "title": f"❓ {title}",
            "template": "blue",
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": instruction}
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "确认"},
                            "type": "primary",
                            "action_id": f"{action_id}_confirm"
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "取消"},
                            "action_id": f"{action_id}_cancel"
                        }
                    ]
                }
            ]
        })
        
        return self.client.send_interactive_card(self.receive_id, card)


def create_bot(receive_id: str = None) -> FeishuBot:
    """创建飞书机器人实例"""
    client = FeishuClient.from_env()
    
    if not receive_id:
        receive_id = os.environ.get("FEISHU_RECEIVE_ID")
    
    return FeishuBot(client, receive_id)
