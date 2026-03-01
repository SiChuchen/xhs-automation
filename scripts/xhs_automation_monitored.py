#!/usr/bin/env python3
"""
小红书自动化发布系统 - 林晓芯人设版（监控增强版）
集成Webhook告警、Cookie监控、存储管理等监控功能
"""

import os
import sys
import json
import random
import datetime
import logging
import time
import threading
from typing import Dict, List, Tuple, Optional
import requests

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 尝试导入监控模块
try:
    from scripts.monitoring import MonitoringSystem
    MONITORING_AVAILABLE = True
except ImportError as e:
    MONITORING_AVAILABLE = False
    print(f"警告: 监控模块导入失败: {e}，将禁用监控功能")

# 尝试导入增强版图片管理器（支持RunningHub AI生成）
try:
    from scripts.enhanced_image_manager import EnhancedImageManager
    ENHANCED_IMAGE_MANAGER_AVAILABLE = True
    print("✅ 增强版图片管理器导入成功（支持RunningHub AI图片生成）")
except ImportError as e:
    ENHANCED_IMAGE_MANAGER_AVAILABLE = False
    print(f"警告: 增强版图片管理器导入失败: {e}，尝试导入基础图片管理器")

# 尝试导入基础图片管理器（备用）
try:
    from scripts.image_manager import ImageManager
    BASE_IMAGE_MANAGER_AVAILABLE = True
except ImportError as e:
    BASE_IMAGE_MANAGER_AVAILABLE = False
    print(f"警告: 基础图片管理器导入失败: {e}")

# 尝试导入LLM内容生成器
try:
    from scripts.llm_content_generator import LLMContentGenerator
    LLM_CONTENT_GENERATOR_AVAILABLE = True
    print("✅ LLM内容生成器导入成功")
except ImportError as e:
    LLM_CONTENT_GENERATOR_AVAILABLE = False
    print(f"警告: LLM内容生成器导入失败: {e}，将使用模板生成")

# 设置可用的图片管理器类型
IMAGE_MANAGER_AVAILABLE = ENHANCED_IMAGE_MANAGER_AVAILABLE or BASE_IMAGE_MANAGER_AVAILABLE

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/xhs-automation/logs/automation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CharacterPersona:
    """人物设定类"""
    
    def __init__(self, config_path: str, soul_path: str):
        """初始化人物设定"""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        with open(soul_path, 'r', encoding='utf-8') as f:
            self.soul_content = f.read()
        
        self.character = self.config['character']
        self.content_modules = self.config['content_modules']
        self.language_style = self.config['language_style']
        
        # 初始化图片管理器
        self.image_manager = None
        if IMAGE_MANAGER_AVAILABLE:
            try:
                # 从配置文件获取Pexels API Key（如果有）
                pexels_key = os.environ.get('PEXELS_API_KEY')  # 可以从环境变量获取
                
                # 优先使用增强版图片管理器（支持AI生成）
                if ENHANCED_IMAGE_MANAGER_AVAILABLE:
                    # 加载RunningHub配置
                    runninghub_config_path = os.path.join(
                        os.path.dirname(config_path), 
                        'runninghub_config.json'
                    )
                    runninghub_config = {}
                    
                    if os.path.exists(runninghub_config_path):
                        try:
                            with open(runninghub_config_path, 'r', encoding='utf-8') as f:
                                runninghub_config = json.load(f)
                            logger.info(f"加载RunningHub配置: {runninghub_config_path}")
                        except Exception as config_error:
                            logger.warning(f"加载RunningHub配置失败: {config_error}")
                            runninghub_config = {"enabled": False}
                    else:
                        logger.warning(f"RunningHub配置文件不存在: {runninghub_config_path}")
                        runninghub_config = {"enabled": False}
                    
                    # 初始化增强版图片管理器
                    self.image_manager = EnhancedImageManager(
                        config_path=config_path,
                        pexels_api_key=pexels_key,
                        runninghub_config=runninghub_config
                    )
                    logger.info("增强版图片管理器初始化成功（支持RunningHub AI图片生成）")
                
                # 如果增强版不可用，使用基础版
                elif BASE_IMAGE_MANAGER_AVAILABLE:
                    self.image_manager = ImageManager(config_path, pexels_api_key=pexels_key)
                    logger.info("基础图片管理器初始化成功")
                
            except Exception as e:
                logger.error(f"图片管理器初始化失败: {e}")
                self.image_manager = None
        else:
            logger.warning("图片管理器不可用，将使用简单图片选择")
        
    def get_random_topic(self) -> Tuple[str, str, List[str]]:
        """根据权重随机选择一个内容模块和话题"""
        modules = list(self.content_modules.keys())
        weights = [self.content_modules[m]['weight'] for m in modules]
        
        # 根据权重随机选择模块
        selected_module = random.choices(modules, weights=weights, k=1)[0]
        
        # 从该模块中随机选择一个话题
        topics = self.content_modules[selected_module]['topics']
        selected_topic = random.choice(topics)
        
        # 获取标签
        tags = self.content_modules[selected_module]['tags']
        
        return selected_module, selected_topic, tags
        
    def _init_llm_generator(self):
        """初始化 LLM 内容生成器"""
        if not LLM_CONTENT_GENERATOR_AVAILABLE:
            return None
        
        try:
            generator = LLMContentGenerator(provider='minimax')
            if generator.enabled:
                logger.info("LLM 内容生成器已启用")
                return generator
            else:
                logger.warning("LLM API 未配置，将使用模板生成")
                return None
        except Exception as e:
            logger.error(f"LLM 生成器初始化失败: {e}")
            return None
    
    def generate_content(self, module: str, topic: str, use_llm: bool = True) -> Tuple[str, str, str]:
        """生成标题、正文内容和图片提示词 - 支持LLM生成"""
        
        # 优先尝试 LLM 生成
        if use_llm:
            if not hasattr(self, '_llm_generator'):
                self._llm_generator = self._init_llm_generator()
            
            if hasattr(self, '_llm_generator') and self._llm_generator:
                try:
                    logger.info(f"🤖 使用 LLM 生成内容: {module} - {topic}")
                    llm_result = self._llm_generator.generate_title_and_content(module, topic)
                    
                    if llm_result and llm_result.get('content'):
                        title = llm_result.get('title', '')
                        content = llm_result.get('content', '')
                        tags = llm_result.get('tags', [])
                        
                        if not title:
                            signature = random.choice(self.language_style['signature_phrases'])
                            title = self._generate_natural_title(topic, signature)
                        
                        image_prompt = self._generate_image_prompt(module, topic, content)
                        
                        if tags:
                            self._llm_generated_tags = tags
                        
                        logger.info(f"🤖 LLM 内容生成成功")
                        return title, content, image_prompt
                except Exception as e:
                    logger.error(f"LLM 生成出错: {e}")
        
        # 模板生成（原始逻辑）
        logger.info(f"📝 使用模板生成内容: {module} - {topic}")
        signature = random.choice(self.language_style['signature_phrases'])
        title = self._generate_natural_title(topic, signature)
        content = self._generate_content_with_length_control(module, topic)
        image_prompt = self._generate_image_prompt(module, topic, content)
        
        return title, content, image_prompt
    
    def _generate_content_with_length_control(self, module: str, topic: str) -> str:
        """生成内容并控制字数"""
        
        # 技术术语用于丰富内容（添加默认值防止配置缺失）
        tech_terms = self.language_style.get('technical_terms', [
            '项目实践', '定期总结', '理论学习', '工具使用', '方法论'
        ])
        technical_terms = random.sample(tech_terms, min(2, len(tech_terms)))
        
        # 根据模块选择内容生成策略和字数控制
        if module == "academic_efficiency":
            content = self._generate_academic_content(topic, technical_terms)
            # 学术效率类：详细技术分享，300-500字
            content = self._adjust_content_length(content, "technical_detailed")
        elif module == "visual_creation":
            content = self._generate_visual_content(topic, technical_terms)
            # 视觉创作类：创意分享，250-400字
            content = self._adjust_content_length(content, "creative_medium")
        elif module == "geek_daily":
            content = self._generate_geek_content(topic, technical_terms)
            # 极客日常类：实用技巧分享，200-350字
            content = self._adjust_content_length(content, "practical_medium")
        elif module == "hot_topics":
            content = self._generate_hot_content(topic, technical_terms)
            # 热点话题：观点讨论，150-250字
            content = self._adjust_content_length(content, "discussion_short")
        else:
            content = self._generate_general_content(topic, technical_terms)
            # 通用内容：中等长度
            content = self._adjust_content_length(content, "general_medium")
        
        return content
    
    def _adjust_content_length(self, content: str, content_type: str) -> str:
        """根据内容类型调整字数"""
        
        # 目标字数范围
        target_ranges = {
            "technical_detailed": (300, 500),    # 详细技术分享
            "creative_medium": (250, 400),       # 创意分享中等
            "practical_medium": (200, 350),      # 实用技巧中等
            "discussion_short": (150, 250),      # 讨论话题较短
            "general_medium": (180, 300),        # 通用内容中等
            "simple_note": (80, 150)             # 简单吐槽/冒泡
        }
        
        current_length = len(content)
        target_min, target_max = target_ranges.get(content_type, (200, 300))
        
        # 如果内容在目标范围内，直接返回
        if target_min <= current_length <= target_max:
            return content
        
        # 如果内容太短，尝试扩展
        if current_length < target_min:
            # 添加一些通用内容扩展
            extensions = [
                "\n\n大家有什么经验也欢迎分享～",
                "\n\n希望这些分享对大家有帮助。",
                "\n\n技术领域变化很快，一起学习进步。",
                "\n\n欢迎交流讨论，共同探索。"
            ]
            # 添加扩展直到达到目标长度
            while current_length < target_min and extensions:
                extension = random.choice(extensions)
                content += extension
                current_length = len(content)
                extensions.remove(extension)  # 避免重复添加
        
        # 如果内容太长，适当截断（保持段落完整性）
        elif current_length > target_max:
            # 找到最后一个完整的句子结束位置
            last_period = content.rfind('。', 0, target_max)
            last_newline = content.rfind('\n', 0, target_max)
            
            # 优先在段落结束处截断
            if last_newline > target_max * 0.7:  # 如果在新行附近
                content = content[:last_newline].rstrip() + "..."
            elif last_period > target_max * 0.7:  # 如果在句号附近
                content = content[:last_period + 1]
            else:
                # 在目标最大值处截断，确保不切断词汇
                content = content[:target_max].rstrip() + "..."
        
        return content
    
    def _generate_image_prompt(self, module: str, topic: str, content: str) -> str:
        """根据内容生成图片提示词"""
        
        # 提取文案中的关键信息来生成匹配的提示词
        content_clean = content.replace('\n', ' ').strip()
        
        # 尝试从内容中提取核心关键词（去掉常见停用词）
        stop_words = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        words = content_clean.split()
        keywords = [w for w in words if w not in stop_words and len(w) > 1]
        
        # 取前5个有意义的词作为关键词
        key_terms = keywords[:5] if keywords else [topic]
        
        # 分析内容情感/类型
        content_lower = content.lower()
        if any(word in content_lower for word in ['分享', '推荐', '种草', '好物', '必备']):
            style_hint = "种草推荐风格，明亮温馨"
        elif any(word in content_lower for word in ['教程', '学习', '方法', '技巧', '攻略']):
            style_hint = "教学风格，清晰明了"
        elif any(word in content_lower for word in ['问题', '困扰', '烦恼', '崩溃', '难']):
            style_hint = "共鸣感插画，轻微夸张"
        elif any(word in content_lower for word in ['开心', '快乐', '幸福', '激动', '成功']):
            style_hint = "积极向上，明快活泼"
        elif any(word in content_lower for word in ['科技', '代码', '数码', '工具', '软件']):
            style_hint = "科技感，简约现代"
        else:
            style_hint = "通用插画，简洁美观"
        
        # 生成更贴合文案的提示词
        prompt_templates = [
            f"{' '.join(key_terms)}，{style_hint}，适合小红书配图",
            f"表达{' '.join(key_terms[:3])}的{style_hint}，视觉吸引人",
            f"关于{' '.join(key_terms[:3])}的{style_hint}插画，现代简约",
        ]
        
        prompt = random.choice(prompt_templates)
        
        return prompt
    
    def _generate_natural_title(self, topic: str, signature: str) -> str:
        """生成自然的标题"""
        
        title_strategies = [
            # 经验分享型
            f"最近在{topic}上的一些心得分享",
            f"关于{topic}，我总结了这些经验",
            f"在{topic}方面的一点小发现",
            
            # 问题解决型
            f"如何更好地{topic}？我的方法分享",
            f"解决{topic}问题的几个思路",
            f"{topic}过程中遇到的坑和解决方法",
            
            # 观点思考型
            f"对{topic}的一些新思考",
            f"{topic}：不仅仅是技术问题",
            f"从不同角度看{topic}",
            
            # 教程分享型
            f"{signature}{topic}的实用方法",
            f"分享几个{topic}的小技巧",
            f"{topic}的入门与进阶",
            
            # 简洁直接型
            f"聊聊{topic}这件事",
            f"{topic}的一些想法",
            f"关于{topic}的分享"
        ]
        
        return random.choice(title_strategies)
    

    
    def _generate_academic_content(self, topic: str, technical_terms: List[str]) -> str:
        """生成学术效率相关话题的内容"""
        
        content_strategies = [
            # 经验总结型
            f"""最近在学习和工作中深入研究了{topic}，发现了一些有意思的点。

刚开始接触{topic}时，总觉得很难系统掌握。后来通过{technical_terms[0] if len(technical_terms) > 0 else '项目实践'}的方式，逐渐找到了适合自己的方法。

我发现{topic}的关键在于建立清晰的知识框架。不要急于求成，从基础概念开始，逐步深入。比如可以先从简单的案例入手，理解核心原理，然后再尝试复杂应用。

另外，定期回顾也很重要。技术知识容易遗忘，通过{technical_terms[1] if len(technical_terms) > 1 else '定期总结'}可以巩固记忆。我习惯用笔记记录关键点，方便后续查阅。

在实际应用中，{topic}往往需要结合具体场景。不同项目有不同的需求，灵活调整方法很重要。多和同行交流，也能获得很多启发。""",
            
            # 方法论分享型
            f"""今天想分享一些关于{topic}的实用方法。

在计算机专业的学习中，{topic}是必须掌握的核心能力之一。我通过大量实践，总结出了一套相对高效的学习路径。

首先，理解{topic}的基本原理很重要。不要只停留在表面操作，要深入理解背后的逻辑。可以通过阅读文档、分析源码等方式加深理解。

其次，实践是最好的老师。我建议从小的项目开始，逐步增加复杂度。在实践中会遇到各种问题，这正是学习的好机会。

最后，保持学习的系统性。{topic}涉及的知识点很多，需要有条理地学习。可以制定学习计划，分阶段掌握不同内容。""",
            
            # 技巧分享型
            f"""分享几个{topic}方面的小技巧，希望对大家有帮助。

1. 利用工具提升效率：合适的工具能让{topic}事半功倍。比如使用代码片段库、自动化脚本等。
2. 建立知识体系：将{topic}相关的知识点系统整理，形成自己的知识地图。
3. 注重实践应用：理论知识需要通过{technical_terms[0] if len(technical_terms) > 0 else '实际项目'}来巩固。
4. 持续学习更新：技术发展很快，要关注{topic}领域的新动态。

这些都是我在日常学习和工作中的体会，大家有什么好的方法也欢迎分享～""",
            
            # 问题解决型
            f"""在{topic}过程中，经常会遇到一些问题。今天分享一下我的解决思路。

常见的问题包括概念理解不清、实践应用困难、效率不高等。针对这些问题，我尝试了一些方法：

- 对于概念问题，可以通过多种渠道学习，比如视频教程、技术博客、官方文档等，从不同角度理解同一个概念。
- 对于实践问题，建议从简单的例子开始，逐步增加复杂度。遇到具体技术难题时，善用搜索引擎和社区资源。
- 对于效率问题，{technical_terms[1] if len(technical_terms) > 1 else '优化工作流'}是关键。分析耗时环节，寻找改进点。

{topic}是一个需要持续学习和实践的领域，大家一起进步！"""
        ]
        
        return random.choice(content_strategies)
    
    def _generate_visual_content(self, topic: str, technical_terms: List[str]) -> str:
        """生成视觉创作相关话题的内容"""
        
        content_strategies = [
            # 创作经验型
            f"""最近在{topic}方面做了一些尝试，分享一下创作过程。

{topic}不仅仅是技术操作，更是创意表达的过程。在开始创作前，我会先明确想要表达的主题和情感基调。

技术层面，{topic}涉及到很多工具和方法。我常用的工具包括Photoshop、Blender等，但最重要的是找到适合自己的工作流。通过{technical_terms[0] if len(technical_terms) > 0 else '流程优化'}，可以大大提高创作效率。

在创意表达上，我比较注重细节和氛围营造。比如色彩搭配、构图平衡、光影效果等，这些细节往往决定作品的质感。

{topic}是一个不断探索的过程，每次创作都有新的发现和收获。保持好奇心和实验精神很重要。""",
            
            # 技术分享型
            f"""今天聊聊{topic}的技术实现。

{topic}的技术栈比较丰富，从传统的设计软件到现代的AI工具都有涉及。我个人的经验是，不要局限于某一种工具，要根据项目需求灵活选择。

比如在处理{technical_terms[0] if len(technical_terms) > 0 else '复杂效果'}时，可能需要结合多种工具的优势。学习不同工具的特点，能在创作中提供更多可能性。

另外，技术的学习需要循序渐进。从基础操作开始，逐步掌握高级功能。多参考优秀作品，分析其技术实现，也是很好的学习方法。

{topic}领域的技术更新很快，保持学习心态很重要。新的工具和方法不断出现，为我们提供了更多创作可能。""",
            
            # 审美讨论型
            f"""关于{topic}的审美思考。

在视觉创作中，技术是基础，审美是灵魂。{topic}不仅仅是工具的使用，更是美学表达的实践。

我比较欣赏简约而有张力的设计风格。在{topic}创作中，我会注重留白、对比、节奏等设计原则的应用。好的作品往往在细节处见功力。

色彩是视觉表达的重要元素。在{topic}中，色彩的选择和搭配需要仔细考量。不同的色彩组合能传达不同的情感和氛围。

{topic}的审美没有绝对标准，但有一些共通的原则。多观察、多思考、多实践，逐渐形成自己的审美体系。"""
        ]
        
        return random.choice(content_strategies)
    
    def _generate_geek_content(self, topic: str, technical_terms: List[str]) -> str:
        """生成极客日常相关话题的内容"""
        
        content_strategies = [
            # 工具分享型
            f"""分享一些{topic}方面的心得。

{topic}是我日常技术探索中经常关注的一个领域。在长期的使用和实践过程中，积累了一些经验体会。

工具的选择对{topic}的效果影响很大。好的工具组合能让工作更加高效。我尝试过不同的方案，发现适合自己的才是最好的。比如在{technical_terms[0] if len(technical_terms) > 0 else '特定应用场景'}中，某些工具的配合使用效果特别好。

工作流的优化也很关键。合理的流程设计可以减少不必要的重复劳动，提升整体效率。我习惯定期审视自己的工作流，寻找可以改进的地方。

问题解决能力在{topic}过程中同样重要。建立系统的问题排查思路，能够帮助快速定位原因并找到解决方案。

{topic}是一个需要持续学习和优化的领域，保持探索和实验的心态很重要。""",
            
            # 效率优化型
            f"""最近在优化{topic}方面的工作流，有一些收获分享给大家。

{topic}的优化可以从多个角度入手：
1. 工具层面：选择更适合当前需求的工具，有时候一个小工具的替换就能带来很大提升。
2. 流程层面：分析现有流程，消除不必要的环节，自动化重复性工作。
3. 习惯层面：养成良好的工作习惯，比如及时整理文档、规范命名等。

在实践{technical_terms[1] if len(technical_terms) > 1 else '具体优化'}时，我建议从小处着手。先优化一个具体的痛点，看到效果后再扩展到其他方面。

持续改进是{topic}优化的核心。技术环境在变化，我们的工作方式也需要不断调整。保持开放心态，乐于尝试新方法。""",
            
            # 问题解决型
            f"""在{topic}过程中，遇到过不少问题。今天总结一下常见的坑和解决方法。

常见问题包括：
- 工具配置复杂，环境问题频发
- 工作流不够顺畅，效率低下
- 学习曲线陡峭，上手困难

针对这些问题，我的经验是：
1. 文档很重要：仔细阅读官方文档，理解工具的设计理念
2. 社区资源：善用GitHub、Stack Overflow等社区，很多问题已经有现成解决方案
3. 逐步深入：不要想一次性掌握所有功能，从核心功能开始，逐步扩展

{topic}的学习和实践是一个渐进过程。遇到困难时，不要轻易放弃，多尝试不同方法，总会找到解决方案。"""
        ]
        
        return random.choice(content_strategies)
    
    def _generate_hot_content(self, topic: str, technical_terms: List[str]) -> str:
        """生成热点话题相关的内容"""
        
        content_strategies = [
            # 趋势分析型
            f"""最近对{topic}这个话题有一些思考。

{topic}作为当前的热点领域，引起了广泛关注。从技术发展的角度看，这背后有多个因素的推动。

一方面，技术进步为{topic}提供了新的可能。比如{technical_terms[0] if len(technical_terms) > 0 else '相关技术'}的发展，降低了{topic}的门槛，让更多人能够参与其中。

另一方面，市场需求也在变化。用户对{topic}的期待越来越高，这促使相关产品和服务不断创新。

从个人角度，我认为{topic}的发展应该注重实用性和可持续性。技术的价值最终要体现在解决实际问题上。

{topic}的未来还有很大想象空间，值得持续关注和思考。""",
            
            # 观点分享型
            f"""关于{topic}，我的一些看法。

{topic}最近成为大家讨论的焦点，我也在持续关注相关动态。作为一名技术学习者，我有几点感受想分享。

首先，{topic}的热度反映了技术发展的新方向。这不仅仅是短暂的热点，而是行业趋势的体现。

其次，在关注{topic}的同时，也要保持理性思考。新技术往往伴随着夸大宣传，需要甄别其中的真实价值。

另外，{topic}的应用场景值得深入探索。技术最终要服务于实际需求，找到合适的应用场景很重要。

{topic}是一个很好的学习机会，通过研究这个领域，可以了解技术发展的最新动态和思考方式。""",
            
            # 实践思考型
            f"""结合实践谈谈对{topic}的理解。

最近在项目中接触到了{topic}相关的内容，有了一些实际的体会。

{topic}的理论知识固然重要，但实践中的感受更加深刻。在实际应用中，往往会遇到理论中没有覆盖的问题。

比如在{technical_terms[1] if len(technical_terms) > 1 else '具体实施'}过程中，需要平衡技术先进性和实际可行性。有时候简单的方案反而更有效。

另外，{topic}的学习需要结合具体场景。脱离场景空谈技术，很难真正理解其价值。

从实践角度看，{topic}的掌握是一个渐进过程。先理解基本原理，再通过项目实践加深认识，最后形成自己的理解体系。"""
        ]
        
        return random.choice(content_strategies)
    
    def _generate_general_content(self, topic: str, technical_terms: List[str]) -> str:
        """生成通用话题的内容"""
        
        return f"""今天分享一下关于{topic}的一些想法。

{topic}是一个很有意思的话题，涉及到多个方面的内容。在探索过程中，我积累了一些经验。

首先，理解{topic}的核心概念很重要。这为后续的学习和实践打下基础。

其次，实践是最好的学习方法。通过{technical_terms[0] if len(technical_terms) > 0 else '实际操作'}，可以加深对{topic}的理解。

另外，保持学习的心态很重要。{topic}领域在不断发展和变化，需要持续关注新动态。

希望这些分享对大家有帮助，欢迎一起交流讨论～"""
        
    def select_image(self, module: str, topic: str = None, image_prompt: str = None) -> str:
        """
        根据模块和话题选择图片
        
        如果图片管理器可用，则使用智能图片选择
        否则使用简单的人物图片选择
        
        带重试逻辑：
        1. 尝试 RunningHub 生成（最多3次）
        2. 每次失败后检查本地备用图片
        3. 所有尝试失败后发送告警
        
        Args:
            module: 内容模块
            topic: 话题
            image_prompt: 图片提示词（可选，用于AI图片生成）
        """
        # 记录提示词（如果提供）
        if image_prompt:
            logger.info(f"图片提示词: {image_prompt[:80]}...")
        
        # 如果图片管理器可用，使用智能图片选择
        if self.image_manager and topic:
            # 优先尝试使用新的重试方法（带本地备用逻辑）
            if hasattr(self.image_manager, 'generate_image_with_retry'):
                try:
                    logger.info(f"[图片选择] 使用重试逻辑: 模块={module}, 话题={topic}")
                    image_path, result_detail = self.image_manager.generate_image_with_retry(
                        module, topic, image_prompt, max_retries=3, retry_delay=5
                    )
                    
                    if image_path and os.path.exists(image_path):
                        source = result_detail.get('source', 'unknown')
                        logger.info(f"✅ 图片获取成功: {os.path.basename(image_path)} (来源: {source})")
                        return image_path
                    
                    # 所有方式都失败了，发送告警
                    logger.error(f"[图片选择] 所有方式尝试失败，准备发送告警")
                    if self.monitoring:
                        alert_msg = self.image_manager.get_image_failure_alert_message(result_detail)
                        self.monitoring.send_alert(
                            "❌ 图片生成失败",
                            alert_msg,
                            "critical"
                        )
                        
                except Exception as e:
                    logger.warning(f"使用重试方法失败: {e}")
            
            # 检查是否有使用提示词生成图片的方法（备用）
            if image_prompt and hasattr(self.image_manager, 'generate_image_with_prompt'):
                try:
                    # 尝试使用提示词生成图片
                    image_path = self.image_manager.generate_image_with_prompt(
                        module, topic, image_prompt
                    )
                    if image_path:
                        logger.info(f"AI图片生成: 模块={module}, 使用自定义提示词")
                        return image_path
                except Exception as e:
                    logger.warning(f"使用提示词生成图片失败: {e}")
            
            # 使用常规图片选择
            image_path = self.image_manager.select_image_for_content(module, topic)
            if image_path:
                logger.info(f"智能图片选择: 模块={module}, 话题={topic}, 图片={os.path.basename(image_path)}")
                return image_path
            else:
                logger.info(f"智能图片选择: 本次发布不使用图片")
                return ""
        
        # 备用方案：使用简单的人物图片选择
        logger.warning("使用简单图片选择（智能图片管理器不可用或无话题）")
        
        # 优先使用小图片（避免上传超时）
        small_images = [
            "/images/test_simple.jpg",  # 14KB
            "/images/test.jpg",          # 14KB  
            "/images/test_vertical.jpg", # 22KB
            "/images/character_original_vertical.jpg",  # 123KB
            "/images/character_cyber_vertical.jpg",   # 192KB
            "/images/001原画.jpg",  # 87KB
        ]
        
        for img in small_images:
            full_path = "/home/ubuntu/xhs-automation/images/" + img.replace("/images/", "")
            if os.path.exists(full_path):
                logger.info(f"✅ 使用小图片: {img}")
                return img
        
        character_images = self.config['visual_assets']['character_images']
        
        # 根据模块选择不同的图片风格
        if module == 'visual_creation':
            # 视觉创作模块使用赛博版形象
            if len(character_images) >= 2:
                return character_images[1]
        
        # 默认使用第一个形象
        return character_images[0] if character_images else ""

class XiaohongshuPublisher:
    """小红书发布器"""
    
    def __init__(self, api_url: str = "http://localhost:18060/api/v1"):
        self.api_url = api_url
    
    def check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            response = requests.get(f"{self.api_url}/login/status", timeout=30)
            data = response.json()
            
            if data.get('success'):
                logger.info(f"登录状态: {data.get('data', {}).get('username', '已登录')}")
                return True
            else:
                logger.error(f"登录状态检查失败: {data.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"登录状态检查请求失败: {e}")
            return False
    
    def _normalize_image_path(self, image_path: str) -> str:
        """
        标准化图片路径 - 将完整路径转换为容器内路径
        容器将 /home/ubuntu/xhs-automation/images 映射到 /images
        """
        if not image_path:
            return image_path
        
        # 本地项目图片目录
        local_image_dir = "/home/ubuntu/xhs-automation/images"
        container_image_dir = "/app/images"
        
        # 如果是完整路径，转换为容器内路径
        if image_path.startswith(local_image_dir):
            # /home/ubuntu/xhs-automation/images/xxx.jpg -> /images/xxx.jpg
            return container_image_dir + "/" + os.path.basename(image_path)
        
        # 如果已经是 /images/xxx 或 /tmp/xxx 格式，直接返回
        if image_path.startswith("/images/") or image_path.startswith("/tmp/"):
            return image_path
        
        # 其他情况，假设是相对于图片目录的路径
        return container_image_dir + "/" + os.path.basename(image_path)
    
    def publish_note(self, title: str, content: str, image_path: str, tags: List[str] = None, max_retries: int = 3) -> Dict:
        """发布笔记（带重试机制）"""
        payload = {
            "title": title,
            "content": content
        }
        
        # 标准化图片路径
        normalized_image_path = self._normalize_image_path(image_path)
        
        # 如果有图片路径，则添加图片
        if normalized_image_path and normalized_image_path.strip():
            payload["images"] = [normalized_image_path]
            logger.info(f"图片路径（已标准化）: {normalized_image_path}")
        else:
            logger.info("本次发布不使用图片")
        
        if tags:
            payload["tags"] = tags[:5]  # 限制标签数量
        
        # 重试机制
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"发布笔记 (尝试 {attempt}/{max_retries})...")
                response = requests.post(
                    f"{self.api_url}/publish",
                    json=payload,
                    timeout=120
                )
                data = response.json()
                
                if data.get('success'):
                    logger.info(f"发布成功! Post ID: {data.get('data', {}).get('post_id', 'Unknown')}")
                    return data
                else:
                    error_msg = data.get('error', 'Unknown error')
                    logger.warning(f"发布失败: {error_msg} (尝试 {attempt}/{max_retries})")
                    last_error = error_msg
                    
                    # 如果是客户端错误（4xx），不重试
                    if response.status_code >= 400 and response.status_code < 500:
                        logger.error(f"客户端错误，不重试: {response.status_code}")
                        break
                    
            except requests.exceptions.Timeout:
                logger.warning(f"发布请求超时 (尝试 {attempt}/{max_retries})")
                last_error = "请求超时"
            except Exception as e:
                logger.warning(f"发布请求失败: {e} (尝试 {attempt}/{max_retries})")
                last_error = str(e)
            
            # 重试前等待
            if attempt < max_retries:
                wait_time = 2 ** attempt  # 指数退避: 2s, 4s
                logger.info(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
        
        logger.error(f"发布最终失败: {last_error}")
        return {"success": False, "error": last_error}

class MonitoringScheduler:
    """监控调度器，定期执行监控任务"""
    
    def __init__(self, monitoring_system):
        self.monitoring = monitoring_system
        self.running = False
        self.thread = None
        
    def start(self):
        """启动监控调度器"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        logger.info("监控调度器已启动")
    
    def stop(self):
        """停止监控调度器"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
        logger.info("监控调度器已停止")
    
    def _run_scheduler(self):
        """运行监控调度器主循环"""
        last_system_check = time.time()
        last_cookie_check = time.time()
        last_storage_cleanup = time.time()
        
        # 监控检查间隔（秒）
        SYSTEM_CHECK_INTERVAL = 3600  # 1小时
        COOKIE_CHECK_INTERVAL = 86400  # 24小时
        STORAGE_CLEANUP_INTERVAL = 86400  # 24小时
        
        while self.running:
            current_time = time.time()
            
            # 系统状态检查
            if current_time - last_system_check >= SYSTEM_CHECK_INTERVAL:
                try:
                    logger.info("执行定期系统状态检查...")
                    self.monitoring.check_system_status()
                    last_system_check = current_time
                except Exception as e:
                    logger.error(f"系统状态检查失败: {e}")
            
            # Cookie状态检查
            if current_time - last_cookie_check >= COOKIE_CHECK_INTERVAL:
                try:
                    logger.info("执行定期Cookie状态检查...")
                    self.monitoring.check_cookie_status()
                    last_cookie_check = current_time
                except Exception as e:
                    logger.error(f"Cookie状态检查失败: {e}")
            
            # 存储清理
            if current_time - last_storage_cleanup >= STORAGE_CLEANUP_INTERVAL:
                try:
                    logger.info("执行定期存储清理...")
                    self.monitoring.manage_storage()
                    last_storage_cleanup = current_time
                except Exception as e:
                    logger.error(f"存储清理失败: {e}")
            
            # 休眠1分钟
            time.sleep(60)

class AutomationManager:
    """自动化管理器（监控增强版）"""
    
    def __init__(self):
        config_path = "/home/ubuntu/xhs-automation/config/publish_config.json"
        soul_path = "/home/ubuntu/xhs-automation/config/soul.md"
        
        self.persona = CharacterPersona(config_path, soul_path)
        self.publisher = XiaohongshuPublisher()
        
        # 发布记录文件
        self.records_file = "/home/ubuntu/xhs-automation/logs/publish_records.json"
        
        # 登录状态跟踪（防止重复告警）
        self._last_login_status = None
        self._login_alert_cooldown = 300  # 告警冷却时间（秒）
        self._last_login_alert_time = 0
        
        # 初始化监控系统
        self.monitoring = None
        self.monitoring_scheduler = None
        if MONITORING_AVAILABLE:
            try:
                self.monitoring = MonitoringSystem()
                self.monitoring_scheduler = MonitoringScheduler(self.monitoring)
                logger.info("监控系统初始化成功")
            except Exception as e:
                logger.error(f"监控系统初始化失败: {e}")
        else:
            logger.warning("监控功能不可用，将跳过所有监控功能")
    
    def load_records(self) -> List[Dict]:
        """加载发布记录"""
        if os.path.exists(self.records_file):
            with open(self.records_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def save_record(self, record: Dict):
        """保存发布记录"""
        records = self.load_records()
        records.append(record)
        
        with open(self.records_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    
    def send_publish_notification(self, success: bool, title: str, error: str = None):
        """发送发布结果通知"""
        if not self.monitoring:
            return
        
        if success:
            self.monitoring.send_alert(
                "发布成功",
                f"标题: {title}\n时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "info"
            )
        else:
            self.monitoring.send_alert(
                "发布失败",
                f"标题: {title}\n错误: {error}\n时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "critical"
            )
    
    def should_publish_now(self) -> bool:
        """根据配置判断是否应该发布"""
        # 重置最佳时间中心点
        self.best_time_center = None
        self.current_check_time = None
        
        records = self.load_records()
        
        if not records:
            return True
        
        # 获取最近一次发布时间
        latest_record = records[-1]
        latest_time = datetime.datetime.fromisoformat(latest_record['timestamp'].replace('Z', '+00:00'))
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # 转换为本地时间比较
        latest_local = latest_time.astimezone()
        now_local = now.astimezone()
        
        # 存储当前检查时间（用于计算抖动）
        self.current_check_time = now_local
        
        # 检查最小间隔
        hours_since_last = (now_local - latest_local).total_seconds() / 3600
        min_interval = self.persona.config['publishing']['min_interval_hours']
        
        if hours_since_last < min_interval:
            logger.info(f"距离上次发布仅{hours_since_last:.1f}小时，未达到最小间隔{min_interval}小时")
            return False
        
        # 检查每日最大发布数 (只统计成功的发布)
        today = now_local.date()
        today_posts = len([r for r in records 
                          if r.get('success', False) and 
                          datetime.datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')).astimezone().date() == today])
        
        max_posts = self.persona.config['publishing']['max_posts_per_day']
        if today_posts >= max_posts:
            logger.info(f"今日已成功发布{today_posts}次，达到每日上限{max_posts}")
            return False
        
        # 检查最佳发布时间
        best_times = self.persona.config['publishing']['best_times']
        current_time_str = now_local.strftime("%H:%M")
        
        # 简单判断：如果当前时间接近最佳时间，则发布
        for best_time in best_times:
            best_hour, best_minute = map(int, best_time.split(':'))
            current_hour, current_minute = map(int, current_time_str.split(':'))
            
            # 允许前后30分钟
            time_diff = abs((current_hour * 60 + current_minute) - (best_hour * 60 + best_minute))
            if time_diff <= 30:
                logger.info(f"当前时间{current_time_str}接近最佳发布时间{best_time}")
                # 记录最佳时间中心点（今天的这个时间）
                self.best_time_center = now_local.replace(hour=best_hour, minute=best_minute, second=0, microsecond=0)
                return True
        
        logger.info(f"当前时间{current_time_str}不在最佳发布时间范围内")
        return False
    
    def run_publish_cycle(self):
        """执行一次发布周期（带整体重试机制）"""
        logger.info("开始发布周期检查...")
        
        # 整体重试机制 - 最多尝试2次
        max_cycle_retries = 2
        cycle_retry_delay = 300  # 5分钟后重试
        
        for cycle_attempt in range(1, max_cycle_retries + 1):
            if cycle_attempt > 1:
                logger.info(f"发布周期重试 ({cycle_attempt}/{max_cycle_retries})，等待 {cycle_retry_delay} 秒...")
                time.sleep(cycle_retry_delay)
            
            cycle_result = self._execute_publish_cycle()
            
            if cycle_result:
                return True
            else:
                logger.warning(f"发布周期第 {cycle_attempt} 次尝试失败")
        
        # 所有重试都失败
        logger.error("发布周期多次失败，放弃本次发布")
        return False
    
    def _execute_publish_cycle(self) -> bool:
        """执行发布周期的核心逻辑"""
        
        # 1. 检查登录状态
        current_login_status = self.publisher.check_login_status()
        
        if not current_login_status:
            logger.error("未登录或登录状态失效，请重新登录")
            
            # 发送登录失败告警（只在状态变化时发送，或冷却时间后发送）
            current_time = time.time()
            should_send_alert = False
            
            # 首次检测到失效 或 超过冷却时间
            if self._last_login_status is None:
                should_send_alert = True
            elif self._last_login_status == True:  # 从正常变为失效
                should_send_alert = True
            elif (current_time - self._last_login_alert_time) > self._login_alert_cooldown:
                should_send_alert = True
            
            if should_send_alert and self.monitoring:
                self.monitoring.send_alert(
                    "登录状态失效",
                    "小红书登录状态失效，需要重新扫码登录",
                    "critical"
                )
                self._last_login_alert_time = current_time
            
            self._last_login_status = False
            return False
        
        # 记录登录状态正常
        if self._last_login_status != True:
            logger.info("登录状态已恢复正常")
            if self.monitoring:
                self.monitoring.send_alert(
                    "登录状态恢复",
                    "小红书登录状态已恢复正常",
                    "info"
                )
        self._last_login_status = True
        
        # 2. 判断是否应该发布
        if not self.should_publish_now():
            logger.info("当前不符合发布条件，跳过")
            return False
        
        # 2.5 发布时间抖动（Cron Jitter）
        if self.best_time_center is not None:
            now = datetime.datetime.now(datetime.timezone.utc).astimezone()
            window_end = self.best_time_center + datetime.timedelta(minutes=30)
            remaining_window_seconds = (window_end - now).total_seconds()
            
            if remaining_window_seconds > 0:
                max_jitter_seconds = min(1800, remaining_window_seconds)  # 最多30分钟
                if max_jitter_seconds > 0:
                    jitter_seconds = random.randint(0, int(max_jitter_seconds))
                    logger.info(f"发布时间抖动: 随机延迟 {jitter_seconds} 秒 ({jitter_seconds/60:.1f} 分钟)")
                    time.sleep(jitter_seconds)
                else:
                    logger.info("发布时间抖动: 剩余窗口时间不足，跳过延迟")
            else:
                logger.warning("发布时间抖动: 已超出最佳时间窗口，立即发布")
        else:
            logger.info("发布时间抖动: 非最佳时间发布，不应用抖动")
        
        # 3. 生成内容
        module, topic, tags = self.persona.get_random_topic()
        title, content, image_prompt = self.persona.generate_content(module, topic)
        image_path = self.persona.select_image(module, topic, image_prompt)
        
        logger.info(f"生成内容 - 模块: {module}, 话题: {topic}")
        logger.info(f"标题: {title}")
        logger.info(f"内容长度: {len(content)} 字符")
        logger.info(f"图片提示词: {image_prompt[:80]}..." if image_prompt and len(image_prompt) > 80 else f"图片提示词: {image_prompt}")
        logger.info(f"图片路径: {image_path}")
        logger.info(f"标签: {', '.join(tags[:3])}...")
        
        # 4. 发布内容
        result = self.publisher.publish_note(title, content, image_path, tags)
        
        # 5. 发送发布结果通知
        self.send_publish_notification(
            success=result.get('success', False),
            title=title,
            error=result.get('error')
        )
        
        # 6. 记录结果
        record = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "module": module,
            "topic": topic,
            "title": title,
            "image": image_path,
            "tags": tags,
            "success": result.get('success', False),
            "post_id": result.get('data', {}).get('post_id'),
            "error": result.get('error')
        }
        
        self.save_record(record)
        
        if result.get('success'):
            logger.info("发布周期完成，发布成功!")
            return True
        else:
            logger.error(f"发布周期完成，发布失败: {result.get('error')}")
            return False
    
    def run_continuous(self, check_interval_minutes: int = 60):
        """持续运行自动化（带监控）"""
        logger.info(f"启动自动化发布系统，检查间隔: {check_interval_minutes}分钟")
        logger.info(f"人物设定: {self.persona.character['name']} ({self.persona.character['nickname']})")
        
        # 启动监控调度器
        if self.monitoring_scheduler:
            self.monitoring_scheduler.start()
            
            # 运行一次全面检查
            try:
                logger.info("执行首次全面系统检查...")
                self.monitoring.run_comprehensive_check()
            except Exception as e:
                logger.error(f"首次全面检查失败: {e}")
        
        # 运行一次Cookie检查
        if self.monitoring:
            try:
                logger.info("检查Cookie状态...")
                cookie_status = self.monitoring.check_cookie_status()
                logger.info(f"Cookie状态: {cookie_status.get('message', '未知')}")
            except Exception as e:
                logger.error(f"Cookie检查失败: {e}")
        
        while True:
            try:
                self.run_publish_cycle_with_timeout(timeout_seconds=600)
            except Exception as e:
                logger.error(f"发布周期执行异常: {e}")
                
                # 发送异常告警
                if self.monitoring:
                    self.monitoring.send_alert(
                        "发布周期异常",
                        f"发布周期执行异常: {str(e)}",
                        "critical"
                    )
        
        # 等待固定间隔
        logger.info(f"等待{check_interval_minutes}分钟...")
        time.sleep(check_interval_minutes * 60)

    def run_publish_cycle_with_timeout(self, timeout_seconds: int = 600):
        """带超时限制的执行发布周期（防止卡住影响后续）"""
        import signal
        
        class TimeoutException(Exception):
            pass
        
        def timeout_handler(signum, frame):
            raise TimeoutException("发布周期超时")
        
        # 设置超时信号
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)
        
        try:
            result = self.run_publish_cycle()
            signal.alarm(0)  # 取消超时
            return result
        except TimeoutException:
            logger.error(f"发布周期执行超时 ({timeout_seconds}秒)，强制终止")
            if self.monitoring:
                self.monitoring.send_alert(
                    "发布周期超时",
                    f"发布周期执行超过 {timeout_seconds} 秒，已强制终止",
                    "warning"
                )
            return False
        finally:
            signal.signal(signal.SIGALRM, old_handler)

def main():
    """主函数"""
    try:
        manager = AutomationManager()
        
        # 检查参数
        if len(sys.argv) > 1 and sys.argv[1] == "oneshot":
            # 单次执行模式
            success = manager.run_publish_cycle()
            sys.exit(0 if success else 1)
        else:
            # 持续运行模式
            manager.run_continuous(check_interval_minutes=60)
            
    except KeyboardInterrupt:
        logger.info("收到中断信号，停止运行")
        
        # 停止监控调度器
        if 'manager' in locals() and manager.monitoring_scheduler:
            manager.monitoring_scheduler.stop()
    except Exception as e:
        logger.error(f"程序异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()