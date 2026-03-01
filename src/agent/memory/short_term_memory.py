"""
短期记忆系统 - 会话上下文管理
"""

import time
import logging
from typing import List, Dict, Optional, Any
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ShortTermMemory:
    """短期记忆系统 - 会话上下文"""
    
    def __init__(self, max_size: int = 50, ttl_seconds: int = 3600):
        """
        初始化短期记忆
        
        Args:
            max_size: 最大存储消息数
            ttl_seconds: 消息过期时间(秒)
        """
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._sessions = {}  # session_id -> deque of messages
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ):
        """
        添加消息到会话
        
        Args:
            session_id: 会话ID
            role: 角色 (user/assistant/system)
            content: 消息内容
            metadata: 额外元数据
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = deque(maxlen=self.max_size)
        
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
        
        self._sessions[session_id].append(message)
    
    def get_context(
        self,
        session_id: str,
        max_messages: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取会话上下文
        
        Args:
            session_id: 会话ID
            max_messages: 最大返回消息数
        
        Returns:
            消息列表
        """
        if session_id not in self._sessions:
            return []
        
        messages = list(self._sessions[session_id])
        
        # 过滤过期消息
        now = time.time()
        messages = [m for m in messages if now - m["timestamp"] < self.ttl]
        
        # 返回最近的消息
        return messages[-max_messages:]
    
    def format_for_llm(
        self,
        session_id: str,
        max_messages: int = 10,
        system_prompt: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        格式化用于 LLM 调用的上下文
        
        Args:
            session_id: 会话ID
            max_messages: 最大消息数
            system_prompt: 系统提示词
        
        Returns:
            格式化后的消息列表
        """
        messages = []
        
        # 添加系统提示词
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # 添加历史消息
        context = self.get_context(session_id, max_messages)
        messages.extend(context)
        
        return messages
    
    def clear_session(self, session_id: str):
        """清除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"清除会话: {session_id}")
    
    def cleanup_expired(self):
        """清理过期会话"""
        now = time.time()
        expired_sessions = []
        
        for session_id, messages in self._sessions.items():
            if not messages:
                expired_sessions.append(session_id)
                continue
            
            # 检查最新消息是否过期
            latest = messages[-1]
            if now - latest["timestamp"] > self.ttl:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self._sessions[session_id]
        
        if expired_sessions:
            logger.info(f"清理过期会话: {len(expired_sessions)}")


class ConversationContext:
    """对话上下文管理器"""
    
    def __init__(self, short_term: ShortTermMemory):
        self.short_term = short_term
    
    def start_conversation(
        self,
        conversation_id: str,
        topic: str,
        user_info: Optional[Dict] = None
    ):
        """开始对话"""
        self.short_term.add_message(
            session_id=conversation_id,
            role="system",
            content=f"开始新对话，话题: {topic}",
            metadata={"topic": topic, "user_info": user_info}
        )
    
    def add_user_message(
        self,
        conversation_id: str,
        content: str
    ):
        """添加用户消息"""
        self.short_term.add_message(
            session_id=conversation_id,
            role="user",
            content=content
        )
    
    def add_assistant_message(
        self,
        conversation_id: str,
        content: str,
        metadata: Optional[Dict] = None
    ):
        """添加助手消息"""
        self.short_term.add_message(
            session_id=conversation_id,
            role="assistant",
            content=content,
            metadata=metadata
        )
    
    def get_conversation_history(
        self,
        conversation_id: str
    ) -> List[Dict]:
        """获取对话历史"""
        return self.short_term.get_context(conversation_id)


_global_short_term = None

def get_short_term_memory(max_size: int = 50, ttl_seconds: int = 3600) -> ShortTermMemory:
    """获取全局短期记忆"""
    global _global_short_term
    if _global_short_term is None:
        _global_short_term = ShortTermMemory(max_size, ttl_seconds)
    return _global_short_term
