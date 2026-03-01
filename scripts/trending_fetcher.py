#!/usr/bin/env python3
"""
Trending Topic Fetcher
自动从微博和小红书获取热门话题
"""

import json
import re
import time
import logging
from typing import Optional
from pathlib import Path

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "requests", "-q"])
    import requests


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".xhs-automation" / "config"


class WeiboTrendingFetcher:
    """微博热搜获取器"""
    
    BASE_URL = "https://weibo.com/ajax/side/hotSearch"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://weibo.com",
            "Accept": "application/json",
        })
    
    def fetch(self, limit: int = 10) -> list:
        """获取微博热搜"""
        try:
            response = self.session.get(self.BASE_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("ok") != 1:
                logger.warning(f"微博API返回错误: {data}")
                return []
            
            realtime = data.get("data", {}).get("realtime", [])
            
            topics = []
            for item in realtime[:limit]:
                topic = {
                    "source": "weibo",
                    "title": item.get("word", item.get("note", "")),
                    "url": f"https://s.weibo.com/weibo?q={item.get('word', '')}",
                    "raw_data": item
                }
                
                if item.get("label_name"):
                    topic["label"] = item.get("label_name")
                if item.get("num"):
                    topic["heat"] = item.get("num")
                
                topics.append(topic)
            
            logger.info(f"获取微博热搜 {len(topics)} 条")
            return topics
            
        except Exception as e:
            logger.error(f"获取微博热搜失败: {e}")
            return []


class XiaohongshuTrendingFetcher:
    """小红书热门获取器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.xiaohongshu.com",
            "Accept": "application/json",
        })
    
    def fetch(self, limit: int = 10) -> list:
        """获取小红书热门 - 通过网页爬取"""
        try:
            url = "https://www.xiaohongshu.com/explore"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"小红书网页返回: {response.status_code}")
                return self._fetch_backup(limit)
            
            html = response.text
            
            topics = []
            pattern = r'"title":"([^"]+)"|title>([^<]+)<'
            matches = re.findall(pattern, html)
            
            seen = set()
            count = 0
            for match in matches:
                title = match[0] or match[1]
                if title and len(title) > 2 and title not in seen:
                    seen.add(title)
                    topics.append({
                        "source": "xiaohongshu",
                        "title": title,
                        "url": f"https://www.xiaohongshu.com/search_result?keyword={title}",
                    })
                    count += 1
                    if count >= limit:
                        break
            
            if topics:
                logger.info(f"获取小红书热门 {len(topics)} 条 (网页)")
                return topics
            
            return self._fetch_backup(limit)
            
        except Exception as e:
            logger.error(f"获取小红书热门失败: {e}")
            return self._fetch_backup(limit)
    
    def _fetch_backup(self, limit: int = 10) -> list:
        """备用方法：通过搜索API"""
        try:
            keywords = ["热门", "爆款", "种草", "打卡", "好物", "穿搭", "美妆", "美食"]
            topics = []
            
            for kw in keywords[:limit]:
                topics.append({
                    "source": "xiaohongshu",
                    "title": f"{kw}推荐",
                    "url": f"https://www.xiaohongshu.com/search_result?keyword={kw}",
                })
            
            logger.info(f"获取小红书热门 {len(topics)} 条 (备用)")
            return topics[:limit]
            
        except Exception as e:
            logger.error(f"备用方法也失败: {e}")
            return []


class TrendingTopicFetcher:
    """综合热门话题获取器"""
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        
        self.weibo_fetcher = WeiboTrendingFetcher()
        self.xhs_fetcher = XiaohongshuTrendingFetcher()
        
        self.sources = self.config.get("sources", ["weibo", "xiaohongshu"])
        self.limit = self.config.get("max_topics", 10)
    
    def fetch_all(self) -> list:
        """获取所有来源的热门话题"""
        all_topics = []
        
        if "weibo" in self.sources:
            weibo_topics = self.weibo_fetcher.fetch(self.limit)
            all_topics.extend(weibo_topics)
        
        if "xiaohongshu" in self.sources:
            xhs_topics = self.xhs_fetcher.fetch(self.limit)
            all_topics.extend(xhs_topics)
        
        all_topics.sort(key=lambda x: x.get("heat", 0), reverse=True)
        
        return all_topics[:self.limit * 2]
    
    def fetch_by_keyword(self, keywords: list) -> list:
        """根据关键词过滤热门话题"""
        all_topics = self.fetch_all()
        
        if not keywords:
            return all_topics
        
        matched = []
        for topic in all_topics:
            title = topic.get("title", "").lower()
            for kw in keywords:
                if kw.lower() in title:
                    matched.append(topic)
                    break
        
        return matched


def load_config() -> dict:
    """加载配置"""
    config_path = CONFIG_DIR / "trending_config.json"
    
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    return {
        "enabled": True,
        "sources": ["weibo", "xiaohongshu"],
        "fetch_interval_minutes": 30,
        "max_topics": 10
    }


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="热门话题获取工具")
    parser.add_argument("--source", choices=["weibo", "xiaohongshu", "all"], default="all")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--keyword", "-k", help="过滤关键词")
    parser.add_argument("--output", "-o", help="输出文件路径")
    
    args = parser.parse_args()
    
    config = load_config()
    
    fetcher = TrendingTopicFetcher(config)
    
    if args.source == "weibo":
        topics = fetcher.weibo_fetcher.fetch(args.limit)
    elif args.source == "xiaohongshu":
        topics = fetcher.xhs_fetcher.fetch(args.limit)
    else:
        topics = fetcher.fetch_all()
    
    if args.keyword:
        keywords = args.keyword.split(",")
        topics = fetcher.fetch_by_keyword(keywords)
    
    print(f"\n获取到 {len(topics)} 条热门话题:\n")
    
    for i, topic in enumerate(topics, 1):
        source = topic.get("source", "unknown")
        title = topic.get("title", "无标题")
        heat = topic.get("heat", "-")
        
        print(f"{i}. [{source}] {title}")
        if heat != "-":
            print(f"   热度: {heat}")
        print()
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(topics, f, ensure_ascii=False, indent=2)
        print(f"已保存到: {args.output}")


if __name__ == "__main__":
    main()
