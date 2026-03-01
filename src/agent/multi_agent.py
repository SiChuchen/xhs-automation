"""
多智能体编排系统
支持流水线协作和并行执行
"""

import os
import logging
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """智能体状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class AgentContext:
    """智能体上下文"""
    topic: str
    data: Dict = field(default_factory=dict)
    results: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class AgentResult:
    """智能体执行结果"""
    status: AgentStatus
    data: Any = None
    error: str = ""
    metadata: Dict = field(default_factory=dict)


class BaseAgent(ABC):
    """智能体基类"""
    
    def __init__(self, name: str, temperature: float = 0.7):
        self.name = name
        self.temperature = temperature
        self.llm_client = None
    
    @abstractmethod
    def run(self, context: AgentContext) -> AgentResult:
        """执行智能体逻辑"""
        pass
    
    def set_llm_client(self, client):
        """设置 LLM 客户端"""
        self.llm_client = client
    
    def call_llm(self, prompt: str, system: str = None) -> str:
        """调用 LLM"""
        if not self.llm_client:
            raise ValueError("LLM 客户端未配置")
        
        response = self.llm_client.chat(
            system=system or self.get_system_prompt(),
            user=prompt,
            temperature=self.temperature
        )
        
        return response.get("content", "")


class BackgroundRetrievalAgent(BaseAgent):
    """背景设定检索智能体 (RAG)"""
    
    def __init__(self, name: str = "BackgroundRetrieval"):
        super().__init__(name)
        self.vector_store = None
    
    def set_vector_store(self, store):
        self.vector_store = store
    
    def run(self, context: AgentContext) -> AgentResult:
        try:
            query = context.topic
            
            if self.vector_store:
                results = self.vector_store.search(query, top_k=3)
                context.results["background"] = results
                context.metadata["retrieved_count"] = len(results)
            else:
                context.results["background"] = []
            
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data=context.results["background"]
            )
        except Exception as e:
            logger.error(f"背景检索失败: {e}")
            return AgentResult(status=AgentStatus.FAILED, error=str(e))
    
    def get_system_prompt(self) -> str:
        return "你是一个知识检索助手，根据用户查询检索相关的背景设定和知识。"


class ContentWriterAgent(BaseAgent):
    """文案主笔智能体"""
    
    def __init__(self, name: str = "ContentWriter", temperature: float = 0.8):
        super().__init__(name, temperature)
    
    def run(self, context: AgentContext) -> AgentResult:
        try:
            topic = context.topic
            background = context.results.get("background", [])
            persona = context.metadata.get("persona", {})
            
            prompt = self._build_prompt(topic, background, persona)
            draft = self.call_llm(prompt)
            
            context.results["draft"] = draft
            context.metadata["draft_length"] = len(draft)
            
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data=draft
            )
        except Exception as e:
            logger.error(f"文案生成失败: {e}")
            return AgentResult(status=AgentStatus.FAILED, error=str(e))
    
    def _build_prompt(self, topic: str, background: List, persona: Dict) -> str:
        parts = [f"请围绕以下话题生成一篇小红书风格的笔记:\n\n话题: {topic}\n"]
        
        if background:
            parts.append("相关背景:\n")
            for bg in background:
                parts.append(f"- {bg}\n")
        
        if persona:
            name = persona.get("name", "AI助手")
            style = persona.get("speaking_style", "")
            parts.append(f"\n人设: {name}, 风格: {style}")
        
        parts.append("\n\n要求:\n- 语言生动有趣\n- 使用适量 emoji\n- 200-500字\n- 有价值的内容")
        
        return "\n".join(parts)
    
    def get_system_prompt(self) -> str:
        return "你是一个专业的小红书文案写手，擅长生成吸引人的内容。"


class ReviewAgent(BaseAgent):
    """审核合规智能体"""
    
    def __init__(self, name: str = "Reviewer", temperature: float = 0.3):
        super().__init__(name, temperature)
        self.blocked_words = []
        self.max_length = 1000
    
    def set_blocked_words(self, words: List[str]):
        self.blocked_words = words
    
    def run(self, context: AgentContext) -> AgentResult:
        try:
            draft = context.results.get("draft", "")
            
            issues = []
            
            if len(draft) > self.max_length:
                issues.append(f"内容过长 ({len(draft)} > {self.max_length})")
            
            for word in self.blocked_words:
                if word in draft:
                    issues.append(f"包含敏感词: {word}")
            
            if issues:
                context.results["review"] = {"approved": False, "issues": issues}
                return AgentResult(
                    status=AgentStatus.SUCCESS,
                    data={"approved": False, "issues": issues}
                )
            
            context.results["review"] = {"approved": True, "issues": []}
            
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data={"approved": True, "final_content": draft}
            )
        except Exception as e:
            logger.error(f"审核失败: {e}")
            return AgentResult(status=AgentStatus.FAILED, error=str(e))
    
    def get_system_prompt(self) -> str:
        return "你是一个内容审核专家，检查内容是否符合规范。"


class MultiAgentOrchestrator:
    """多智能体编排器"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.pipeline: List[str] = []
        self.parallel_agents: List[str] = []
    
    def add_agent(self, name: str, agent: BaseAgent):
        """添加智能体"""
        self.agents[name] = agent
        logger.info(f"已添加智能体: {name}")
    
    def set_pipeline(self, agent_names: List[str]):
        """设置执行流水线"""
        self.pipeline = agent_names
    
    def add_to_pipeline(self, agent_name: str):
        """添加到流水线"""
        if agent_name in self.agents:
            self.pipeline.append(agent_name)
    
    def execute_pipeline(
        self,
        topic: str,
        context_data: Dict = None,
        persona: Dict = None,
        stop_on_error: bool = True
    ) -> AgentContext:
        """执行流水线"""
        context = AgentContext(
            topic=topic,
            data=context_data or {},
            metadata={"persona": persona}
        )
        
        for agent_name in self.pipeline:
            if agent_name not in self.agents:
                logger.warning(f"智能体不存在: {agent_name}")
                continue
            
            agent = self.agents[agent_name]
            logger.info(f"执行智能体: {agent_name}")
            
            result = agent.run(context)
            
            if result.status == AgentStatus.FAILED:
                logger.error(f"智能体执行失败: {agent_name}, {result.error}")
                context.errors.append(f"{agent_name}: {result.error}")
                
                if stop_on_error:
                    break
        
        return context
    
    def execute_parallel(
        self,
        agents: List[str],
        context: AgentContext
    ) -> Dict[str, AgentResult]:
        """并行执行多个智能体"""
        import concurrent.futures
        
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {}
            for name in agents:
                if name in self.agents:
                    future = executor.submit(self.agents[name].run, context)
                    futures[name] = future
            
            for name, future in futures.items():
                try:
                    results[name] = future.result()
                except Exception as e:
                    results[name] = AgentResult(status=AgentStatus.FAILED, error=str(e))
        
        return results


class ContentGenerationPipeline:
    """内容生成流水线"""
    
    def __init__(self, orchestrator: MultiAgentOrchestrator = None):
        self.orchestrator = orchestrator or MultiAgentOrchestrator()
        self._setup_default_agents()
    
    def _setup_default_agents(self):
        """设置默认智能体"""
        retrieval = BackgroundRetrievalAgent()
        writer = ContentWriterAgent()
        reviewer = ReviewAgent()
        
        self.orchestrator.add_agent("retrieval", retrieval)
        self.orchestrator.add_agent("writer", writer)
        self.orchestrator.add_agent("reviewer", reviewer)
        
        self.orchestrator.set_pipeline(["retrieval", "writer", "reviewer"])
    
    def set_llm_client(self, client):
        """设置 LLM 客户端"""
        for agent in self.orchestrator.agents.values():
            agent.set_llm_client(client)
    
    def set_vector_store(self, store):
        """设置向量存储"""
        retrieval = self.orchestrator.agents.get("retrieval")
        if retrieval:
            retrieval.set_vector_store(store)
    
    def set_persona(self, persona: Dict):
        """设置人设"""
        self.orchestrator.pipeline_context_metadata["persona"] = persona
    
    def generate(self, topic: str, max_retries: int = 2) -> str:
        """生成内容"""
        for attempt in range(max_retries):
            context = self.orchestrator.execute_pipeline(topic)
            
            review = context.results.get("review", {})
            if review.get("approved"):
                return review.get("final_content", "")
            
            if attempt < max_retries - 1:
                issues = review.get("issues", [])
                logger.info(f"审核未通过，重试 {attempt + 1}: {issues}")
                context.results["draft"] = self._revise_based_on_feedback(
                    context.results.get("draft", ""),
                    issues
                )
        
        return context.results.get("draft", "")
    
    def _revise_based_on_feedback(self, draft: str, issues: List[str]) -> str:
        """根据反馈修订"""
        prompt = f"请根据以下反馈修订内容:\n\n原文:\n{draft}\n\n问题:\n" + "\n".join(f"- {i}" for i in issues)
        
        writer = self.orchestrator.agents.get("writer")
        if writer:
            return writer.call_llm(prompt)
        
        return draft


def create_content_pipeline(llm_client = None, vector_store = None) -> ContentGenerationPipeline:
    """创建内容生成流水线"""
    pipeline = ContentGenerationPipeline()
    
    if llm_client:
        pipeline.set_llm_client(llm_client)
    
    if vector_store:
        pipeline.set_vector_store(vector_store)
    
    return pipeline
