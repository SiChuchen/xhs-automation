"""
小红书自动互动模块
自动评论、点赞、收藏其他帖子
"""

import logging
import os
import random
import time
import json
from typing import List, Dict, Optional
from datetime import datetime

from .xhs_api_client import XHSAPIClient, get_xhs_client
from .mcp_client import XHSMCPClient, get_mcp_client
from .database import XHSDatabase, get_database

logger = logging.getLogger(__name__)


class AutoInteract:
    """小红书自动互动类"""
    
    def __init__(self, config: Dict):
        """初始化自动互动模块
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.enabled = config.get('enabled', True)
        self.daily_comment_limit = config.get('daily_comment_limit', 15)
        self.daily_like_limit = config.get('daily_like_limit', 20)
        self.daily_collect_limit = config.get('daily_collect_limit', 10)
        self.min_interval = config.get('min_interval_seconds', 5)
        self.max_interval = config.get('max_interval_seconds', 15)
        
        # 目标关键词
        self.target_keywords = config.get('target_keywords', {})
        self.primary_keywords = self.target_keywords.get('primary', [])
        self.trending_keywords = self.target_keywords.get('trending', [])
        
        # 评论生成配置
        self.comment_llm_enabled = config.get('comment_llm_enabled', True)
        
        # API客户端
        self.xhs_client = get_xhs_client()
        self.mcp_client = get_mcp_client()
        self.db = get_database()
        
        # LLM评论生成器
        self.llm_generator = None
    
    def _init_llm_generator(self):
        """初始化LLM评论生成器"""
        if not self.comment_llm_enabled:
            return None
        
        try:
            from ..scripts.llm_content_generator import LLMContentGenerator
            generator = LLMContentGenerator(provider='minimax')
            if generator.enabled:
                self.llm_generator = generator
                logger.info("LLM评论生成器已启用")
        except Exception as e:
            logger.warning(f"LLM评论生成器初始化失败: {e}")
    
    def _select_keyword(self) -> str:
        """随机选择目标关键词"""
        # 70%概率选择主要领域关键词，30%选择热门话题
        if random.random() < 0.7 and self.primary_keywords:
            return random.choice(self.primary_keywords)
        elif self.trending_keywords:
            return random.choice(self.trending_keywords)
        elif self.primary_keywords:
            return random.choice(self.primary_keywords)
        return "编程"
    
    def _generate_comment(self, post_content: Optional[str] = None) -> str:
        """生成评论内容
        
        Args:
            post_content: 帖子内容（可选，用于LLM生成）
        
        Returns:
            评论文本
        """
        # 使用固定模板（LLM评论生成需要单独实现）
        templates = [
            "学到了！感谢分享~ 🐶",
            "太强了，收藏了！",
            "这个真的有用，点赞👍",
            "太棒了，学到了！",
            "感谢博主的分享~",
            "写得真好，mark一下",
            "👍 棒棒的！",
            "学习到了！",
            "很有帮助，谢谢！",
            "太实用了！"
        ]
        return random.choice(templates)
    
    def _wait_interval(self):
        """随机等待一段时间（避免风控）"""
        wait_time = random.randint(self.min_interval, self.max_interval)
        logger.debug(f"等待 {wait_time} 秒...")
        time.sleep(wait_time)
    
    def _check_daily_limits(self) -> Dict:
        """检查每日限额
        
        Returns:
            {'can_comment': bool, 'can_like': bool, 'can_collect': bool}
        """
        comment_count = self.db.get_interaction_count('comment')
        like_count = self.db.get_interaction_count('like')
        collect_count = self.db.get_interaction_count('collect')
        
        return {
            'can_comment': comment_count < self.daily_comment_limit,
            'can_like': like_count < self.daily_like_limit,
            'can_collect': collect_count < self.daily_collect_limit,
            'comment_remaining': max(0, self.daily_comment_limit - comment_count),
            'like_remaining': max(0, self.daily_like_limit - like_count),
            'collect_remaining': max(0, self.daily_collect_limit - collect_count)
        }
    
    def search_target_posts(self, keyword: str, limit: int = 20) -> List[Dict]:
        """搜索目标帖子
        
        Args:
            keyword: 搜索关键词
            limit: 返回数量
        
        Returns:
            帖子列表
        """
        logger.info(f"搜索关键词: {keyword}")
        results = self.mcp_client.search(keyword)
        
        posts = []
        for item in results:
            note_card = item.get('noteCard', {})
            xsec_token = item.get('xsecToken', '')
            post_id = item.get('id', '')
            
            if post_id and xsec_token:
                posts.append({
                    'id': post_id,
                    'xsec_token': xsec_token,
                    'title': note_card.get('displayTitle', ''),
                    'user': note_card.get('user', {}),
                })
        
        logger.info(f"找到 {len(posts)} 个可用帖子")
        return posts[:limit]
    
    def interact_with_post(self, post_info: Dict, action: str, comment: Optional[str] = None) -> bool:
        """与帖子互动
        
        Args:
            post_info: 帖子信息 {'id': str, 'xsec_token': str, 'title': str}
            action: 操作类型 'like'/'collect'/'comment'
            comment: 评论内容（仅comment需要）
        
        Returns:
            是否成功
        """
        post_id = post_info.get('id')
        xsec_token = post_info.get('xsec_token')
        
        if not post_id or not xsec_token:
            logger.warning("帖子信息不完整")
            return False
        
        # 检查是否已互动
        if self.db.is_interacted(post_id, action):
            logger.debug(f"帖子 {post_id} 已进行过 {action} 操作，跳过")
            return False
        
        # 执行操作
        try:
            if action == 'like':
                success = self.mcp_client.like_feed(post_id, xsec_token)
                result = {'success': success}
            elif action == 'collect':
                success = self.mcp_client.favorite_feed(post_id, xsec_token)
                result = {'success': success}
            elif action == 'comment':
                success = self.mcp_client.post_comment(post_id, xsec_token, comment or '')
                result = {'success': success}
            else:
                logger.warning(f"未知操作: {action}")
                return False
            
            # 记录结果
            status = 'success' if result.get('success') else 'failed'
            self.db.add_interaction(
                target_post_id=post_id,
                target_keyword=post_info.get('keyword', ''),
                action=action,
                content=comment or '',
                status=status
            )
            
            if result.get('success'):
                logger.info(f"{action} 帖子成功: {post_id}")
                return True
            else:
                logger.warning(f"{action} 帖子失败: {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"互动操作异常: {e}")
            return False
    
    def run_keyword_interaction(self, keyword: str, 
                               comment_count: int = 3, 
                               like_count: int = 5,
                               collect_count: int = 2) -> Dict:
        """执行关键词相关的互动任务
        
        Args:
            keyword: 关键词
            comment_count: 评论数量
            like_count: 点赞数量
            collect_count: 收藏数量
        
        Returns:
            任务结果统计
        """
        logger.info(f"开始关键词互动任务: {keyword}")
        
        # 搜索帖子
        posts = self.search_target_posts(keyword, limit=30)
        
        if not posts:
            logger.warning(f"未找到相关帖子: {keyword}")
            return {'keyword': keyword, 'success': 0, 'failed': 0}
        
        # 过滤已互动的帖子
        available_posts = []
        for post in posts:
            if not self.db.is_interacted(post['id']):
                post['keyword'] = keyword
                available_posts.append(post)
        
        logger.info(f"可用帖子数: {len(available_posts)}")
        
        # 随机打乱顺序
        random.shuffle(available_posts)
        
        results = {'success': 0, 'failed': 0}
        
        # 执行评论
        for post in available_posts[:comment_count]:
            if self.interact_with_post(post, 'comment'):
                results['success'] += 1
            else:
                results['failed'] += 1
            self._wait_interval()
        
        # 执行点赞
        for post in available_posts[comment_count:comment_count + like_count]:
            if self.interact_with_post(post, 'like'):
                results['success'] += 1
            else:
                results['failed'] += 1
            self._wait_interval()
        
        # 执行收藏
        for post in available_posts[comment_count + like_count:comment_count + like_count + collect_count]:
            if self.interact_with_post(post, 'collect'):
                results['success'] += 1
            else:
                results['failed'] += 1
            self._wait_interval()
        
        logger.info(f"关键词 {keyword} 互动完成: 成功 {results['success']}, 失败 {results['failed']}")
        return results
    
    def run_daily_task(self) -> Dict:
        """执行每日互动任务
        
        Returns:
            每日任务结果
        """
        if not self.enabled:
            logger.info("自动互动已禁用")
            return {'enabled': False}
        
        # 检查每日限额
        limits = self._check_daily_limits()
        logger.info(f"今日限额: 评论{limits['comment_remaining']}, 点赞{limits['like_remaining']}, 收藏{limits['collect_remaining']}")
        
        if not any([limits['can_comment'], limits['can_like'], limits['can_collect']]):
            logger.info("今日互动限额已用完")
            return {'status': 'limit_reached'}
        
        # 初始化LLM
        self._init_llm_generator()
        
        # 合并所有关键词
        all_keywords = self.primary_keywords + self.trending_keywords
        if not all_keywords:
            logger.warning("未配置目标关键词")
            return {'error': 'no_keywords'}
        
        # 随机选择2-3个关键词进行互动
        num_keywords = min(3, len(all_keywords))
        selected_keywords = random.sample(all_keywords, num_keywords)
        
        logger.info(f"选择关键词: {selected_keywords}")
        
        total_results = {'success': 0, 'failed': 0}
        
        for keyword in selected_keywords:
            results = self.run_keyword_interaction(
                keyword,
                comment_count=min(3, limits['comment_remaining']),
                like_count=min(5, limits['like_remaining']),
                collect_count=min(2, limits['collect_remaining'])
            )
            total_results['success'] += results.get('success', 0)
            total_results['failed'] += results.get('failed', 0)
            
            # 关键词之间也等待一下
            time.sleep(random.randint(10, 30))
        
        # 更新最终限额
        final_limits = self._check_daily_limits()
        
        return {
            'status': 'completed',
            'keywords': selected_keywords,
            'total_success': total_results['success'],
            'total_failed': total_results['failed'],
            'remaining': final_limits
        }


# 快捷函数
def run_auto_interact(config_path: str = "config/auto_interact_config.json") -> Dict:
    """运行自动互动任务
    
    Args:
        config_path: 配置文件路径
    
    Returns:
        任务结果
    """
    # 加载配置
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        config = {
            'enabled': True,
            'daily_comment_limit': 15,
            'daily_like_limit': 20,
            'daily_collect_limit': 10,
            'target_keywords': {
                'primary': ['编程技巧', '效率工具', 'AI工具', '学习方法'],
                'trending': ['开学', '实习', '考证']
            }
        }
    
    # 执行任务
    auto_interact = AutoInteract(config)
    return auto_interact.run_daily_task()
