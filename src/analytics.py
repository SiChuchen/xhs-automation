"""
小红书数据分析模块
提供帖子分析、账号统计等功能
"""

import logging
from typing import Dict, List, Optional

from .mcp_client import get_mcp_client
from .database import get_database

logger = logging.getLogger(__name__)


class XHSAnalytics:
    """小红书数据分析类"""
    
    def __init__(self):
        self.mcp_client = get_mcp_client()
        self.db = get_database()
    
    def get_post_stats(self, feed_id: str, xsec_token: str) -> Dict:
        """获取帖子互动数据
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
        
        Returns:
            {'likes': int, 'collects': int, 'comments': int, 'shares': int}
        """
        detail = self.mcp_client.get_feed_detail(feed_id, xsec_token)
        
        if not detail:
            logger.warning(f"无法获取帖子 {feed_id} 的详情")
            return {'likes': 0, 'collects': 0, 'comments': 0, 'shares': 0}
        
        note = detail.get('note', {})
        interact_info = note.get('interactInfo', {})
        
        stats = {
            'likes': int(interact_info.get('likedCount', 0) or 0),
            'collects': int(interact_info.get('collectedCount', 0) or 0),
            'comments': int(interact_info.get('commentCount', 0) or 0),
            'shares': int(interact_info.get('shareCount', 0) or 0)
        }
        
        # 保存到数据库
        self.db.add_post_analytics(
            post_id=feed_id,
            likes=stats['likes'],
            collects=stats['collects'],
            comments=stats['comments'],
            shares=stats['shares']
        )
        
        return stats
    
    def refresh_post_stats(self, post_id: str) -> Optional[Dict]:
        """刷新帖子统计数据
        
        Args:
            post_id: 小红书帖子ID
        
        Returns:
            更新后的统计数据
        """
        post = self.db.get_post_by_xhs_id(post_id)
        if not post:
            logger.warning(f"未找到帖子记录: {post_id}")
            return None
        
        xsec_token = post.get('xsec_token')
        if not xsec_token:
            logger.warning(f"帖子 {post_id} 缺少 xsec_token")
            return None
        
        return self.get_post_stats(post_id, xsec_token)
    
    def get_post_detail(self, feed_id: str, xsec_token: str) -> Dict:
        """获取帖子详细信息
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
        
        Returns:
            帖子详情字典
        """
        return self.mcp_client.get_feed_detail(feed_id, xsec_token)
    
    def batch_refresh_posts(self, limit: int = 10) -> Dict:
        """批量刷新帖子数据
        
        Args:
            limit: 刷新数量
        
        Returns:
            刷新结果统计
        """
        posts = self.db.get_posts(limit=limit, status='success')
        
        success = 0
        failed = 0
        
        for post in posts:
            post_id = post.get('post_id')
            if post_id:
                try:
                    stats = self.refresh_post_stats(post_id)
                    if stats:
                        success += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"刷新帖子 {post_id} 失败: {e}")
                    failed += 1
        
        return {
            'success': success,
            'failed': failed,
            'total': len(posts)
        }
    
    def get_post_comments(self, feed_id: str, xsec_token: str, limit: int = 20) -> List[Dict]:
        """获取帖子评论
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
            limit: 评论数量
        
        Returns:
            评论列表
        """
        return self.mcp_client.get_comments(feed_id, xsec_token, limit)
    
    def get_user_posts(self, user_id: str, xsec_token: str, limit: int = 20) -> List[Dict]:
        """获取用户帖子列表
        
        Args:
            user_id: 用户ID
            xsec_token: 安全令牌
            limit: 帖子数量
        
        Returns:
            帖子列表
        """
        profile = self.mcp_client.get_user_profile(user_id, xsec_token)
        
        if profile:
            return profile.get('notes', [])
        return []


_analytics_instance: Optional[XHSAnalytics] = None

def get_analytics() -> XHSAnalytics:
    """获取数据分析单例"""
    global _analytics_instance
    if _analytics_instance is None:
        _analytics_instance = XHSAnalytics()
    return _analytics_instance
