"""
LLM 响应解析器
处理 LLM 输出的 JSON 提取、校验和错误重试
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class LLMParseError(Exception):
    """LLM 解析错误异常 - 用于触发 Huey 重试"""
    def __init__(self, message: str, raw_content: str = "", parse_error: str = ""):
        super().__init__(message)
        self.raw_content = raw_content
        self.parse_error = parse_error


@dataclass
class ContentSchema:
    """内容结构定义"""
    title: str = ""
    content: str = ""
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class LLMResponseParser:
    """LLM 响应解析器"""
    
    JSON_PATTERNS = [
        re.compile(r'```json\s*(.*?)\s*```', re.DOTALL),
        re.compile(r'```\s*(.*?)\s*```', re.DOTALL),
        re.compile(r'\{.*\}', re.DOTALL),
    ]
    
    INTRO_PATTERNS = [
        r'^好的[，,].*',
        r'^以下是.*',
        r'^这里.*',
        r'^为您.*',
        r'^下面.*',
        r'^我来.*',
        r'^OK[,\s].*',
        r'^Here.*',
        r'^Sure[,\s].*',
    ]
    
    REQUIRED_FIELDS = ['title', 'content']
    
    def __init__(self, required_fields: List[str] = None):
        self.required_fields = required_fields or self.REQUIRED_FIELDS
    
    def parse(self, content: str) -> ContentSchema:
        """
        解析 LLM 响应
        
        Args:
            content: LLM 原始输出
        
        Returns:
            ContentSchema
        
        Raises:
            LLMParseError: 解析失败，触发 Huey 重试
        """
        cleaned = self._clean_content(content)
        
        json_str = self._extract_json(cleaned)
        
        if not json_str:
            raise LLMParseError("无法提取 JSON", content, "no json found")
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise LLMParseError(f"JSON 解析失败: {e}", content, str(e))
        
        validated = self._validate_and_normalize(data)
        
        return ContentSchema(**validated)
    
    def _clean_content(self, content: str) -> str:
        """清理内容 - 移除开场白"""
        if not content:
            return ""
        
        for pattern in self.INTRO_PATTERNS:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE).strip()
        
        return content.strip()
    
    def _extract_json(self, content: str) -> Optional[str]:
        """提取 JSON 块"""
        for pattern in self.JSON_PATTERNS:
            match = pattern.search(content)
            if match:
                return match.group(1) if match.lastindex else match.group()
        
        return None
    
    def _validate_and_normalize(self, data: Dict) -> Dict:
        """校验并规范化数据"""
        result = {}
        
        for field in self.required_fields:
            if field not in data or not data[field]:
                raise LLMParseError(f"缺少必需字段: {field}", str(data), f"missing field: {field}")
            result[field] = str(data[field]).strip()
        
        if 'title' in result:
            result['title'] = self._normalize_title(result['title'])
        
        if 'content' in result:
            result['content'] = self._normalize_content(result['content'])
        
        result['tags'] = self._extract_tags(data)
        
        return result
    
    def build_retry_prompt(self, original_prompt: str, error: LLMParseError, retry_count: int = 1) -> str:
        """
        构建重试时的修正 prompt - 注入错误信息引导模型修正行为
        
        Args:
            original_prompt: 原始 prompt
            error: 解析错误
            retry_count: 重试次数
        
        Returns:
            注入修正指令的 prompt
        """
        if retry_count <= 0:
            return original_prompt
        
        correction_instruction = self._get_correction_instruction(error, retry_count)
        
        if "{correction}" in original_prompt:
            return original_prompt.replace("{correction}", correction_instruction)
        
        return f"{original_prompt}\n\n{correction_instruction}"
    
    def _get_correction_instruction(self, error: LLMParseError, retry_count: int) -> str:
        """根据错误类型生成修正指令"""
        base_instructions = [
            "【重要】前一次输出格式错误，必须仅返回纯净 JSON 字符串，",
            "严禁携带 ```json、``` 等任何 Markdown 包裹符号，",
            "不要添加任何开场白（如'好的，以下是...'），直接输出 JSON。"
        ]
        
        if retry_count >= 2:
            base_instructions.extend([
                f"错误详情: {error.parse_error}",
                "请严格遵守 JSON 格式，确保可以被 json.loads() 解析。"
            ])
        
        return "\n".join(base_instructions)
    
    def _normalize_title(self, title: str) -> str:
        """规范化标题"""
        title = re.sub(r'[\*\#\_]', '', title)
        title = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', title)
        
        if len(title) > 20:
            title = title[:20]
        
        return title.strip()
    
    def _normalize_content(self, content: str) -> str:
        """规范化内容"""
        content = re.sub(r'^#{1,6}\s+', '', content, flags=re.MULTILINE)
        content = re.sub(r'\*\*([^\*]+)\*\*', r'\1', content)
        content = re.sub(r'\*([^\*]+)\*', r'\1', content)
        content = re.sub(r'__([^_]+)__', r'\1', content)
        content = re.sub(r'`([^`]+)`', r'\1', content)
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
        content = re.sub(r'^[\-\*\+]\s+', '', content, flags=re.MULTILINE)
        content = re.sub(r'^\d+\.\s+', '', content, flags=re.MULTILINE)
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content.strip()
    
    def _extract_tags(self, data: Dict) -> List[str]:
        """提取标签"""
        tags = []
        
        if 'tags' in data:
            raw_tags = data['tags']
            if isinstance(raw_tags, list):
                tags = [str(t).strip() for t in raw_tags if t]
            elif isinstance(raw_tags, str):
                tags = re.findall(r'#[\u4e00-\u9fa5a-zA-Z0-9]+', raw_tags)
        
        tags = list(set([t.strip() for t in tags if len(t.strip()) > 1]))[:5]
        
        return tags


_global_parser = None


def get_llm_parser() -> LLMResponseParser:
    """获取全局解析器"""
    global _global_parser
    if _global_parser is None:
        _global_parser = LLMResponseParser()
    return _global_parser


def parse_llm_response(content: str) -> ContentSchema:
    """便捷函数: 解析 LLM 响应"""
    parser = get_llm_parser()
    return parser.parse(content)
