#!/usr/bin/env python3
"""
小红书自动化发布系统 - 林晓芯人设版
基于人物设定和内容模块的自动化发布流程
"""

import os
import sys
import json
import random
import datetime
import logging
import time
from typing import Dict, List, Tuple, Optional
import requests

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        
    def get_random_topic(self) -> Tuple[str, str, List[str]]:
        """根据权重随机选择一个内容模块和话题"""
        modules = list(self.content_modules.keys())
        weights = [self.content_modules[m]['weight'] for m in modules]
        
        selected_module = random.choices(modules, weights=weights, k=1)[0]
        module_config = self.content_modules[selected_module]
        
        topic = random.choice(module_config['topics'])
        tags = module_config['tags']
        
        return selected_module, topic, tags
    
    def generate_content(self, module: str, topic: str) -> Tuple[str, str]:
        """根据模块和话题生成标题和内容"""
        # 基础标题模板
        title_templates = [
            f"【{topic}】{random.choice(self.language_style['signature_phrases'])}",
            f"关于{topic}，我想说...",
            f"今天聊聊{topic}的那些事",
            f"发现一个{topic}的超实用技巧",
            f"【干货分享】{topic}全解析"
        ]
        
        # 根据模块调整标题风格
        if module == 'academic_efficiency':
            title_templates.extend([
                f"技术分享 | {topic}的完整指南",
                f"效率提升 | 如何更好地{topic}",
                f"实用工具 | {topic}必备神器"
            ])
        elif module == 'visual_creation':
            title_templates.extend([
                f"视觉创作 | {topic}作品展示",
                f"AI艺术 | {topic}的无限可能",
                f"二创分享 | {topic}灵感迸发"
            ])
        elif module == 'geek_daily':
            title_templates.extend([
                f"极客日常 | {topic}的那些事",
                f"技术生活 | {topic}小记",
                f"代码人生 | {topic}经验分享"
            ])
        
        title = random.choice(title_templates)
        
        # 生成内容正文
        content_parts = []
        
        # 开头
        openings = [
            f"大家好，我是{self.character['nickname']}～",
            f"这里是{self.character['name']}，",
            ""
        ]
        content_parts.append(random.choice(openings))
        
        # 主体内容
        if module == 'academic_efficiency':
            content_parts.extend([
                f"作为{self.character['major']}专业的学生，{topic}是我日常研究中非常重要的一部分。",
                "今天整理了一些实用技巧和大家分享：",
                "",
                "1️⃣ 第一点技巧...",
                "2️⃣ 第二点方法...", 
                "3️⃣ 第三点建议...",
                "",
                f"这些方法帮我大幅提升了{topic}的效率，希望对你们也有帮助！"
            ])
        elif module == 'visual_creation':
            content_parts.extend([
                f"最近在研究{topic}，尝试用AI工具进行了一些创作。",
                "分享一些作品和制作心得：",
                "",
                "🎨 创作灵感来源于...",
                "🛠️ 使用工具包括...",
                "💡 关键技巧是...",
                "",
                f"对{topic}感兴趣的朋友可以一起交流！"
            ])
        elif module == 'geek_daily':
            content_parts.extend([
                f"今天的{topic}日常分享～",
                "作为一个技术宅，每天最开心的事情就是...",
                "",
                "💻 遇到的问题：...",
                "🔧 解决方案：...",
                "📈 优化效果：...",
                "",
                "技术让生活更美好！"
            ])
        else:  # hot_topics
            content_parts.extend([
                f"最近{topic}这个话题很火，我也来聊聊自己的看法。",
                "从技术/学生角度谈谈我的理解：",
                "",
                "📌 观点一：...",
                "📌 观点二：...", 
                "📌 观点三：...",
                "",
                f"关于{topic}，你们有什么看法呢？"
            ])
        
        # 结尾
        endings = [
            f"——{self.character['nickname']}的日常分享",
            "#理工科女大的日常#",
            "感谢阅读，下期见～"
        ]
        content_parts.append("")
        content_parts.append(random.choice(endings))
        
        content = "\n".join(content_parts)
        
        # 确保内容长度符合小红书要求（标题≤20字，正文≤1000字）
        if len(title) > 20:
            title = title[:19] + "…"
        
        if len(content) > 1000:
            content = content[:997] + "…"
        
        return title, content
    
    def select_image(self, module: str) -> str:
        """根据内容模块选择图片"""
        visual_assets = self.config['visual_assets']
        
        if module == 'visual_creation':
            # 视觉创作模块使用内容图片
            content_dir = visual_assets['content_images_dir']
            # 这里可以扩展为从内容图片目录选择
            # 暂时使用人物形象图片
            return random.choice(visual_assets['character_images'])
        else:
            # 其他模块使用人物形象图片
            return random.choice(visual_assets['character_images'])

class XiaohongshuPublisher:
    """小红书发布器"""
    
    def __init__(self, base_url: str = "http://localhost:18060"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        
    def check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            response = requests.get(f"{self.api_url}/login/status", timeout=30)
            data = response.json()
            return data.get('success', False)
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False
    
    def publish_note(self, title: str, content: str, image_path: str, tags: List[str] = None) -> Dict:
        """发布笔记"""
        payload = {
            "title": title,
            "content": content,
            "images": [image_path]
        }
        
        if tags:
            payload["tags"] = tags[:5]  # 限制标签数量
        
        try:
            response = requests.post(
                f"{self.api_url}/publish",
                json=payload,
                timeout=120
            )
            data = response.json()
            
            if data.get('success'):
                logger.info(f"发布成功! Post ID: {data.get('data', {}).get('post_id', 'Unknown')}")
            else:
                logger.error(f"发布失败: {data.get('error', 'Unknown error')}")
            
            return data
            
        except Exception as e:
            logger.error(f"发布请求失败: {e}")
            return {"success": False, "error": str(e)}

class AutomationManager:
    """自动化管理器"""
    
    def __init__(self):
        config_path = "/home/ubuntu/xhs-automation/config/publish_config.json"
        soul_path = "/home/ubuntu/xhs-automation/config/soul.md"
        
        self.persona = CharacterPersona(config_path, soul_path)
        self.publisher = XiaohongshuPublisher()
        
        # 发布记录文件
        self.records_file = "/home/ubuntu/xhs-automation/logs/publish_records.json"
        
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
    
    def should_publish_now(self) -> bool:
        """根据配置判断是否应该发布"""
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
        
        # 检查最小间隔
        hours_since_last = (now_local - latest_local).total_seconds() / 3600
        min_interval = self.persona.config['publishing']['min_interval_hours']
        
        if hours_since_last < min_interval:
            logger.info(f"距离上次发布仅{hours_since_last:.1f}小时，未达到最小间隔{min_interval}小时")
            return False
        
        # 检查每日最大发布数
        today = now_local.date()
        today_posts = len([r for r in records 
                          if datetime.datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')).astimezone().date() == today])
        
        max_posts = self.persona.config['publishing']['max_posts_per_day']
        if today_posts >= max_posts:
            logger.info(f"今日已发布{today_posts}次，达到每日上限{max_posts}")
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
                return True
        
        logger.info(f"当前时间{current_time_str}不在最佳发布时间范围内")
        return False
    
    def run_publish_cycle(self):
        """执行一次发布周期"""
        logger.info("开始发布周期检查...")
        
        # 1. 检查登录状态
        if not self.publisher.check_login_status():
            logger.error("未登录或登录状态失效，请重新登录")
            return False
        
        # 2. 判断是否应该发布
        if not self.should_publish_now():
            logger.info("当前不符合发布条件，跳过")
            return False
        
        # 3. 生成内容
        module, topic, tags = self.persona.get_random_topic()
        title, content = self.persona.generate_content(module, topic)
        image_path = self.persona.select_image(module)
        
        logger.info(f"生成内容 - 模块: {module}, 话题: {topic}")
        logger.info(f"标题: {title}")
        logger.info(f"图片路径: {image_path}")
        logger.info(f"标签: {', '.join(tags[:3])}...")
        
        # 4. 发布内容
        result = self.publisher.publish_note(title, content, image_path, tags)
        
        # 5. 记录结果
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
        """持续运行自动化"""
        logger.info(f"启动自动化发布系统，检查间隔: {check_interval_minutes}分钟")
        logger.info(f"人物设定: {self.persona.character['name']} ({self.persona.character['nickname']})")
        
        while True:
            try:
                self.run_publish_cycle()
            except Exception as e:
                logger.error(f"发布周期执行异常: {e}")
            
            logger.info(f"等待{check_interval_minutes}分钟...")
            time.sleep(check_interval_minutes * 60)

def main():
    """主函数"""
    try:
        manager = AutomationManager()
        
        # 检查参数
        if len(sys.argv) > 1 and sys.argv[1] == "oneshot":
            # 单次执行模式
            manager.run_publish_cycle()
        else:
            # 持续运行模式
            manager.run_continuous(check_interval_minutes=60)
            
    except KeyboardInterrupt:
        logger.info("收到中断信号，停止运行")
    except Exception as e:
        logger.error(f"程序异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()