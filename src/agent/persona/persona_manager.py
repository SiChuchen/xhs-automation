"""
人设管理系统 - 管理 AI 角色设定
"""

import os
import json
import logging
from typing import Dict, Optional, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class Persona:
    """人设"""
    
    def __init__(
        self,
        name: str,
        age: Optional[int] = None,
        gender: Optional[str] = None,
        profession: Optional[str] = None,
        personality: Optional[List[str]] = None,
        interests: Optional[List[str]] = None,
        speaking_style: Optional[str] = None,
        system_prompt: Optional[str] = None,
        templates: Optional[Dict] = None
    ):
        self.name = name
        self.age = age
        self.gender = gender
        self.profession = profession
        self.personality = personality or []
        self.interests = interests or []
        self.speaking_style = speaking_style
        self.system_prompt = system_prompt
        self.templates = templates or {}
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "profession": self.profession,
            "personality": self.personality,
            "interests": self.interests,
            "speaking_style": self.speaking_style,
            "system_prompt": self.system_prompt,
            "templates": self.templates
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Persona":
        return cls(**{k: v for k, v in data.items() if k in [
            "name", "age", "gender", "profession", "personality",
            "interests", "speaking_style", "system_prompt", "templates"
        ]})
    
    def build_system_prompt(
        self,
        context: Optional[str] = None,
        topic: Optional[str] = None
    ) -> str:
        """构建完整系统提示词"""
        parts = []
        
        if self.system_prompt:
            parts.append(self.system_prompt)
        else:
            parts.append(f"你是一个{self.name}")
            
            if self.age:
                parts.append(f"{self.age}岁")
            if self.profession:
                parts.append(f"专业是{self.profession}")
            
            if self.personality:
                parts.append(f"性格特点: {', '.join(self.personality)}")
            
            if self.interests:
                parts.append(f"兴趣爱好: {', '.join(self.interests)}")
        
        if self.speaking_style:
            parts.append(f"说话风格: {self.speaking_style}")
        
        if context:
            parts.append(f"\n当前上下文:\n{context}")
        
        if topic:
            parts.append(f"\n当前话题: {topic}")
        
        return "\n\n".join(parts)


class PersonaManager:
    """人设管理器"""
    
    PRESET_PERSONAS = {
        "hot_topic_hunter": {
            "name": "热点追风者",
            "age": 20,
            "gender": "女",
            "profession": "计算机专业大学生",
            "personality": ["热情", "好奇", "乐于分享", "有洞察力"],
            "interests": ["AI工具", "效率软件", "编程技巧", "数码产品"],
            "speaking_style": "活泼亲切，喜欢用表情符号，分享欲强",
            "templates": {
                "comment": [
                    "学到了！感谢分享~ 🐶",
                    "太强了，收藏了！",
                    "这个也太实用了吧",
                    "终于找到了！",
                    "码住慢慢看"
                ]
            }
        },
        "tech_expert": {
            "name": "技术专家",
            "age": 28,
            "gender": "男",
            "profession": "软件工程师",
            "personality": ["专业", "严谨", "乐于助人", "追求效率"],
            "interests": ["编程", "架构设计", "开源项目", "AI技术"],
            "speaking_style": "专业但易懂，逻辑清晰，偶尔幽默",
            "templates": {
                "comment": [
                    "这个思路很棒，补充一点...",
                    "实测有效，赞！",
                    "收藏了，很实用",
                    "学到了，感谢分享"
                ]
            }
        },
        "lifestyle_blogger": {
            "name": "生活博主",
            "age": 25,
            "gender": "女",
            "profession": "自媒体博主",
            "personality": ["温柔", "细腻", "热爱生活", "审美在线"],
            "interests": ["生活方式", "美妆护肤", "家居好物", "旅行"],
            "speaking_style": "温柔亲切，分享生活点滴",
            "templates": {
                "comment": [
                    "也太美了吧！",
                    "太种草了！",
                    "好喜欢这种风格",
                    "mark一下",
                    "太实用了"
                ]
            }
        }
    }
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self._personas = {}
        self._load_presets()
        self._load_custom()
    
    def _load_presets(self):
        """加载预设人设"""
        for name, data in self.PRESET_PERSONAS.items():
            self._personas[name] = Persona.from_dict(data)
        logger.info(f"加载 {len(self.PRESET_PERSONAS)} 个预设人设")
    
    def _load_custom(self):
        """加载自定义人设"""
        persona_file = os.path.join(self.config_dir, "personas.json")
        if os.path.exists(persona_file):
            try:
                with open(persona_file, "r", encoding="utf-8") as f:
                    custom_data = json.load(f)
                
                for name, data in custom_data.items():
                    self._personas[name] = Persona.from_dict(data)
                
                logger.info(f"加载 {len(custom_data)} 个自定义人设")
            except Exception as e:
                logger.warning(f"加载自定义人设失败: {e}")
    
    def get_persona(self, name: str) -> Optional[Persona]:
        """获取人设"""
        return self._personas.get(name)
    
    def list_personas(self) -> List[str]:
        """列出所有人设"""
        return list(self._personas.keys())
    
    def add_persona(self, name: str, persona: Persona):
        """添加人设"""
        self._personas[name] = persona
        self._save_custom()
    
    def _save_custom(self):
        """保存自定义人设"""
        persona_file = os.path.join(self.config_dir, "personas.json")
        
        custom = {
            name: persona.to_dict()
            for name, persona in self._personas.items()
            if name not in self.PRESET_PERSONAS
        }
        
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(persona_file, "w", encoding="utf-8") as f:
                json.dump(custom, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存人设失败: {e}")
    
    def create_persona_from_config(
        self,
        config: Dict[str, Any]
    ) -> Persona:
        """从配置创建人设"""
        return Persona.from_dict(config)


_global_manager = None

def get_persona_manager(config_dir: str = "config") -> PersonaManager:
    """获取全局人设管理器"""
    global _global_manager
    if _global_manager is None:
        _global_manager = PersonaManager(config_dir)
    return _global_manager
