"""
图片理解模块 - 多模态理解
"""

import os
import base64
import logging
from typing import Dict, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ImageUnderstanding:
    """图片理解 - 使用多模态模型"""
    
    def __init__(self, provider: str = "openai", api_key: str = None, **kwargs):
        self.provider = provider
        self.api_key = api_key or os.environ.get("MULTIMODAL_API_KEY")
        self.model = kwargs.get("model", "gpt-4o")
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
    
    def describe_image(self, image_path: str) -> str:
        """
        描述图片内容
        
        Args:
            image_path: 图片路径
        
        Returns:
            图片描述
        """
        if not os.path.exists(image_path):
            return "图片不存在"
        
        try:
            if self.provider == "openai" and self._client:
                return self._describe_with_openai(image_path)
            else:
                return self._simple_describe(image_path)
        except Exception as e:
            logger.error(f"图片理解失败: {e}")
            return "无法理解图片"
    
    def _describe_with_openai(self, image_path: str) -> str:
        """使用 OpenAI 描述图片"""
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请简洁描述这张图片的内容，不超过50字"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=100
        )
        
        return response.choices[0].message.content
    
    def _simple_describe(self, image_path: str) -> str:
        """简单描述 (无 API 时)"""
        return f"图片: {Path(image_path).name}"
    
    def analyze_image_style(self, image_path: str) -> Dict:
        """
        分析图片风格
        
        Args:
            image_path: 图片路径
        
        Returns:
            风格分析结果
        """
        if not os.path.exists(image_path):
            return {"error": "图片不存在"}
        
        if self.provider == "openai" and self._client:
            return self._analyze_style_with_openai(image_path)
        
        return {"style": "unknown", "colors": [], "mood": "unknown"}
    
    def _analyze_style_with_openai(self, image_path: str) -> Dict:
        """使用 OpenAI 分析风格"""
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "分析这张图片的风格特点，以JSON格式返回: {\"style\": \"风格\", \"colors\": [\"主色调\"], \"mood\": \"氛围\"}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=100
        )
        
        content = response.choices[0].message.content
        try:
            import json
            return json.loads(content)
        except:
            return {"raw": content}


class ConsistencyChecker:
    """图片一致性校验器"""
    
    def __init__(self, vision_model: ImageUnderstanding = None):
        self.vision_model = vision_model or ImageUnderstanding()
        self._style_memory = {}  # 存储各话题的风格特征
    
    def record_style(
        self,
        topic: str,
        image_path: str,
        metadata: Optional[Dict] = None
    ):
        """记录话题的图片风格"""
        if not os.path.exists(image_path):
            return
        
        style = self.vision_model.analyze_image_style(image_path)
        
        if topic not in self._style_memory:
            self._style_memory[topic] = []
        
        self._style_memory[topic].append({
            "style": style,
            "metadata": metadata,
            "image_path": image_path
        })
        
        logger.info(f"记录话题风格: {topic}, style={style.get('style')}")
    
    def check_consistency(
        self,
        topic: str,
        candidate_image_path: str
    ) -> Dict:
        """
        检查候选图片与话题风格的一致性
        
        Args:
            topic: 话题
            candidate_image_path: 候选图片路径
        
        Returns:
            一致性检查结果
        """
        if not os.path.exists(candidate_image_path):
            return {"consistent": False, "reason": "图片不存在"}
        
        if topic not in self._style_memory or not self._style_memory[topic]:
            return {"consistent": True, "reason": "无历史风格记录"}
        
        candidate_style = self.vision_model.analyze_image_style(candidate_image_path)
        reference = self._style_memory[topic][-1]
        
        score = self._calculate_similarity(candidate_style, reference["style"])
        
        return {
            "consistent": score > 0.6,
            "similarity": score,
            "candidate_style": candidate_style,
            "reference_style": reference["style"]
        }
    
    def _calculate_similarity(self, style1: Dict, style2: Dict) -> float:
        """计算风格相似度"""
        score = 0.0
        
        if style1.get("style") and style2.get("style"):
            if style1["style"] == style2["style"]:
                score += 0.5
        
        if style1.get("mood") and style2.get("mood"):
            if style1["mood"] == style2["mood"]:
                score += 0.3
        
        colors1 = set(style1.get("colors", []))
        colors2 = set(style2.get("colors", []))
        if colors1 and colors2:
            overlap = len(colors1 & colors2)
            score += overlap / max(len(colors1 | colors2), 1) * 0.2
        
        return min(score, 1.0)
    
    def get_recommended_style(self, topic: str) -> Optional[Dict]:
        """获取话题推荐风格"""
        if topic not in self._style_memory:
            return None
        
        history = self._style_memory[topic]
        if not history:
            return None
        
        return history[-1].get("style", {})


def get_image_understanding(provider: str = "openai", **kwargs) -> ImageUnderstanding:
    """获取图片理解实例"""
    return ImageUnderstanding(provider=provider, **kwargs)


def get_consistency_checker(vision_model: ImageUnderstanding = None) -> ConsistencyChecker:
    """获取一致性校验器实例"""
    return ConsistencyChecker(vision_model)
