#!/usr/bin/env python3
"""
智能图片管理器 - 根据内容选择合适的图片
支持本地图片库和Pexels在线搜索
"""

import os
import sys
import json
import random
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
from pathlib import Path

# 尝试导入Pexels相关库
try:
    import requests
    PEXELS_AVAILABLE = True
except ImportError:
    PEXELS_AVAILABLE = False

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImageManager:
    """智能图片管理器"""
    
    def __init__(self, config_path: str = None, pexels_api_key: str = None):
        """初始化图片管理器"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config',
                'publish_config.json'
            )
        
        self.config_path = config_path
        self.config = self._load_config()
        self.pexels_api_key = pexels_api_key
        
        # 图片目录
        self.image_dir = Path('/home/ubuntu/xhs-automation/images')
        self.content_image_dir = Path('/tmp/xhs-official/images')
        
        # 创建必要的目录
        self.image_dir.mkdir(exist_ok=True)
        self.content_image_dir.mkdir(exist_ok=True)
        
        # 图片使用记录
        self.usage_file = self.image_dir / 'image_usage.json'
        self.usage_records = self._load_usage_records()
        
        # 图片分类映射
        self.image_categories = self._init_image_categories()
        
        # 话题到关键词的映射
        self.topic_keywords = self._init_topic_keywords()
        
        # 图片发布频率控制（每N次发布使用一次图片）
        self.image_frequency = self.config.get('image_frequency', 1)  # 默认每次发布都尽量用图
        
        # 初始化图片库
        self._scan_local_images()
        
        logger.info(f"图片管理器初始化完成，本地图片: {len(self.local_images)}张")
        
        if pexels_api_key:
            logger.info("Pexels API已配置")
        else:
            logger.warning("Pexels API未配置，将仅使用本地图片")
    
    def _load_config(self) -> Dict:
        """加载配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"配置文件不存在: {self.config_path}")
            return {}
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {}
    
    def _load_usage_records(self) -> Dict:
        """加载图片使用记录"""
        if not self.usage_file.exists():
            return {
                "usage_history": [],
                "last_image_date": None,
                "image_use_count": 0,
                "total_posts": 0
            }
        
        try:
            with open(self.usage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载使用记录失败: {e}")
            return {
                "usage_history": [],
                "last_image_date": None,
                "image_use_count": 0,
                "total_posts": 0
            }
    
    def _save_usage_records(self):
        """保存图片使用记录"""
        try:
            with open(self.usage_file, 'w', encoding='utf-8') as f:
                json.dump(self.usage_records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存使用记录失败: {e}")
    
    def _init_image_categories(self) -> Dict:
        """初始化图片分类映射"""
        return {
            "academic_efficiency": {
                "categories": ["study", "programming", "books", "desk", "computer", "office"],
                "person_required": True,  # 需要人物照片
                "character_style": "original"  # 使用原始形象
            },
            "visual_creation": {
                "categories": ["art", "design", "digital", "anime", "game", "cyberpunk"],
                "person_required": True,
                "character_style": "cyber"  # 使用赛博形象
            },
            "geek_daily": {
                "categories": ["tech", "gadgets", "workspace", "coding", "keyboard", "setup"],
                "person_required": True,
                "character_style": "original"
            },
            "hot_topics": {
                "categories": ["news", "trend", "campus", "discussion", "social"],
                "person_required": False,  # 不一定需要人物
                "character_style": "original"
            }
        }
    
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
    
    def _scan_local_images(self):
        """扫描本地图片库"""
        self.local_images = []
        self.character_images = []
        self.content_images = []
        
        # 支持的图片格式
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        
        for file_path in self.image_dir.rglob('*'):
            if file_path.suffix.lower() in image_extensions and file_path.is_file():
                image_info = {
                    "path": str(file_path),
                    "filename": file_path.name,
                    "size": file_path.stat().st_size,
                    "mtime": file_path.stat().st_mtime,
                    "category": self._detect_image_category(file_path),
                    "is_character": self._is_character_image(file_path),
                    "used_count": 0,
                    "last_used": None
                }
                
                self.local_images.append(image_info)
                
                if image_info["is_character"]:
                    self.character_images.append(image_info)
                else:
                    self.content_images.append(image_info)
        
        # 更新使用记录中的使用次数
        for record in self.usage_records.get("usage_history", []):
            for img in self.local_images:
                if img["path"] == record.get("image_path"):
                    img["used_count"] = record.get("use_count", 0)
                    img["last_used"] = record.get("last_used")
    
    def _detect_image_category(self, file_path: Path) -> List[str]:
        """检测图片分类（基于文件名）"""
        filename = file_path.stem.lower()
        categories = []
        
        # 基于文件名关键词检测
        category_keywords = {
            "study": ["学习", "读书", "study", "book"],
            "programming": ["编程", "代码", "programming", "code", "python"],
            "art": ["艺术", "绘画", "art", "draw", "paint"],
            "tech": ["科技", "技术", "tech", "gadget"],
            "campus": ["校园", "学校", "campus", "school"],
            "nature": ["自然", "风景", "nature", "landscape"],
            "food": ["食物", "美食", "food", "meal"],
            "travel": ["旅行", "旅游", "travel", "trip"],
            "portrait": ["肖像", "人物", "portrait", "person", "face"]
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in filename for keyword in keywords):
                categories.append(category)
        
        return categories if categories else ["general"]
    
    def _is_character_image(self, file_path: Path) -> bool:
        """判断是否为人设图片"""
        filename = file_path.name.lower()
        
        # 人物图片关键词
        character_keywords = ["原画", "赛博", "character", "portrait", "face", "person"]
        
        # 检查文件名是否包含人物关键词
        if any(keyword in filename for keyword in character_keywords):
            return True
        
        # 检查是否在配置的人物图片列表中
        character_paths = self.config.get('visual_assets', {}).get('character_images', [])
        if str(file_path) in character_paths:
            return True
        
        return False
    
    def should_use_image(self) -> bool:
        """
        判断本次发布是否应该使用图片
        
        修改为总是返回True，尽量使用图片，纯文字尽量少出现
        但仍保留频率记录用于统计
        """
        # 总是尝试使用图片
        return True
    
    def select_image_for_content(self, module: str, topic: str, force_image: bool = False) -> Optional[str]:
        """
        根据内容和模块选择合适的图片
        
        尽量使用图片，纯文字尽量少出现
        
        Args:
            module: 内容模块 (academic_efficiency, visual_creation, etc.)
            topic: 具体话题
            force_image: 是否强制使用图片
            
        Returns:
            图片路径或None（如果不使用图片）
        """
        module_config = self.image_categories.get(module, {})
        person_required = module_config.get("person_required", True)
        character_style = module_config.get("character_style", "original")
        
        # 获取话题相关的关键词
        keywords = self.topic_keywords.get(topic, [])
        
        selected_image = None
        
        # 1. 首先尝试从本地内容图片库匹配
        selected_image = self._select_from_local_content(module, topic, keywords)
        if selected_image:
            logger.info(f"✅ 从本地内容库选择匹配图片: {os.path.basename(selected_image)}")
        
        # 2. 如果没有合适的内容图片，尝试使用人物图片
        if not selected_image:
            selected_image = self._select_character_image(character_style)
            if selected_image:
                logger.info(f"✅ 使用人物形象图片: {os.path.basename(selected_image)}")
        
        # 3. 如果还是没有图片，且允许使用网络图片，则尝试从Pexels搜索相关图片
        if not selected_image and self.pexels_api_key:
            selected_image = self._search_pexels_image(topic, keywords)
            if selected_image:
                logger.info(f"✅ 从Pexels搜索相关图片: {os.path.basename(selected_image)}")
        
        # 4. 如果还是没有图片，尝试搜索通用图片（风景、自然等）
        if not selected_image and self.pexels_api_key:
            generic_keywords = ["nature", "landscape", "scenery", "city", "urban", "sky", "beautiful"]
            # 选择与话题最相关的通用关键词
            if "校园" in topic or "学校" in topic:
                generic_keywords = ["campus", "university", "student", "education"]
            elif "编程" in topic or "代码" in topic:
                generic_keywords = ["technology", "computer", "code", "programming"]
            elif "艺术" in topic or "绘画" in topic:
                generic_keywords = ["art", "design", "creative", "color"]
            
            selected_image = self._search_pexels_image(" ".join(generic_keywords[:2]), [])
            if selected_image:
                logger.info(f"✅ 从Pexels搜索通用图片: {os.path.basename(selected_image)}")
        
        # 5. 如果还是没有图片，尝试使用任何可用的本地图片
        if not selected_image and self.content_images:
            # 使用第一张内容图片
            selected_image = self.content_images[0]["path"]
            logger.info(f"✅ 使用任意可用内容图片: {os.path.basename(selected_image)}")
        
        # 6. 如果还是没有图片，使用默认人物图片
        if not selected_image:
            selected_image = self._get_default_character_image()
            if selected_image:
                logger.info(f"✅ 使用默认人物图片: {os.path.basename(selected_image)}")
        
        # 7. 如果还是没有图片（理论上不可能），记录错误
        if not selected_image:
            logger.error("❌ 无法找到任何可用图片")
            return None
        
        # 更新使用记录
        self._update_usage_record(selected_image, module, topic)
        
        return selected_image
    
    def _select_from_local_content(self, module: str, topic: str, keywords: List[str]) -> Optional[str]:
        """从本地内容图片库中选择"""
        if not self.content_images:
            return None
        
        # 根据模块和关键词评分
        scored_images = []
        for img in self.content_images:
            score = 0
            
            # 模块匹配加分
            if any(cat in img.get("category", []) for cat in self.image_categories.get(module, {}).get("categories", [])):
                score += 3
            
            # 关键词匹配加分
            if keywords:
                filename_lower = img["filename"].lower()
                for keyword in keywords:
                    if keyword.lower() in filename_lower:
                        score += 2
            
            # 使用频率减分（优先使用未使用或较少使用的图片）
            use_count = img.get("used_count", 0)
            score -= min(use_count, 5)  # 最多减5分
            
            # 最近使用减分
            if img.get("last_used"):
                days_since = (datetime.now() - datetime.fromisoformat(img["last_used"])).days
                if days_since < 7:
                    score -= 1
            
            scored_images.append((score, img))
        
        # 选择分数最高的图片
        scored_images.sort(key=lambda x: x[0], reverse=True)
        
        if scored_images and scored_images[0][0] > 0:
            selected_img = scored_images[0][1]
            logger.info(f"从本地内容库选择图片: {selected_img['filename']} (分数: {scored_images[0][0]})")
            return selected_img["path"]
        
        return None
    
    def _select_character_image(self, style: str = "original") -> Optional[str]:
        """选择人物形象图片"""
        if not self.character_images:
            return None
        
        # 根据风格筛选
        style_keywords = {
            "original": ["原画", "original", "normal"],
            "cyber": ["赛博", "cyber", "future"]
        }
        
        style_words = style_keywords.get(style, [])
        matching_images = []
        
        for img in self.character_images:
            filename = img["filename"].lower()
            if any(word in filename for word in style_words):
                matching_images.append(img)
        
        # 如果没有匹配风格，使用所有人物图片
        if not matching_images:
            matching_images = self.character_images
        
        if not matching_images:
            return None
        
        # 选择使用次数最少的图片
        matching_images.sort(key=lambda x: x.get("used_count", 0))
        selected_img = matching_images[0]
        
        logger.info(f"选择人物形象图片: {selected_img['filename']} (风格: {style})")
        return selected_img["path"]
    
    def _get_default_character_image(self) -> Optional[str]:
        """获取默认人物图片"""
        character_images = self.config.get('visual_assets', {}).get('character_images', [])
        if character_images:
            # 检查文件是否存在
            for img_path in character_images:
                if os.path.exists(img_path):
                    logger.info(f"使用默认人物图片: {img_path}")
                    return img_path
        
        # 如果没有配置，使用第一个可用的人物图片
        if self.character_images:
            selected_img = self.character_images[0]
            logger.info(f"使用备用人物图片: {selected_img['filename']}")
            return selected_img["path"]
        
        return None
    
    def _search_pexels_image(self, topic: str, keywords: List[str]) -> Optional[str]:
        """从Pexels搜索并下载图片"""
        if not PEXELS_AVAILABLE or not self.pexels_api_key:
            return None
        
        # 构建搜索查询
        query = topic
        if keywords:
            query = " ".join([topic] + keywords[:3])
        
        logger.info(f"搜索Pexels图片: {query}")
        
        try:
            # Pexels API搜索
            headers = {"Authorization": self.pexels_api_key}
            params = {
                "query": query,
                "per_page": 5,
                "page": 1,
                "orientation": "portrait"  # 小红书推荐竖屏
            }
            
            response = requests.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                photos = data.get("photos", [])
                
                if photos:
                    # 选择第一张图片
                    photo = photos[0]
                    photo_url = photo.get("src", {}).get("large")
                    
                    if photo_url:
                        # 下载图片
                        downloaded_path = self._download_image(photo_url, f"pexels_{photo.get('id', 'image')}")
                        if downloaded_path:
                            # 添加到本地库
                            self._add_to_local_library(downloaded_path, [topic] + keywords)
                            return downloaded_path
            
        except Exception as e:
            logger.error(f"Pexels搜索失败: {e}")
        
        return None
    
    def _download_image(self, url: str, filename: str) -> Optional[str]:
        """下载图片到本地"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # 生成文件名
            file_ext = ".jpg"  # 默认jpg
            if "jpeg" in response.headers.get("content-type", "").lower():
                file_ext = ".jpg"
            elif "png" in response.headers.get("content-type", "").lower():
                file_ext = ".png"
            
            # 生成唯一文件名
            file_hash = hashlib.md5(response.content).hexdigest()[:8]
            filename = f"{filename}_{file_hash}{file_ext}"
            file_path = self.content_image_dir / filename
            
            # 保存文件
            with open(file_path, "wb") as f:
                f.write(response.content)
            
            logger.info(f"图片下载成功: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"图片下载失败: {e}")
            return None
    
    def _add_to_local_library(self, image_path: str, categories: List[str]):
        """将图片添加到本地库"""
        if not os.path.exists(image_path):
            return
        
        file_path = Path(image_path)
        image_info = {
            "path": image_path,
            "filename": file_path.name,
            "size": file_path.stat().st_size,
            "mtime": file_path.stat().st_mtime,
            "category": categories,
            "is_character": False,
            "used_count": 0,
            "last_used": None
        }
        
        self.local_images.append(image_info)
        self.content_images.append(image_info)
    
    def _update_usage_record(self, image_path: str, module: str, topic: str):
        """更新图片使用记录"""
        now = datetime.now().isoformat()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 更新总体统计
        self.usage_records["total_posts"] = self.usage_records.get("total_posts", 0) + 1
        self.usage_records["image_use_count"] = self.usage_records.get("image_use_count", 0) + 1
        self.usage_records["last_image_date"] = today
        
        # 添加到使用历史
        usage_entry = {
            "timestamp": now,
            "image_path": image_path,
            "module": module,
            "topic": topic,
            "use_count": 1
        }
        
        # 检查是否已有该图片的使用记录
        found = False
        for record in self.usage_records.get("usage_history", []):
            if record.get("image_path") == image_path:
                record["use_count"] = record.get("use_count", 0) + 1
                record["last_used"] = now
                found = True
                break
        
        if not found:
            usage_entry["last_used"] = now
            self.usage_records.setdefault("usage_history", []).append(usage_entry)
        
        # 更新本地图片信息
        for img in self.local_images:
            if img["path"] == image_path:
                img["used_count"] = img.get("used_count", 0) + 1
                img["last_used"] = now
        
        # 保存记录
        self._save_usage_records()
    
    def get_usage_stats(self) -> Dict:
        """获取使用统计"""
        return {
            "total_posts": self.usage_records.get("total_posts", 0),
            "image_use_count": self.usage_records.get("image_use_count", 0),
            "image_frequency": self.image_frequency,
            "last_image_date": self.usage_records.get("last_image_date"),
            "local_images": len(self.local_images),
            "character_images": len(self.character_images),
            "content_images": len(self.content_images)
        }

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='智能图片管理器')
    parser.add_argument('--stats', action='store_true', help='显示使用统计')
    parser.add_argument('--scan', action='store_true', help='扫描本地图片库')
    parser.add_argument('--test-select', help='测试图片选择 (格式: 模块,话题)')
    parser.add_argument('--pexels-key', help='设置Pexels API Key')
    
    args = parser.parse_args()
    
    # 初始化图片管理器
    manager = ImageManager(pexels_api_key=args.pexels_key)
    
    if args.stats:
        stats = manager.get_usage_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    elif args.scan:
        print(f"扫描完成，发现 {len(manager.local_images)} 张图片:")
        print(f"  人物图片: {len(manager.character_images)} 张")
        print(f"  内容图片: {len(manager.content_images)} 张")
        
        # 显示图片列表
        for i, img in enumerate(manager.local_images[:10], 1):
            print(f"  {i}. {img['filename']} ({'人物' if img['is_character'] else '内容'})")
        
        if len(manager.local_images) > 10:
            print(f"  ... 还有 {len(manager.local_images) - 10} 张图片")
    
    elif args.test_select:
        try:
            module, topic = args.test_select.split(',')
            image_path = manager.select_image_for_content(module.strip(), topic.strip())
            
            if image_path:
                print(f"✅ 选择的图片: {image_path}")
            else:
                print("ℹ️  本次发布不使用图片")
                
        except ValueError:
            print("错误: 请使用格式 --test-select '模块,话题'")
    
    else:
        # 显示帮助信息
        stats = manager.get_usage_stats()
        print("智能图片管理器")
        print("=" * 50)
        print(f"本地图片: {stats['local_images']}张 (人物: {stats['character_images']}, 内容: {stats['content_images']})")
        print(f"发布统计: 总计 {stats['total_posts']}次，使用图片 {stats['image_use_count']}次")
        print(f"图片频率: 每 {stats['image_frequency']}次发布使用一次图片")
        print(f"最后使用: {stats['last_image_date'] or '从未'}")
        
        if not manager.pexels_api_key:
            print("\n⚠️  未配置Pexels API Key，无法搜索网络图片")

if __name__ == "__main__":
    main()