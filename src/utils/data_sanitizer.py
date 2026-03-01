"""
数据清洗工具 - LLM 调用前数据预处理
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, parse_qs
from datetime import datetime

logger = logging.getLogger(__name__)


class DataSanitizer:
    """数据清洗器"""
    
    HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
    URL_PARAM_PATTERN = re.compile(r'[?&](utm_|from=|ref=|source=)[^&]+')
    WHITESPACE_PATTERN = re.compile(r'\s+')
    EMOJI_PATTERN = re.compile(
        "[\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251]+"
    )
    
    def __init__(self, max_title_len: int = 100, max_summary_len: int = 500, max_comment_len: int = 200):
        self.max_title_len = max_title_len
        self.max_summary_len = max_summary_len
        self.max_comment_len = max_comment_len
    
    def remove_html_tags(self, text: str) -> str:
        """移除 HTML 标签"""
        if not text:
            return ""
        return self.HTML_TAG_PATTERN.sub('', text)
    
    def clean_url(self, url: str) -> str:
        """清理 URL 参数"""
        if not url:
            return ""
        
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        filtered_params = {
            k: v for k, v in params.items()
            if not k.startswith('utm_') and k not in ['from', 'ref', 'source']
        }
        
        new_query = '&'.join(f"{k}={v[0]}" for k, v in filtered_params.items())
        
        return parsed._replace(query=new_query).geturl()
    
    def remove_tracking_params(self, text: str) -> str:
        """移除追踪参数"""
        if not text:
            return ""
        return self.URL_PARAM_PATTERN.sub('', text)
    
    def normalize_whitespace(self, text: str) -> str:
        """标准化空白字符"""
        if not text:
            return ""
        text = self.WHITESPACE_PATTERN.sub(' ', text)
        return text.strip()
    
    def truncate(self, text: str, max_len: int, suffix: str = "...") -> str:
        """截断文本"""
        if not text:
            return ""
        if len(text) <= max_len:
            return text
        return text[:max_len - len(suffix)] + suffix
    
    def extract_title(self, data: Any) -> str:
        """提取标题"""
        if isinstance(data, dict):
            for key in ['title', 'Title', 'name', 'Name', 'text', 'content']:
                if key in data and data[key]:
                    return self.normalize(str(data[key]))
        
        if isinstance(data, str):
            return self.normalize(data[:self.max_title_len])
        
        return ""
    
    def extract_summary(self, data: Any, max_len: int = None) -> str:
        """提取摘要"""
        if max_len is None:
            max_len = self.max_summary_len
        
        if isinstance(data, dict):
            for key in ['summary', 'Summary', 'desc', 'description', 'content', 'text']:
                if key in data and data[key]:
                    text = str(data[key])
                    return self.truncate(self.normalize(text), max_len)
        
        if isinstance(data, str):
            return self.truncate(self.normalize(data), max_len)
        
        return ""
    
    def extract_top_comments(self, comments: List[Dict], n: int = 5) -> List[str]:
        """提取高赞评论"""
        if not comments:
            return []
        
        sorted_comments = sorted(
            [c for c in comments if isinstance(c, dict) and c.get('like_count', 0) > 0],
            key=lambda x: x.get('like_count', 0),
            reverse=True
        )[:n]
        
        results = []
        for c in sorted_comments:
            text = c.get('text') or c.get('content') or c.get('comment', '')
            if text:
                results.append(self.truncate(self.normalize(text), self.max_comment_len))
        
        return results
    
    def normalize(self, text: str, remove_emoji: bool = False) -> str:
        """综合清洗"""
        if not text:
            return ""
        
        text = str(text)
        text = self.remove_html_tags(text)
        text = self.remove_tracking_params(text)
        
        if remove_emoji:
            text = self.EMOJI_PATTERN.sub('', text)
        
        text = self.normalize_whitespace(text)
        
        return text
    
    def sanitize_for_llm(self, raw_data: Dict) -> Dict:
        """
        完整清洗流程
        
        Args:
            raw_data: 原始爬虫数据
        
        Returns:
            清洗后的数据
        """
        result = {
            "title": "",
            "summary": "",
            "top_comments": [],
            "metadata": {}
        }
        
        result["title"] = self.truncate(
            self.extract_title(raw_data),
            self.max_title_len
        )
        
        result["summary"] = self.extract_summary(raw_data)
        
        if "comments" in raw_data and isinstance(raw_data["comments"], list):
            result["top_comments"] = self.extract_top_comments(raw_data["comments"])
        
        if "url" in raw_data:
            result["metadata"]["url"] = self.clean_url(raw_data["url"])
        
        if "hot_rank" in raw_data:
            result["metadata"]["rank"] = raw_data["hot_rank"]
        
        if "timestamp" in raw_data:
            result["metadata"]["timestamp"] = raw_data["timestamp"]
        
        logger.info(f"数据清洗完成: title={result['title'][:30]}...")
        
        return result
    
    def build_llm_context(self, data: Dict, include_comments: bool = True) -> str:
        """
        构建 LLM 上下文
        
        Args:
            data: 清洗后的数据
            include_comments: 是否包含评论
        
        Returns:
            格式化的上下文字符串
        """
        parts = []
        
        if data.get("title"):
            parts.append(f"标题: {data['title']}")
        
        if data.get("summary"):
            parts.append(f"摘要: {data['summary']}")
        
        if include_comments and data.get("top_comments"):
            parts.append("高赞评论:")
            for i, comment in enumerate(data["top_comments"], 1):
                parts.append(f"  {i}. {comment}")
        
        return "\n".join(parts)


class TrendingDataSanitizer(DataSanitizer):
    """热搜数据专用清洗器"""
    
    def __init__(self):
        super().__init__(
            max_title_len=80,
            max_summary_len=300,
            max_comment_len=150
        )
    
    def parse_weibo_hot(self, raw_data: Dict) -> Dict:
        """解析微博热搜数据"""
        return self.sanitize_for_llm({
            "title": raw_data.get("word") or raw_data.get("label"),
            "summary": raw_data.get("note", ""),
            "url": raw_data.get("url", ""),
            "hot_rank": raw_data.get("num", 0),
            "timestamp": raw_data.get("raw_data", {}).get("created_at"),
        })
    
    def parse_xhs_trending(self, raw_data: Dict) -> Dict:
        """解析小红书热搜数据"""
        return self.sanitize_for_llm({
            "title": raw_data.get("title"),
            "summary": raw_data.get("desc", ""),
            "comments": raw_data.get("comments", [])[:10],
            "hot_rank": raw_data.get("rank"),
        })


def sanitize_trending_data(raw_data: Dict, platform: str = "weibo") -> Dict:
    """便捷函数: 清洗热搜数据"""
    sanitizer = TrendingDataSanitizer()
    
    if platform == "weibo":
        return sanitizer.parse_weibo_hot(raw_data)
    elif platform == "xiaohongshu":
        return sanitizer.parse_xhs_trending(raw_data)
    else:
        return sanitizer.sanitize_for_llm(raw_data)


def clean_json_for_llm(json_str: str) -> str:
    """便捷函数: 清洗 JSON 字符串"""
    try:
        data = json.loads(json_str)
        sanitizer = DataSanitizer()
        return sanitizer.sanitize_for_llm(data)
    except json.JSONDecodeError:
        return {"raw": json_str}
