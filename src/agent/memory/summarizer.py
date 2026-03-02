"""
记忆摘要器 - 将长对话压缩为简洁摘要
"""

import os
import sys
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class MemorySummarizer:
    """记忆摘要器 - 使用 LLM 将长对话压缩为 100 字以内的摘要"""
    
    def __init__(self, provider: str = "minimax"):
        self.provider = provider
        self._init_llm()
    
    def _init_llm(self):
        """初始化 LLM 客户端"""
        if self.provider == "minimax":
            self.api_key = os.environ.get("MINIMAX_API_KEY", "")
            self.base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
            self.model = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.5")
            self.enabled = bool(self.api_key)
        elif self.provider == "deepseek":
            self.api_key = os.environ.get("DEEPSEEK_API_KEY", "sk-b6384f153e374cddb8fcd73ab21e280b")
            self.base_url = "https://api.deepseek.com/v1"
            self.model = "deepseek-chat"
            self.enabled = bool(self.api_key)
        else:
            self.enabled = False
    
    def summarize(self, messages: List[Dict], max_length: int = 100) -> str:
        """
        将对话历史压缩为摘要
        
        Args:
            messages: 对话消息列表 [{"role": "user/assistant", "content": "..."}]
            max_length: 摘要最大长度(字)
        
        Returns:
            压缩后的摘要字符串
        """
        if not self.enabled:
            logger.warning("LLM 未启用，无法生成摘要")
            return ""
        
        if not messages:
            return ""
        
        if len(messages) <= 5:
            return ""
        
        conversation_text = self._format_messages(messages)
        
        prompt = f"""请将以下小红书评论区对话压缩为{max_length}字以内的摘要，保留关键信息、用户诉求和互动脉络:

{conversation_text}

摘要:"""
        
        try:
            summary = self._call_llm(prompt)
            return summary.strip()[:max_length * 2]
        except Exception as e:
            logger.error(f"生成摘要失败: {e}")
            return ""
    
    def _format_messages(self, messages: List[Dict]) -> str:
        """格式化消息列表为文本"""
        lines = []
        for msg in messages[-10:]:
            role = "用户" if msg.get("role") == "user" else "AI"
            content = msg.get("content", "")[:100]
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
    
    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""
        import requests
        
        if self.provider == "minimax":
            url = f"{self.base_url}/text/chatcompletion_v2"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5,
                "max_tokens": 200
            }
        else:
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5,
                "max_tokens": 200
            }
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]


def get_summarizer(provider: str = "minimax") -> MemorySummarizer:
    """获取全局摘要器实例"""
    global _summarizer
    if _summarizer is None:
        _summarizer = MemorySummarizer(provider)
    return _summarizer


_summarizer = None
