#!/usr/bin/env python3
"""
增强版图片管理器 - 集成RunningHub AI图片生成
基于原有image_manager.py扩展
"""

import os
import sys
import json
import random
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set, Any
from pathlib import Path

# 加载环境变量
def load_env_file():
    """从 .env 文件加载环境变量"""
    env_path = Path("/home/ubuntu/xhs-automation/.env")
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

load_env_file()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 尝试导入原有图片管理器
try:
    from scripts.image_manager import ImageManager
    BASE_IMAGE_MANAGER_AVAILABLE = True
    logger.info("成功导入基础图片管理器")
except ImportError as e:
    BASE_IMAGE_MANAGER_AVAILABLE = False
    logger.warning(f"无法导入基础图片管理器: {e}")

# 尝试导入RunningHub客户端
try:
    from scripts.runninghub_client import RunningHubClient
    RUNNINGHUB_CLIENT_AVAILABLE = True
    logger.info("成功导入RunningHub客户端")
except ImportError as e:
    RUNNINGHUB_CLIENT_AVAILABLE = False
    logger.warning(f"无法导入RunningHub客户端: {e}")


class EnhancedImageManager:
    """增强版图片管理器，集成RunningHub AI图片生成"""
    
    def __init__(self, 
                 config_path: str = None,
                 pexels_api_key: str = None,
                 runninghub_config: Dict = None):
        """
        初始化增强版图片管理器
        
        Args:
            config_path: 配置文件路径
            pexels_api_key: Pexels API密钥
            runninghub_config: RunningHub配置
                {
                    "enabled": true,
                    "consumer_api_key": "8d80d8df1e5d4585916c929c20db31ee",
                    "workflow_id": "2027074632334970882",
                    "workflow_json": "/home/ubuntu/else/runninghub-t2i/scc 文生图_api.json",
                    "daily_budget": 2.0,
                    "max_images_per_day": 10,
                    "prompt_templates": {
                        "academic_efficiency": "与'{topic}'相关的教育插图，清晰易懂，{style}",
                        "visual_creation": "'{topic}'主题的艺术创作，创意设计，{style}",
                        "geek_daily": "'{topic}'相关的技术场景，极客风格，{style}",
                        "hot_topics": "'{topic}'主题的现代插图，社交媒体风格，{style}"
                    }
                }
        """
        # 初始化基础图片管理器
        self.base_manager = None
        if BASE_IMAGE_MANAGER_AVAILABLE:
            try:
                self.base_manager = ImageManager(config_path, pexels_api_key)
                logger.info("基础图片管理器初始化成功")
            except Exception as e:
                logger.error(f"基础图片管理器初始化失败: {e}")
                self.base_manager = None
        else:
            logger.warning("基础图片管理器不可用，将仅使用AI生成功能")
        
        # RunningHub配置
        self.runninghub_config = runninghub_config or {}
        self.runninghub_enabled = self.runninghub_config.get('enabled', False)
        
        # 成本跟踪
        self.cost_tracker = {
            "daily_cost": 0.0,
            "monthly_cost": 0.0,
            "total_cost": 0.0,
            "images_generated": 0,
            "last_reset_date": datetime.now().date().isoformat()
        }
        
        # 加载成本记录
        self._load_cost_tracking()
        
        # 图片生成缓存（避免重复生成相同内容）
        self.generation_cache = {}
        
        # 话题到关键词的映射（用于图片选择）
        self.topic_keywords = self._init_topic_keywords()
        
        # 图片目录
        self.image_dir = Path("/home/ubuntu/xhs-automation/images")
        self.runninghub_image_dir = self.image_dir / "runninghub_generated"
        self.runninghub_image_dir.mkdir(exist_ok=True)
        
        # RunningHub客户端（必须在目录设置后初始化）
        self.runninghub_client = None
        if self.runninghub_enabled and RUNNINGHUB_CLIENT_AVAILABLE:
            self._init_runninghub_client()
        
        # 提示词模板
        self.prompt_templates = self.runninghub_config.get('prompt_templates', {
            "academic_efficiency": "与'{topic}'相关的教育插图，清晰易懂，适合学习分享，{style}",
            "visual_creation": "'{topic}'主题的艺术创作，创意设计，高质量细节，{style}",
            "geek_daily": "'{topic}'相关的技术场景，极客风格，现代感，{style}",
            "hot_topics": "'{topic}'主题的现代插图，社交媒体风格，吸引眼球，{style}"
        })
        
        logger.info(f"增强版图片管理器初始化完成 (RunningHub: {'启用' if self.runninghub_enabled else '禁用'})")
    
    def _init_runninghub_client(self):
        """初始化RunningHub客户端"""
        try:
            # 优先从环境变量读取，其次从配置文件读取
            consumer_api_key = os.environ.get('RUNNINGHUB_CONSUMER_API_KEY') or \
                              self.runninghub_config.get('consumer_api_key')
            enterprise_api_key = os.environ.get('RUNNINGHUB_ENTERPRISE_API_KEY') or \
                                self.runninghub_config.get('enterprise_api_key')
            
            if not consumer_api_key and not enterprise_api_key:
                logger.warning("未配置RunningHub API密钥，禁用RunningHub集成")
                logger.warning("请在 .env 文件中设置 RUNNINGHUB_CONSUMER_API_KEY")
                self.runninghub_enabled = False
                return
            
            workflow_id = self.runninghub_config.get('workflow_id', "2027074632334970882")
            workflow_json = self.runninghub_config.get('workflow_json', "/home/ubuntu/else/runninghub-t2i/scc 文生图_api.json")
            
            self.runninghub_client = RunningHubClient(
                consumer_api_key=consumer_api_key,
                enterprise_api_key=enterprise_api_key,
                output_dir=str(self.runninghub_image_dir)
            )
            
            logger.info(f"RunningHub客户端初始化成功 (工作流: {workflow_id})")
            
        except Exception as e:
            logger.error(f"初始化RunningHub客户端失败: {e}")
            self.runninghub_enabled = False
            self.runninghub_client = None
    
    def _load_cost_tracking(self):
        """加载成本跟踪记录"""
        cost_file = Path("/home/ubuntu/xhs-automation/config/cost_tracking.json")
        
        if cost_file.exists():
            try:
                with open(cost_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    
                    # 检查是否需要重置每日成本
                    last_reset = datetime.fromisoformat(saved_data.get("last_reset_date", "2000-01-01")).date()
                    today = datetime.now().date()
                    
                    if last_reset < today:
                        # 新的一天，重置每日成本
                        saved_data["daily_cost"] = 0.0
                        saved_data["last_reset_date"] = today.isoformat()
                        logger.info(f"新的一天，重置每日成本。上次重置: {last_reset}")
                    
                    self.cost_tracker.update(saved_data)
                    
            except Exception as e:
                logger.error(f"加载成本跟踪记录失败: {e}")
        
        # 确保目录存在
        cost_file.parent.mkdir(exist_ok=True)
    
    def _save_cost_tracking(self):
        """保存成本跟踪记录"""
        try:
            cost_file = Path("/home/ubuntu/xhs-automation/config/cost_tracking.json")
            with open(cost_file, 'w', encoding='utf-8') as f:
                json.dump(self.cost_tracker, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存成本跟踪记录失败: {e}")
    
    def _init_topic_keywords(self) -> Dict:
        """初始化话题到关键词的映射"""
        return {
            # 学术效率模块
            "编程技巧": ["programming", "coding", "python", "javascript", "developer"],
            "工具推荐": ["tools", "software", "apps", "productivity", "workflow"],
            "学习方法": ["study", "learning", "education", "students", "books"],
            "效率工具": ["productivity", "tools", "apps", "software", "workflow"],
            "学术写作": ["writing", "research", "academic", "paper", "study"],
            
            # 视觉创作模块
            "AI绘画": ["ai art", "digital art", "generative art", "artificial intelligence"],
            "游戏同人": ["game", "fan art", "gaming", "character design", "illustration"],
            "动漫壁纸": ["anime", "wallpaper", "manga", "cartoon", "art"],
            "科幻概念": ["scifi", "futuristic", "concept art", "space", "technology"],
            "数字艺术": ["digital art", "illustration", "graphic design", "creative"],
            
            # 极客日常模块
            "代码调试": ["debugging", "coding", "programming", "developer", "software"],
            "工作流优化": ["workflow", "productivity", "tools", "automation", "efficiency"],
            "桌面布置": ["desk setup", "workspace", "office", "ergonomics", "gaming setup"],
            "极客装备": ["gadgets", "tech", "electronics", "gear", "tools"],
            "技术分享": ["technology", "tech", "sharing", "community", "knowledge"],
            
            # 热点话题模块
            "行业趋势": ["trends", "industry", "technology", "future", "innovation"],
            "技术热点": ["hot", "trending", "technology", "news", "updates"],
            "社会议题": ["social", "discussion", "society", "issues", "opinion"],
            "校园生活": ["campus", "university", "students", "college", "education"]
        }
    
    def can_generate_image(self) -> bool:
        """检查是否可以生成新图片（预算和限制检查）"""
        if not self.runninghub_enabled or not self.runninghub_client:
            logger.debug("RunningHub未启用或客户端不可用")
            return False
        
        # 检查每日预算
        daily_budget = self.runninghub_config.get('daily_budget', 2.0)
        if self.cost_tracker["daily_cost"] >= daily_budget:
            logger.warning(f"已达到每日预算限制: {daily_budget}元 (已使用: {self.cost_tracker['daily_cost']}元)")
            return False
        
        # 检查每日生成数量限制
        max_per_day = self.runninghub_config.get('max_images_per_day', 10)
        daily_generated = self._get_today_generated_count()
        if daily_generated >= max_per_day:
            logger.warning(f"已达到每日生成数量限制: {max_per_day}张 (今日已生成: {daily_generated}张)")
            return False
        
        return True
    
    def _get_today_generated_count(self) -> int:
        """获取今日已生成图片数量"""
        today = datetime.now().date().isoformat()
        count = 0
        
        for cache_key, cache_data in self.generation_cache.items():
            generated_date = datetime.fromtimestamp(cache_data.get("generated_at", 0)).date()
            if generated_date.isoformat() == today:
                count += 1
        
        return count
    
    def _generate_prompt_for_topic(self, module: str, topic: str, style: str = "卡通风格") -> str:
        """为话题生成图片提示词"""
        # 获取模板
        template = self.prompt_templates.get(
            module, 
            f"'{topic}'主题的高质量图片，{style}"
        )
        
        # 替换变量
        prompt = template.replace("{topic}", topic).replace("{style}", style)
        
        # 添加小红书优化
        prompt += "，适合小红书分享，高分辨率，美观"
        
        return prompt
    
    def _record_image_usage(self, 
                          image_path: str, 
                          module: str, 
                          topic: str, 
                          is_ai_generated: bool = False):
        """记录图片使用历史"""
        try:
            # 更新使用记录文件
            usage_file = self.image_dir / "image_usage.json"
            if usage_file.exists():
                with open(usage_file, 'r', encoding='utf-8') as f:
                    usage_data = json.load(f)
            else:
                usage_data = {
                    "usage_history": [],
                    "last_image_date": None,
                    "image_use_count": 0,
                    "total_posts": 0
                }
            
            # 添加使用记录
            usage_record = {
                "timestamp": datetime.now().isoformat(),
                "image_path": image_path,
                "module": module,
                "topic": topic,
                "is_ai_generated": is_ai_generated,
                "use_count": 1,
                "last_used": datetime.now().isoformat()
            }
            
            usage_data["usage_history"].append(usage_record)
            usage_data["image_use_count"] += 1
            usage_data["last_image_date"] = datetime.now().date().isoformat()
            
            with open(usage_file, 'w', encoding='utf-8') as f:
                json.dump(usage_data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"图片使用记录已更新: {os.path.basename(image_path)}")
                
        except Exception as e:
            logger.error(f"记录图片使用历史失败: {e}")
    
    def select_image_for_content(self, 
                               module: str, 
                               topic: str, 
                               force_image: bool = False,
                               use_ai_if_needed: bool = True) -> Optional[str]:
        """
        增强版图片选择方法，支持AI图片生成
        
        Args:
            module: 内容模块 (academic_efficiency, visual_creation, etc.)
            topic: 具体话题
            force_image: 是否强制使用图片
            use_ai_if_needed: 当没有合适图片时是否使用AI生成
        
        Returns:
            图片路径或None（如果不使用图片）
        """
        logger.info(f"选择图片: 模块={module}, 话题={topic}")
        
        # 1. 首先尝试使用基础管理器的选择逻辑（如果有）
        if self.base_manager and hasattr(self.base_manager, 'select_image_for_content'):
            try:
                image_path = self.base_manager.select_image_for_content(module, topic, force_image)
                if image_path and os.path.exists(image_path):
                    logger.info(f"✅ 从基础库选择图片: {os.path.basename(image_path)}")
                    self._record_image_usage(image_path, module, topic, is_ai_generated=False)
                    return image_path
            except Exception as e:
                logger.warning(f"基础图片选择失败: {e}")
        
        # 2. 如果没有合适图片，且允许使用AI生成，则尝试生成新图片
        if use_ai_if_needed and self.can_generate_image():
            logger.info(f"🔄 尝试AI图片生成: {module} - {topic}")
            
            # 根据模块选择合适的风格
            style_mapping = {
                "academic_efficiency": "教育插画风格",
                "visual_creation": "艺术创作风格",
                "geek_daily": "现代科技风格",
                "hot_topics": "社交媒体风格"
            }
            
            style = style_mapping.get(module, "卡通风格")
            ai_image_path = self._generate_ai_image(module, topic, style)
            
            if ai_image_path:
                logger.info(f"✅ AI图片生成成功: {os.path.basename(ai_image_path)}")
                return ai_image_path
        
        # 3. 如果AI生成失败或不可用，尝试使用简单的人物图片
        character_images = self._get_character_images()
        if character_images:
            # 根据模块选择角色风格
            if module == 'visual_creation':
                # 视觉创作模块使用赛博版形象
                for img_path in character_images:
                    if "赛博" in img_path:
                        logger.info(f"✅ 使用赛博角色图片: {os.path.basename(img_path)}")
                        return img_path
            
            # 默认使用第一个角色图片
            logger.info(f"✅ 使用默认角色图片: {os.path.basename(character_images[0])}")
            return character_images[0]
        
        logger.warning("ℹ️  没有找到合适的图片，本次发布不使用图片")
        return None
    
    def _generate_ai_image(self, module: str, topic: str, style: str = "卡通风格") -> Optional[str]:
        """生成AI图片"""
        if not self.runninghub_enabled or not self.runninghub_client:
            return None
        
        try:
            # 生成缓存键
            cache_key = hashlib.md5(f"{module}_{topic}_{style}".encode()).hexdigest()
            
            # 检查缓存
            if cache_key in self.generation_cache:
                cached_image = self.generation_cache[cache_key]
                if os.path.exists(cached_image["path"]):
                    logger.info(f"使用缓存的AI生成图片: {topic}")
                    return cached_image["path"]
            
            # 生成提示词
            prompt = self._generate_prompt_for_topic(module, topic, style)
            
            logger.info(f"生成AI图片: '{prompt}'")
            
            # 调用RunningHub生成图片
            result = self.runninghub_client.generate_image_for_topic(
                topic=topic,
                module=module,
                style=style,
                width=1024,
                height=1024
            )
            
            if result.get("success") and result.get("image_paths"):
                image_path = result["image_paths"][0]
                cost = result.get("cost", 0.200)
                
                # 更新成本跟踪
                self.cost_tracker["daily_cost"] += cost
                self.cost_tracker["monthly_cost"] += cost
                self.cost_tracker["total_cost"] += cost
                self.cost_tracker["images_generated"] += 1
                
                # 保存到缓存
                self.generation_cache[cache_key] = {
                    "path": image_path,
                    "prompt": prompt,
                    "module": module,
                    "topic": topic,
                    "style": style,
                    "cost": cost,
                    "generated_at": datetime.now().timestamp()
                }
                
                # 保存成本记录
                self._save_cost_tracking()
                
                # 记录使用历史
                self._record_image_usage(image_path, module, topic, is_ai_generated=True)
                
                logger.info(f"AI图片生成成功: {image_path} (成本: {cost}元)")
                return image_path
            else:
                error_msg = result.get('error', '未知错误')
                logger.error(f"AI图片生成失败: {error_msg}")
                return None
                
        except Exception as e:
            logger.error(f"生成AI图片时发生错误: {e}")
            return None
    
    def generate_image_with_prompt(self, module: str, topic: str, prompt: str) -> Optional[str]:
        """
        使用自定义提示词生成AI图片
        
        Args:
            module: 内容模块 (用于记录和缓存)
            topic: 话题 (用于记录和缓存)
            prompt: 自定义图片提示词
        
        Returns:
            生成的图片路径，或None（如果生成失败）
        """
        if not self.runninghub_enabled or not self.runninghub_client:
            logger.warning("RunningHub未启用或客户端不可用，无法生成AI图片")
            return None
        
        try:
            # 将文案转换为视觉描述词
            logger.info(f"原始提示词: {prompt[:80]}...")
            visual_prompt = self._extract_visual_prompt(prompt)
            logger.info(f"使用RunningHub生成图片: {visual_prompt[:80]}...")
            
            # 调用 RunningHub 生成图片 (使用9:16竖版，更适合小红书)
            result = self.runninghub_client.generate_image(
                prompt=visual_prompt,
                workflow_id=self.runninghub_config.get('workflow_id', '2027074632334970882'),
                aspect_ratio="9:16",  # 竖版图片，适合小红书
                resolution="2k"       # 2K分辨率，保证清晰度
            )
            
            if result.get('success') and result.get('image_paths'):
                image_path = result['image_paths'][0]
                logger.info(f"RunningHub图片生成成功: {image_path}")
                return image_path
            else:
                error = result.get('error', '未知错误')
                logger.warning(f"RunningHub图片生成失败: {error}")
                return None
                
        except Exception as e:
            logger.error(f"生成图片时发生异常: {e}")
            return None
    
    def _extract_visual_prompt(self, text: str, max_retries: int = 2) -> str:
        """
        从文案中提取视觉描述词（Visual Prompts）
        
        使用 LLM 将中文文案转换为英文视觉描述词，
        提取人物形象、动作、环境、色彩风格等元素。
        优化：避免违规内容，确保图片生成成功。
        
        Args:
            text: 原始文案
            max_retries: 最大重试次数
            
        Returns:
            英文视觉描述词
        """
        import requests
        import json
        
        # 构建 prompt - 明确要求安全、合规的提示词
        extraction_prompt = f"""Convert this Chinese text to a SAFE, COMPLIANT English visual prompt for AI image generation.

Requirements:
- Output ONLY visual keywords: subject, setting, lighting, style
- MUST AVOID: celebrity names, copyrighted characters, political content, explicit content
- Use safe, general descriptors instead
- Example: young woman, cozy study room, warm lighting, illustration style, soft colors

Text: {text}

Visual:"""

        # 尝试使用环境变量中的 API Key
        api_key = os.environ.get("MINIMAX_API_KEY", "")
        
        if not api_key:
            logger.warning("MINIMAX_API_KEY 未配置，使用简单关键词提取")
            return self._simple_extract_keywords(text)
        
        try:
            url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "MiniMax-M2.5",
                "messages": [
                    {"role": "system", "content": "You are an expert at creating SAFE, COMPLIANT visual prompts for AI image generation. Never include celebrity names, copyrighted characters, or any potentially problematic content."},
                    {"role": "user", "content": extraction_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 256
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            result = response.json()
            
            if response.status_code == 200 and result.get("choices"):
                msg = result["choices"][0].get("message", {})
                # M2.5 模型返回内容可能在 reasoning_content 中
                visual_prompt = msg.get("content", "").strip() or msg.get("reasoning_content", "").strip()
                if visual_prompt:
                    # 后处理：确保提示词安全
                    visual_prompt = self._sanitize_prompt(visual_prompt)
                    logger.info(f"LLM 提取视觉描述词成功: {visual_prompt[:50]}...")
                    return visual_prompt
                logger.warning(f"LLM 返回内容为空")
                return self._simple_extract_keywords(text)
            else:
                logger.warning(f"LLM 提取失败: {result.get('base_resp', {}).get('status_msg', '未知错误')}")
                return self._simple_extract_keywords(text)
                
        except Exception as e:
            logger.warning(f"视觉描述词提取异常: {e}")
            return self._simple_extract_keywords(text)
    
    def _sanitize_prompt(self, prompt: str) -> str:
        """
        清理和规范化提示词，确保合规
        """
        import re
        
        # 需要避免的关键词（英文）
        blocked_keywords = [
            "celebrity", "famous person", "politician", "president",
            "donald trump", "biden", "mao", "xi", "government",
            "disney", "marvel", "pokemon", "hello kitty", "mickey",
            "nazi", "weapon", "blood", "gore", "nsfw", "explicit",
            "underwear", "bikini", "revealing", "nude", "naked"
        ]
        
        prompt_lower = prompt.lower()
        
        for keyword in blocked_keywords:
            if keyword in prompt_lower:
                # 替换为安全词汇
                prompt = prompt.replace(keyword, "[filtered]")
        
        # 移除任何被标记为过滤的内容
        prompt = re.sub(r'\[filtered\]', '', prompt)
        
        # 如果提示词太短或被清空，使用默认值
        if len(prompt.strip()) < 10:
            return "young woman, casual clothing, natural expression, soft lighting, illustration style"
        
        return prompt.strip()
    
    def _simple_extract_keywords(self, text: str) -> str:
        """
        简单的关键词提取（当 LLM 不可用时使用）
        
        从文案中提取核心视觉元素并转换为英文提示词
        """
        # 简单关键词映射
        keyword_map = {
            "研究生": "young woman student",
            "论文": "study, books, laptop",
            "代码": "computer, coding, programming",
            "学术": "academic, study environment",
            "学习": "studying, learning",
            "写作": "writing, typing",
            "电脑": "laptop, computer",
            "书": "books, textbook",
            "课堂": "classroom, lecture",
            "图书馆": "library, reading",
            "研究生": "graduate student",
            "分享": "friendly, approachable",
            "可爱": "cute, adorable",
            "漂亮": "beautiful, pretty",
            "美丽": "beautiful, elegant"
        }
        
        keywords = []
        text_lower = text.lower()
        
        for cn, en in keyword_map.items():
            if cn in text:
                keywords.append(en)
        
        if not keywords:
            keywords = ["young woman", "casual wear", "happy expression", "soft lighting"]
        
        # 添加风格后缀
        style_suffix = ", illustration style, flat design, vibrant colors, soft lighting, clean background"
        
        return ", ".join(keywords) + style_suffix
        
        # 检查是否可以生成新图片（预算和限制检查）
        if not self.can_generate_image():
            logger.warning("无法生成AI图片：预算或数量限制已达上限")
            return None
        
        try:
            # 生成缓存键（基于提示词）
            cache_key = hashlib.md5(f"{module}_{topic}_{prompt}".encode()).hexdigest()
            
            # 检查缓存
            if cache_key in self.generation_cache:
                cached_image = self.generation_cache[cache_key]
                if os.path.exists(cached_image["path"]):
                    logger.info(f"使用缓存的AI生成图片（自定义提示词）: {topic}")
                    return cached_image["path"]
            
            # 将文案转换为视觉描述词
            visual_prompt = self._extract_visual_prompt(prompt)
            logger.info(f"使用视觉描述词生成AI图片: '{visual_prompt[:80]}...'")
            
            # 调用RunningHub生成图片（使用视觉描述词）
            result = self.runninghub_client.generate_image(
                prompt=visual_prompt,
                width=768,
                height=1024,
                cache_key=cache_key  # 传递缓存键
            )
            
            if result.get("success") and result.get("image_paths"):
                image_path = result["image_paths"][0]
                cost = result.get("cost", 0.200)
                
                # 检查图片大小，超过2MB则压缩
                try:
                    from PIL import Image
                    file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
                    if file_size_mb > 2.0:
                        logger.info(f"图片大小 {file_size_mb:.2f}MB > 2MB，进行压缩...")
                        img = Image.open(image_path)
                        
                        # 转换为RGB（处理透明通道）
                        if img.mode in ('RGBA', 'LA', 'P'):
                            background = Image.new('RGB', img.size, (255, 255, 255))
                            if img.mode == 'P':
                                img = img.convert('RGBA')
                            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                            img = background
                        
                        # 压缩到小于2MB
                        output_path = image_path.replace('.png', '.jpg')
                        for quality in range(85, 40, -5):
                            img.save(output_path, 'JPEG', quality=quality, optimize=True)
                            if os.path.getsize(output_path) / (1024 * 1024) <= 2.0:
                                # 删除原文件
                                if os.path.exists(image_path) and image_path != output_path:
                                    os.remove(image_path)
                                image_path = output_path
                                logger.info(f"压缩成功: {os.path.getsize(image_path) / (1024 * 1024):.2f}MB")
                                break
                except Exception as compress_err:
                    logger.warning(f"图片压缩失败: {compress_err}")
                
                # 更新成本跟踪
                self.cost_tracker["daily_cost"] += cost
                self.cost_tracker["monthly_cost"] += cost
                self.cost_tracker["total_cost"] += cost
                self.cost_tracker["images_generated"] += 1
                
                # 保存到缓存
                self.generation_cache[cache_key] = {
                    "path": image_path,
                    "prompt": prompt,
                    "module": module,
                    "topic": topic,
                    "style": "custom",  # 自定义风格
                    "cost": cost,
                    "generated_at": datetime.now().timestamp()
                }
                
                # 保存成本记录
                self._save_cost_tracking()
                
                # 记录使用历史
                self._record_image_usage(image_path, module, topic, is_ai_generated=True)
                
                logger.info(f"AI图片生成成功（自定义提示词）: {image_path} (成本: {cost}元)")
                return image_path
            else:
                error_msg = result.get('error', '未知错误')
                logger.error(f"AI图片生成失败（自定义提示词）: {error_msg}")
                return None
                
        except Exception as e:
            logger.error(f"使用自定义提示词生成AI图片时发生错误: {e}")
            return None

    def generate_image_with_retry(self, module: str, topic: str, prompt: str = None, 
                                   max_retries: int = 3, retry_delay: int = 5) -> Tuple[Optional[str], Dict]:
        """
        带重试和本地备用逻辑的图片生成
        
        流程：
        1. 尝试 RunningHub 生成
        2. 失败后等待并重试（最多max_retries次）
        3. 每次失败后检查本地备用图片
        4. 所有尝试都失败返回失败信息（供告警使用）
        
        Args:
            module: 内容模块
            topic: 话题
            prompt: 自定义提示词（可选）
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
            
        Returns:
            (图片路径, 结果详情字典)
            - 成功时: (图片路径, {"status": "success", "source": "runninghub"/"local", ...})
            - 失败时: (None, {"status": "failed", "error": "...", "attempts": [...], ...})
        """
        import time
        
        result_detail = {
            "module": module,
            "topic": topic,
            "prompt": prompt,
            "attempts": [],
            "final_status": "unknown"
        }
        
        # 如果没有提供prompt，根据模块生成一个
        if not prompt:
            style_mapping = {
                "academic_efficiency": "教育插画风格，学生学习场景",
                "visual_creation": "艺术创作风格，创意设计",
                "geek_daily": "现代科技风格，数码设备",
                "hot_topics": "社交媒体风格，热点话题"
            }
            prompt = style_mapping.get(module, "卡通风格")
        
        # Step 1: 首次尝试 RunningHub 生成
        logger.info(f"[图片生成] 模块={module}, 话题={topic}, 开始第1次生成尝试")
        
        for attempt in range(1, max_retries + 1):
            attempt_info = {
                "attempt": attempt,
                "timestamp": datetime.now().isoformat(),
                "method": "runninghub",
                "prompt": prompt
            }
            
            # 尝试生成图片
            image_path = self.generate_image_with_prompt(module, topic, prompt)
            
            if image_path and os.path.exists(image_path):
                logger.info(f"[图片生成] 第{attempt}次尝试成功: {image_path}")
                result_detail["attempts"].append(attempt_info)
                result_detail["final_status"] = "success"
                result_detail["source"] = "runninghub"
                return image_path
            
            # 记录失败
            attempt_info["status"] = "failed"
            attempt_info["error"] = "生成失败或图片不存在"
            result_detail["attempts"].append(attempt_info)
            logger.warning(f"[图片生成] 第{attempt}次尝试失败")
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < max_retries:
                logger.info(f"[图片生成] 等待{retry_delay}秒后进行第{attempt+1}次尝试...")
                time.sleep(retry_delay)
        
        # 所有RunningHub尝试都失败后，尝试本地备用图片
        logger.warning(f"[图片生成] RunningHub {max_retries}次尝试全部失败，尝试本地备用图片")
        
        local_image = self._get_fallback_image(module)
        if local_image:
            logger.info(f"[图片生成] 使用本地备用图片: {local_image}")
            result_detail["final_status"] = "success"
            result_detail["source"] = "local_fallback"
            result_detail["fallback_image"] = local_image
            return local_image, result_detail
        
        # 记录本地图片也失败
        result_detail["local_fallback_status"] = "not_found"
        
        # 最后再尝试一次RunningHub（作为最终尝试）
        logger.info(f"[图片生成] 本地无备用图片，进行最终一次RunningHub尝试")
        final_attempt = {
            "attempt": max_retries + 1,
            "timestamp": datetime.now().isoformat(),
            "method": "runninghub_final",
            "prompt": prompt
        }
        
        image_path = self.generate_image_with_prompt(module, topic, prompt)
        if image_path and os.path.exists(image_path):
            logger.info(f"[图片生成] 最终尝试成功: {image_path}")
            result_detail["attempts"].append(final_attempt)
            result_detail["final_status"] = "success"
            result_detail["source"] = "runninghub_final"
            return image_path, result_detail
        
        # 彻底失败
        final_attempt["status"] = "failed"
        result_detail["attempts"].append(final_attempt)
        result_detail["final_status"] = "failed"
        
        # 获取失败详情用于告警
        result_detail["error_summary"] = {
            "total_attempts": max_retries + 1,
            "runninghub_failures": max_retries,
            "local_fallback": "not_available",
            "last_error": "所有生成方式均失败"
        }
        
        # 获取当前成本状态
        result_detail["cost_status"] = {
            "daily_cost": self.cost_tracker.get("daily_cost", 0),
            "monthly_cost": self.cost_tracker.get("monthly_cost", 0),
            "images_generated": self.cost_tracker.get("images_generated", 0)
        }
        
        logger.error(f"[图片生成] 所有尝试均失败，准备告警: module={module}, topic={topic}")
        return None, result_detail

    def _get_fallback_image(self, module: str) -> Optional[str]:
        """
        获取本地备用图片
        
        Args:
            module: 内容模块
            
        Returns:
            本地图片路径，或None（如果没有找到）
        """
        fallback_images = []
        
        # 1. 优先查找该模块对应的本地图片
        module_keywords = {
            "academic_efficiency": ["学习", "study", "book", "教育"],
            "visual_creation": ["创作", "art", "设计", "创意"],
            "geek_daily": ["科技", "tech", "数码", "电脑"],
            "hot_topics": ["社交", "social", "热点", "trend"]
        }
        
        keywords = module_keywords.get(module, [])
        
        # 扫描images目录
        if os.path.exists(self.image_dir):
            for file_path in self.image_dir.iterdir():
                if file_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    # 检查是否匹配模块关键词
                    filename_lower = file_path.name.lower()
                    if any(kw.lower() in filename_lower for kw in keywords):
                        fallback_images.append(str(file_path))
        
        # 2. 如果没有匹配的，使用人物形象图片
        if not fallback_images:
            character_images = self._get_character_images()
            if character_images:
                # 视觉创作使用赛博版，其他使用原版
                if module == "visual_creation":
                    for img in character_images:
                        if "赛博" in img or "cyber" in img.lower():
                            fallback_images.append(img)
                            break
                if not fallback_images and character_images:
                    fallback_images.append(character_images[0])
        
        # 3. 再没有就使用任何可用图片
        if not fallback_images:
            if os.path.exists(self.image_dir):
                for file_path in self.image_dir.iterdir():
                    if file_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                        # 排除AI生成的和测试图片
                        if 'runninghub' not in str(file_path) and 'test' not in file_path.name.lower():
                            fallback_images.append(str(file_path))
        
        if fallback_images:
            selected = random.choice(fallback_images)
            logger.info(f"[备用图片] 选择: {os.path.basename(selected)} (模块: {module})")
            return selected
        
        logger.warning(f"[备用图片] 未找到任何可用图片")
        return None

    def get_image_failure_alert_message(self, result_detail: Dict) -> str:
        """
        生成图片生成失败的告警消息
        
        Args:
            result_detail: generate_image_with_retry返回的详情字典
            
        Returns:
            格式化的告警消息
        """
        msg = f"""❌ **图片生成失败告警**

**模块**: {result_detail.get('module', 'N/A')}
**话题**: {result_detail.get('topic', 'N/A')}
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**尝试详情**:
"""
        for attempt in result_detail.get('attempts', []):
            method = attempt.get('method', 'unknown')
            status = attempt.get('status', 'unknown')
            msg += f"- 第{attempt.get('attempt')}次: {method} → {status}\n"
        
        cost = result_detail.get('cost_status', {})
        msg += f"""
**成本状态**:
- 今日消耗: ¥{cost.get('daily_cost', 0):.2f}
- 本月消耗: ¥{cost.get('monthly_cost', 0):.2f}
- 已生成图片: {cost.get('images_generated', 0)}张

**最终状态**: {result_detail.get('final_status', 'unknown')}
**图片来源**: {result_detail.get('source', 'N/A')}

请检查 RunningHub 服务状态和本地图片库。"""
        
        return msg
    
    def _get_character_images(self) -> List[str]:
        """获取人物形象图片列表"""
        character_images = []
        
        # 从配置文件中获取（如果基础管理器可用）
        if self.base_manager and hasattr(self.base_manager, 'config'):
            config = getattr(self.base_manager, 'config', {})
            visual_assets = config.get('visual_assets', {})
            character_paths = visual_assets.get('character_images', [])
            
            for path in character_paths:
                if os.path.exists(path):
                    character_images.append(path)
        
        # 如果配置中没有，扫描images目录
        if not character_images:
            for ext in ['.jpg', '.jpeg', '.png', '.gif']:
                for file_path in self.image_dir.glob(f'*{ext}'):
                    filename = file_path.name.lower()
                    if '原画' in filename or '赛博' in filename or 'character' in filename:
                        character_images.append(str(file_path))
        
        return character_images
    
    def should_use_image(self) -> bool:
        """
        判断本次发布是否应该使用图片
        
        修改为总是返回True，尽量使用图片，纯文字尽量少出现
        但仍保留频率记录用于统计
        """
        # 总是尝试使用图片
        return True
    
    def get_cost_stats(self) -> Dict:
        """获取成本统计信息"""
        today = datetime.now().date().isoformat()
        daily_budget = self.runninghub_config.get('daily_budget', 2.0)
        max_per_day = self.runninghub_config.get('max_images_per_day', 10)
        
        return {
            "runninghub_enabled": self.runninghub_enabled,
            "daily_budget": daily_budget,
            "daily_cost": round(self.cost_tracker["daily_cost"], 3),
            "budget_remaining": max(0, daily_budget - self.cost_tracker["daily_cost"]),
            "monthly_cost": round(self.cost_tracker["monthly_cost"], 3),
            "total_cost": round(self.cost_tracker["total_cost"], 3),
            "images_generated": self.cost_tracker["images_generated"],
            "today_generated": self._get_today_generated_count(),
            "max_per_day": max_per_day,
            "last_reset_date": self.cost_tracker["last_reset_date"],
            "generation_cache_size": len(self.generation_cache)
        }
    
    def get_usage_stats(self) -> Dict:
        """获取使用统计信息"""
        stats = self.get_cost_stats()
        
        # 添加基础管理器统计（如果可用）
        if self.base_manager and hasattr(self.base_manager, 'get_usage_stats'):
            try:
                base_stats = self.base_manager.get_usage_stats()
                stats.update(base_stats)
            except Exception as e:
                logger.warning(f"获取基础管理器统计失败: {e}")
        
        return stats
    
    def reset_daily_cost(self):
        """重置每日成本（用于测试或手动重置）"""
        self.cost_tracker["daily_cost"] = 0.0
        self.cost_tracker["last_reset_date"] = datetime.now().date().isoformat()
        self._save_cost_tracking()
        logger.info("每日成本已重置")


# 使用示例和测试
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="增强版图片管理器测试")
    parser.add_argument("--module", help="内容模块", default="visual_creation")
    parser.add_argument("--topic", help="话题", default="AI绘画")
    parser.add_argument("--config", help="配置文件路径", default=None)
    parser.add_argument("--stats", help="显示统计信息", action="store_true")
    parser.add_argument("--test-generate", help="测试AI图片生成", action="store_true")
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(level=logging.INFO)
    
    # RunningHub配置
    runninghub_config = {
        "enabled": True,
        "consumer_api_key": "8d80d8df1e5d4585916c929c20db31ee",
        "workflow_id": "2027074632334970882",
        "workflow_json": "/home/ubuntu/else/runninghub-t2i/scc 文生图_api.json",
        "daily_budget": 2.0,
        "max_images_per_day": 10,
        "prompt_templates": {
            "academic_efficiency": "与'{topic}'相关的教育插图，清晰易懂，{style}",
            "visual_creation": "'{topic}'主题的艺术创作，创意设计，{style}",
            "geek_daily": "'{topic}'相关的技术场景，极客风格，{style}",
            "hot_topics": "'{topic}'主题的现代插图，社交媒体风格，{style}"
        }
    }
    
    # 初始化管理器
    manager = EnhancedImageManager(
        config_path=args.config,
        runninghub_config=runninghub_config
    )
    
    if args.stats:
        stats = manager.get_usage_stats()
        print("📊 增强版图片管理器统计")
        print("=" * 60)
        
        print("🤖 AI生成统计:")
        print(f"  RunningHub启用: {stats.get('runninghub_enabled', False)}")
        print(f"  已生成图片: {stats.get('images_generated', 0)}张")
        print(f"  今日生成: {stats.get('today_generated', 0)}张")
        print(f"  今日成本: {stats.get('daily_cost', 0)}元")
        print(f"  剩余预算: {stats.get('budget_remaining', 0)}元")
        print(f"  总成本: {stats.get('total_cost', 0)}元")
        print(f"  缓存大小: {stats.get('generation_cache_size', 0)}")
        
        if 'local_images' in stats:
            print(f"\n📁 基础统计:")
            print(f"  本地图片: {stats['local_images']}张")
            print(f"  图片使用次数: {stats.get('image_use_count', 0)}次")
        
    elif args.test_generate:
        print(f"测试AI图片生成: {args.module} - {args.topic}")
        image_path = manager._generate_ai_image(args.module, args.topic, "卡通风格")
        
        if image_path:
            print(f"✅ AI图片生成成功: {image_path}")
        else:
            print("❌ AI图片生成失败")
    
    else:
        print(f"测试图片选择: {args.module} - {args.topic}")
        image_path = manager.select_image_for_content(args.module, args.topic)
        
        if image_path:
            print(f"✅ 选择的图片: {image_path}")
            
            # 检查是否为AI生成
            is_ai = "runninghub_generated" in image_path
            if is_ai:
                print(f"  类型: AI生成")
            else:
                print(f"  类型: 本地图片")
        else:
            print("ℹ️  没有找到合适的图片")