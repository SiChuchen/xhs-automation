"""
LLM Provider 路由模块 - 多提供商 + 熔断机制
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class LLMProviderRouter:
    """LLM 提供商路由器 - 支持多 Provider 轮询 + 熔断"""
    
    RETRYABLE_ERRORS = {502, 503, 429, 402, 408, 504}
    
    def __init__(
        self,
        config_path: str = "config/llm_config.json",
        fallback_threshold: int = 2
    ):
        self.config_path = config_path
        self.fallback_threshold = fallback_threshold
        self._config = None
        self._providers = []
        self._current_index = 0
        self._failure_count = {}
        self._circuit_broken = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        path = Path(self.config_path)
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except Exception as e:
                logger.warning(f"加载 LLM 配置失败: {e}")
                self._config = {"providers": [], "fallback_enabled": False}
        else:
            self._config = {"providers": [], "fallback_enabled": False}
        
        self._providers = [
            p for p in self._config.get("providers", [])
            if p.get("enabled", True)
        ]
        
        for p in self._providers:
            self._failure_count[p["name"]] = 0
            self._circuit_broken[p["name"]] = False
        
        logger.info(f"LLM Provider 路由初始化: {len(self._providers)} 个可用提供商")
    
    def _is_retryable_error(self, status_code: int) -> bool:
        """判断是否可重试的错误"""
        return status_code in self.RETRYABLE_ERRORS
    
    def _switch_to_backup(self):
        """切换到备用 Provider"""
        if len(self._providers) <= 1:
            return
        
        old_provider = self._providers[self._current_index]["name"]
        self._current_index = (self._current_index + 1) % len(self._providers)
        new_provider = self._providers[self._current_index]["name"]
        
        logger.warning(f"Provider 切换: {old_provider} -> {new_provider}")
    
    def _record_failure(self, provider_name: str):
        """记录失败次数"""
        self._failure_count[provider_name] = self._failure_count.get(provider_name, 0) + 1
        
        if self._failure_count[provider_name] >= self.fallback_threshold:
            self._circuit_broken[provider_name] = True
            logger.warning(f"Provider 熔断: {provider_name}, 失败次数: {self._failure_count[provider_name]}")
    
    def _record_success(self, provider_name: str):
        """记录成功，重置失败计数"""
        self._failure_count[provider_name] = 0
        if self._circuit_broken.get(provider_name, False):
            self._circuit_broken[provider_name] = False
            logger.info(f"Provider 恢复: {provider_name}")
    
    def get_provider(self) -> Optional[Dict]:
        """获取当前可用的 Provider"""
        if not self._providers:
            return None
        
        fallback_enabled = self._config.get("fallback_enabled", True)
        
        if not fallback_enabled:
            return self._providers[0]
        
        for _ in range(len(self._providers)):
            provider = self._providers[self._current_index]
            if not self._circuit_broken.get(provider["name"], False):
                return provider
            self._switch_to_backup()
        
        logger.error("所有 Provider 均已熔断")
        return None
    
    def call(
        self,
        prompt: str,
        system: str = "",
        call_func: callable = None
    ) -> Dict[str, Any]:
        """
        调用 LLM，支持多 Provider 轮询和熔断
        
        Args:
            prompt: 用户 prompt
            system: 系统 prompt
            call_func: 调用 LLM 的函数，签名为 (provider_config, prompt, system) -> response
        
        Returns:
            {"content": "...", "provider": "..."}
        """
        if call_func is None:
            raise ValueError("call_func 不能为空")
        
        fallback_enabled = self._config.get("fallback_enabled", True)
        max_retries = len(self._providers) if fallback_enabled else 1
        
        for attempt in range(max_retries):
            provider = self.get_provider()
            if provider is None:
                return {"error": "no available provider", "content": ""}
            
            try:
                response = call_func(provider, prompt, system)
                self._record_success(provider["name"])
                return {
                    "content": response.get("content", ""),
                    "provider": provider["name"],
                    "raw": response
                }
            except Exception as e:
                error_msg = str(e)
                status_code = 500
                
                if "402" in error_msg:
                    status_code = 402
                elif "429" in error_msg:
                    status_code = 429
                elif "502" in error_msg:
                    status_code = 502
                elif "503" in error_msg:
                    status_code = 503
                
                logger.warning(f"Provider {provider['name']} 调用失败 (attempt {attempt+1}): {error_msg}")
                
                if fallback_enabled and self._is_retryable_error(status_code):
                    self._record_failure(provider["name"])
                    self._switch_to_backup()
                else:
                    raise
        
        return {"error": "all providers failed", "content": ""}


def get_llm_router(config_path: str = "config/llm_config.json") -> LLMProviderRouter:
    """获取全局 LLM 路由实例"""
    global _llm_router
    if _llm_router is None:
        _llm_router = LLMProviderRouter(config_path)
    return _llm_router


_llm_router = None
