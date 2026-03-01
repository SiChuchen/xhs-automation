"""
长期记忆系统 - 使用 ChromaDB (Embedded 模式)
记录 AI 账号的历史发言特征与立场
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("chromadb 未安装，向量记忆功能不可用")


class LongTermMemory:
    """长期记忆系统"""
    
    def __init__(self, persist_dir: str = "data/vector_memory"):
        """
        初始化长期记忆
        
        Args:
            persist_dir: 持久化目录
        """
        self.persist_dir = persist_dir
        self.client = None
        self.collection = None
        
        if CHROMADB_AVAILABLE:
            self._initialize()
        else:
            logger.warning("ChromaDB 不可用，使用简单内存存储")
            self._memory_store = []
    
    def _initialize(self):
        """初始化 ChromaDB"""
        try:
            os.makedirs(self.persist_dir, exist_ok=True)
            
            self.client = chromadb.Client(Settings(
                persist_directory=self.persist_dir,
                anonymized_telemetry=False
            ))
            
            self.collection = self.client.get_or_create_collection(
                name="interaction_memory",
                metadata={"description": "AI 互动历史记忆"}
            )
            
            logger.info(f"长期记忆系统初始化完成: {self.persist_dir}")
        except Exception as e:
            logger.error(f"ChromaDB 初始化失败: {e}")
            CHROMADB_AVAILABLE = False
            self._memory_store = []
    
    def add_memory(
        self,
        content: str,
        topic: str,
        sentiment: str = "neutral",
        metadata: Optional[Dict] = None
    ) -> str:
        """
        添加记忆
        
        Args:
            content: 互动内容
            topic: 话题标签
            sentiment: 情感倾向 (positive/neutral/negative)
            metadata: 额外元数据
        
        Returns:
            memory_id
        """
        memory_data = {
            "content": content,
            "topic": topic,
            "sentiment": sentiment,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        if CHROMADB_AVAILABLE and self.collection:
            memory_id = f"mem_{datetime.now().timestamp()}"
            self.collection.add(
                documents=[content],
                metadatas=[{
                    "topic": topic,
                    "sentiment": sentiment,
                    "timestamp": memory_data["timestamp"],
                    **memory_data.get("metadata", {})
                }],
                ids=[memory_id]
            )
            logger.info(f"添加记忆: {memory_id}, topic={topic}")
            return memory_id
        else:
            self._memory_store.append(memory_data)
            return str(len(self._memory_store) - 1)
    
    def search_similar(
        self,
        query: str,
        topic: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        搜索相似记忆
        
        Args:
            query: 查询内容
            topic: 可选话题过滤
            limit: 返回数量
        
        Returns:
            相似记忆列表
        """
        if CHROMADB_AVAILABLE and self.collection:
            try:
                where = {"topic": topic} if topic else None
                results = self.collection.query(
                    query_texts=[query],
                    n_results=limit,
                    where=where
                )
                
                memories = []
                if results["documents"] and results["documents"][0]:
                    for i, doc in enumerate(results["documents"][0]):
                        memories.append({
                            "content": doc,
                            "topic": results["metadatas"][0][i].get("topic"),
                            "sentiment": results["metadatas"][0][i].get("sentiment"),
                            "timestamp": results["metadatas"][0][i].get("timestamp"),
                            "id": results["ids"][0][i]
                        })
                
                return memories
            except Exception as e:
                logger.error(f"搜索记忆失败: {e}")
                return []
        else:
            return self._simple_search(query, topic, limit)
    
    def _simple_search(self, query: str, topic: Optional[str], limit: int) -> List[Dict]:
        """简单搜索 (ChromaDB 不可用时)"""
        if topic:
            filtered = [m for m in self._memory_store if m.get("topic") == topic]
        else:
            filtered = self._memory_store
        
        return filtered[-limit:]
    
    def get_topic_summary(self, topic: str) -> Dict:
        """获取话题摘要"""
        if CHROMADB_AVAILABLE and self.collection:
            results = self.collection.get(where={"topic": topic})
            
            sentiments = [m.get("sentiment") for m in (results.get("metadatas") or [])]
            return {
                "topic": topic,
                "total_interactions": len(sentiments),
                "sentiment_distribution": {
                    "positive": sentiments.count("positive"),
                    "neutral": sentiments.count("neutral"),
                    "negative": sentiments.count("negative")
                }
            }
        else:
            topic_mems = [m for m in self._memory_store if m.get("topic") == topic]
            return {
                "topic": topic,
                "total_interactions": len(topic_mems),
                "sentiment_distribution": {}
            }
    
    def delete_old_memories(self, days: int = 90):
        """删除旧记忆"""
        if CHROMADB_AVAILABLE and self.collection:
            try:
                all_memories = self.collection.get()
                if not all_memories["ids"]:
                    return 0
                
                delete_count = 0
                for i, meta in enumerate(all_memories["metadatas"]):
                    timestamp = datetime.fromisoformat(meta.get("timestamp", "2020-01-01"))
                    if (datetime.now() - timestamp).days > days:
                        self.collection.delete(ids=[all_memories["ids"][i]])
                        delete_count += 1
                
                logger.info(f"删除旧记忆: {delete_count}")
                return delete_count
            except Exception as e:
                logger.error(f"删除记忆失败: {e}")
                return 0
        return 0
    
    def close(self):
        """关闭"""
        if CHROMADB_AVAILABLE and self.client:
            self.client = None
            logger.info("长期记忆系统已关闭")


class InteractionHistory:
    """互动历史记录器"""
    
    def __init__(self, memory: LongTermMemory):
        self.memory = memory
    
    def record_interaction(
        self,
        post_content: str,
        my_reply: str,
        topic: str,
        action: str = "comment"
    ):
        """记录互动"""
        sentiment = self._analyze_sentiment(my_reply)
        
        self.memory.add_memory(
            content=my_reply,
            topic=topic,
            sentiment=sentiment,
            metadata={
                "action": action,
                "post_content_preview": post_content[:100]
            }
        )
    
    def _analyze_sentiment(self, text: str) -> str:
        """简单情感分析"""
        positive_words = ["好", "棒", "强", "喜欢", "赞", "感谢", "收藏", "学到了"]
        negative_words = ["差", "烂", "不好", "失望"]
        
        for word in positive_words:
            if word in text:
                return "positive"
        for word in negative_words:
            if word in text:
                return "negative"
        return "neutral"
    
    def get_context_for_topic(self, topic: str, current_query: str) -> str:
        """
        获取话题上下文用于 Prompt 注入
        
        Returns:
            格式化的上下文字符串
        """
        memories = self.memory.search_similar(
            query=current_query,
            topic=topic,
            limit=3
        )
        
        if not memories:
            return ""
        
        context_parts = [f"你在该话题下的历史发言:"]
        for i, mem in enumerate(memories, 1):
            context_parts.append(f"{i}. {mem['content']}")
        
        return "\n".join(context_parts)


_global_memory = None

def get_long_term_memory(persist_dir: str = "data/vector_memory") -> LongTermMemory:
    """获取全局长期记忆"""
    global _global_memory
    if _global_memory is None:
        _global_memory = LongTermMemory(persist_dir)
    return _global_memory
