"""
个性化回复生成器 - Persona + RAG
"""

import os
import random
import logging
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)


class ReplyGenerator:
    """个性化回复生成器"""
    
    def __init__(
        self,
        persona_manager,
        long_term_memory=None,
        llm_client=None
    ):
        self.persona_manager = persona_manager
        self.long_term_memory = long_term_memory
        self.llm_client = llm_client
    
    def generate_comment(
        self,
        post_content: str,
        post_author: str = "",
        topic: str = "general",
        persona_name: str = "hot_topic_hunter",
        use_template: bool = True,
        use_llm: bool = True
    ) -> str:
        """
        生成评论
        
        Args:
            post_content: 帖子内容
            post_author: 帖子作者
            topic: 话题标签
            persona_name: 人设名称
            use_template: 是否使用模板
            use_llm: 是否使用 LLM 生成
        
        Returns:
            生成的评论内容
        """
        persona = self.persona_manager.get_persona(persona_name)
        if not persona:
            logger.warning(f"未找到人设: {persona_name}，使用默认")
            persona = self.persona_manager.get_persona("hot_topic_hunter")
        
        # 优先使用模板
        if use_template and persona.templates.get("comment"):
            return random.choice(persona.templates["comment"])
        
        # 使用 LLM 生成
        if use_llm and self.llm_client:
            return self._generate_with_llm(
                post_content=post_content,
                post_author=post_author,
                topic=topic,
                persona=persona
            )
        
        return "喜欢，收藏了！"
    
    def _generate_with_llm(
        self,
        post_content: str,
        post_author: str,
        topic: str,
        persona: Any
    ) -> str:
        """使用 LLM 生成回复"""
        # 获取历史上下文
        context = ""
        if self.long_term_memory:
            context = self.long_term_memory.get_context_for_topic(topic, post_content)
        
        # 构建 Prompt
        system_prompt = persona.build_system_prompt(context=context, topic=topic)
        
        user_prompt = f"""请为以下小红书帖子生成一条评论:

帖子内容: {post_content[:200]}...
作者: {post_author}
话题: {topic}

要求:
1. 符合人设特点
2. 自然、真实
3. 30字以内
4. 可以使用emoji

评论:"""
        
        try:
            response = self.llm_client.chat(
                system=system_prompt,
                user=user_prompt
            )
            return response.get("content", "收藏了！")
        except Exception as e:
            logger.error(f"LLM 生成失败: {e}")
            return "收藏了，谢谢分享！"
    
    def generate_reply(
        self,
        original_comment: str,
        topic: str = "general",
        persona_name: str = "hot_topic_hunter"
    ) -> str:
        """生成回复 (回复他人评论)"""
        persona = self.persona_manager.get_persona(persona_name)
        
        user_prompt = f"""请回复以下评论:

原评论: {original_comment}
话题: {topic}

人设: {persona.name}
特点: {', '.join(persona.personality)}

要求:
1. 符合人设风格
2. 友好互动
3. 20字以内

回复:"""
        
        if self.llm_client:
            try:
                response = self.llm_client.chat(
                    system=persona.build_system_prompt(topic=topic),
                    user=user_prompt
                )
                return response.get("content", "说得对！")
            except Exception as e:
                logger.error(f"LLM 生成回复失败: {e}")
        
        return "同意你的观点！"


class LLMClient:
    """LLM 客户端 (需根据实际 LLM 实现)"""
    
    def __init__(self, provider: str = "openai", api_key: str = None, **kwargs):
        self.provider = provider
        self.api_key = api_key or os.environ.get("LLM_API_KEY")
        self.base_url = kwargs.get("base_url")
        self.model = kwargs.get("model", "gpt-3.5-turbo")
        self._client = None
        
        self._initialize()
    
    def _initialize(self):
        """初始化客户端"""
        if self.provider == "openai":
            try:
                import openai
                self._client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("openai 未安装")
        
        elif self.provider == "deepseek":
            try:
                import openai
                self._client = openai.OpenAI(
                    api_key=self.api_key,
                    base_url="https://api.deepseek.com/v1"
                )
            except ImportError:
                logger.warning("openai 未安装")
        
        elif self.provider == "minimax":
            self.base_url = self.base_url or "https://api.minimax.chat/v1"
    
    def chat(
        self,
        system: str,
        user: str,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """发送聊天请求"""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
        
        if self.provider in ["openai", "deepseek"] and self._client:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature
            )
            return {
                "content": response.choices[0].message.content,
                "usage": response.usage.total_tokens
            }
        
        elif self.provider == "minimax":
            return self._chat_minimax(messages, temperature)
        
        return {"content": "LLM 客户端未配置", "usage": 0}
    
    def _chat_minimax(self, messages, temperature) -> Dict:
        """MiniMax API 调用"""
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        try:
            resp = requests.post(
                f"{self.base_url}/text/chatcompletion_v2",
                headers=headers,
                json=data,
                timeout=30
            )
            result = resp.json()
            return {
                "content": result.get("choices", [{}])[0].get("message", {}).get("content", ""),
                "usage": result.get("usage", {}).get("total_tokens", 0)
            }
        except Exception as e:
            logger.error(f"MiniMax API 调用失败: {e}")
            return {"content": "", "usage": 0}


def get_reply_generator(
    persona_manager=None,
    long_term_memory=None,
    llm_provider: str = None,
    **llm_config
) -> ReplyGenerator:
    """获取回复生成器"""
    if persona_manager is None:
        from .persona_manager import get_persona_manager
        persona_manager = get_persona_manager()
    
    llm_client = None
    if llm_provider:
        llm_client = LLMClient(provider=llm_provider, **llm_config)
    
    return ReplyGenerator(
        persona_manager=persona_manager,
        long_term_memory=long_term_memory,
        llm_client=llm_client
    )
