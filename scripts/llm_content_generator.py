#!/usr/bin/env python3
"""
LLM 内容生成器 - 使用大语言模型生成更自然的小红书内容
支持 DeepSeek 和 MiniMax API
"""

import os
import json
import logging
from typing import Dict, List, Optional
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LLMContentGenerator:
    """LLM 内容生成器"""
    
    def __init__(self, provider: str = "minimax", config_path: str = None):
        """
        初始化 LLM 生成器
        
        Args:
            provider: LLM 提供商 (deepseek/minimax)
            config_path: 配置文件路径
        """
        self.provider = provider
        self.config = self._load_config(config_path)
        
        if provider == "deepseek":
            self.api_key = os.environ.get("DEEPSEEK_API_KEY", "sk-b6384f153e374cddb8fcd73ab21e280b")
            self.base_url = "https://api.deepseek.com/v1"
            self.model = "deepseek-chat"
        elif provider == "minimax":
            self.api_key = os.environ.get("MINIMAX_API_KEY", self.config.get("llm", {}).get("api_key", ""))
            self.base_url = os.environ.get("MINIMAX_BASE_URL", self.config.get("llm", {}).get("base_url", "https://api.minimax.chat/v1"))
            self.model = os.environ.get("MINIMAX_MODEL", self.config.get("llm", {}).get("model", "MiniMax-M2.5"))
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")
        
        self.enabled = bool(self.api_key)
        if not self.enabled:
            logger.warning(f"{provider} API key 未配置，LLM 内容生成将不可用")
        else:
            logger.info(f"LLM 内容生成器初始化成功: {provider}/{self.model}")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config',
                'publish_config.json'
            )
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {}
    
    def _build_prompt(self, module: str, topic: str, content_type: str = "正文") -> str:
        """构建 LLM prompt"""
        
        character = self.config.get('character', {})
        name = character.get('name', '林晓芯')
        nickname = character.get('nickname', '杨枝甘露椰果红豆')
        personality = character.get('personality', '理工科女大、效率控、技术宅')
        
        language_style = self.config.get('language_style', {})
        tone = language_style.get('tone', '理性、专业但亲切')
        
        # 内容模块描述
        module_descriptions = {
            "academic_efficiency": "学术效率类 - 分享编程技巧、工具推荐、学习方法等干货内容",
            "visual_creation": "视觉创作类 - 分享AI绘画、游戏同人、创意设计等内容",
            "geek_daily": "极客日常类 - 分享代码调试、工作流优化、极客装备等日常",
            "hot_topics": "热点话题类 - 讨论行业趋势、技术热点、社会议题"
        }
        
        module_desc = module_descriptions.get(module, "分享类内容")
        
        # 字数要求
        length_requirements = {
            "标题": "8-20字，必须精简有力，能引发点击欲望，严格不超过20字！去掉所有标点符号后的纯文字不能超过20字",
            "正文": "500-1000字，内容充实，干货满满，结尾引导评论",
            "图片描述": "30-80字，简洁描述画面内容，适合AI绘图"
        }
        
        prompt = f"""你是一位小红书博主，名叫{name}（{nickname}），人设是{personality}。

请帮我生成以下内容：

【类型】{content_type}
【模块】{module_desc}
【话题】{topic}
【风格】{tone}
【字数要求】{length_requirements.get(content_type, '500-1000字')}

重要提醒：
1. 标题必须8-20字，去掉所有标点符号后不能超过20字！这是硬性要求！
2. 正文必须500-1000字，要有深度，有干货价值
3. 使用第一人称"我"来写
4. 语言亲切自然，像和朋友聊天
5. 可以使用适量的emoji增加趣味性
6. 标签用#开头，2-5个热门标签
7. 正文结尾必须加一句引导评论的话（如：你们觉得呢？/欢迎评论区聊聊/有问题评论区见）

请直接输出内容，不要其他说明。"""
        
        return prompt
    
    def generate(self, module: str, topic: str, content_type: str = "正文") -> Optional[Dict]:
        """
        生成内容
        
        Args:
            module: 内容模块
            topic: 话题
            content_type: 内容类型 (标题/正文/图片描述)
        
        Returns:
            生成的内容 dict，包含 title, content, tags 等
        """
        if not self.enabled:
            logger.warning("LLM 未启用，无法生成内容")
            return None
        
        prompt = self._build_prompt(module, topic, content_type)
        
        try:
            if self.provider == "deepseek":
                return self._call_deepseek(prompt)
            elif self.provider == "minimax":
                return self._call_minimax(prompt)
        except Exception as e:
            logger.error(f"LLM 内容生成失败: {e}")
            return None
    
    def _call_deepseek(self, prompt: str) -> Dict:
        """调用 DeepSeek API"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.8,
            "max_tokens": 2000
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        return self._parse_llm_output(content)
    
    def _call_minimax(self, prompt: str) -> Dict:
        """调用 MiniMax API"""
        url = f"{self.base_url}/text/chatcompletion_v2"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.8,
            "max_tokens": 2000
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        return self._parse_llm_output(content)
    
    def _parse_llm_output(self, content: str) -> Dict:
        """解析 LLM 输出"""
        lines = content.strip().split('\n')
        
        result = {
            "title": "",
            "content": "",
            "tags": [],
            "raw": content
        }
        
        # 解析标题 - 优先找【标题】
        title_found = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("【标题】") or line.startswith("标题："):
                result["title"] = line.split("】")[-1].split("：")[-1].strip()
                title_found = True
                break
            elif line.startswith("【标题+正文】") or line.startswith("标题+正文："):
                # 这种格式，标题在下一行
                continue
        
        # 如果没找到【标题】格式，尝试找第一行作为标题
        if not result["title"]:
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#") and len(line) < 30:
                    result["title"] = line
                    break
        
        # 解析正文 - 找【正文】或者跳过标题后的内容
        content_start = False
        content_lines = []
        in_code_block = False
        
        for line in lines:
            line_stripped = line.strip()
            
            # 跳过空行和标题行
            if not line_stripped:
                continue
            
            if "【正文】" in line_stripped or "正文：" in line_stripped:
                content_start = True
                continue
            
            # 遇到下一个标签块，停止正文
            if content_start and ("【标签】" in line_stripped or "标签：" in line_stripped or line_stripped.startswith("【") and "】" in line_stripped):
                break
            
            if content_start:
                content_lines.append(line)
        
        # 如果没有明确标记，从第二段开始作为正文
        if not content_lines:
            skip_first = False
            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                if not skip_first and not line_stripped.startswith("【"):
                    skip_first = True
                    continue
                if skip_first and line_stripped and not line_stripped.startswith("【"):
                    if "#" not in line_stripped:
                        content_lines.append(line_stripped)
        
        result["content"] = '\n'.join(content_lines).strip()
        
        # 解析标签 - 找所有 # 开头的
        tags = []
        for line in lines:
            # 提取行内所有 #标签
            import re
            found_tags = re.findall(r'#[\u4e00-\u9fa5a-zA-Z0-9]+', line)
            tags.extend(found_tags)
        
        # 去重并过滤空标签
        result["tags"] = list(set([tag for tag in tags if len(tag) > 1]))[:5]
        
        import re
        
        # 清理标题中的 markdown 格式
        title = result.get("title", "")
        title = re.sub(r'[\*\#\_]', '', title)  # 移除 * # _ 
        title = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', title)  # 移除链接但保留文字
        title = title.strip()
        
        # 移除emoji和不必要的标点来计算纯文字长度
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        title_no_emoji = emoji_pattern.sub('', title)
        # 移除标点符号
        title_no_punct = re.sub(r'[^\w\u4e00-\u9fa5]', '', title_no_emoji)
        
        # 如果去掉emoji和标点后超过20字，强制截断
        if len(title_no_punct) > 20:
            # 找到最后一个完整的中文词或单词
            title = title[:20]
        
        result["title"] = title
        
        # 限制标题长度（小红书限制20字）
        if len(result["title"]) > 20:
            result["title"] = result["title"][:20]
        
        # 清理内容中的 markdown
        content = result.get("content", "")
        # 移除标题标记
        content = re.sub(r'^#{1,6}\s+', '', content, flags=re.MULTILINE)
        # 移除加粗、斜体、下划线
        content = re.sub(r'\*\*([^\*]+)\*\*', r'\1', content)
        content = re.sub(r'\*([^\*]+)\*', r'\1', content)
        content = re.sub(r'__([^_]+)__', r'\1', content)
        content = re.sub(r'_([^_]+)_', r'\1', content)
        # 移除行内代码
        content = re.sub(r'`([^`]+)`', r'\1', content)
        # 移除链接但保留文字
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
        # 移除列表标记但保留内容
        content = re.sub(r'^[\-\*\+]\s+', '', content, flags=re.MULTILINE)
        content = re.sub(r'^\d+\.\s+', '', content, flags=re.MULTILINE)
        # 清理多余空行
        content = re.sub(r'\\n{3,}', r'\\n\\n', content)
        content = content.strip()
        
        # 移除水平分隔线
        content = re.sub(r'^---+$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^\*{3,}\$', '', content, flags=re.MULTILINE)
        
        # 移除多余空行
        content = re.sub(r'\n{3,}', r'\n\n', content)
        content = content.strip()
        
        result["content"] = content
        
        return result
    
    def generate_title_and_content(self, module: str, topic: str) -> Optional[Dict]:
        """生成标题和正文"""
        prompt = self._build_prompt(module, topic, "标题+正文")
        
        try:
            if self.provider == "deepseek":
                return self._call_deepseek(prompt)
            elif self.provider == "minimax":
                return self._call_minimax(prompt)
        except Exception as e:
            logger.error(f"LLM 内容生成失败: {e}")
            return None


if __name__ == "__main__":
    # 测试
    generator = LLMContentGenerator(provider="deepseek")
    
    if generator.enabled:
        print("=== 测试 LLM 内容生成 ===")
        result = generator.generate_title_and_content("geek_daily", "工作流优化")
        
        if result:
            print(f"\n标题: {result.get('title')}")
            print(f"\n正文:\n{result.get('content')}")
            print(f"\n标签: {result.get('tags')}")
        else:
            print("生成失败")
    else:
        print("LLM 未配置，请设置 API Key")
