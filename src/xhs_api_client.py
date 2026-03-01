"""
小红书 MCP API 客户端封装
统一封装所有小红书 API 调用
"""

import requests
import logging
import json
import os
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class XHSAPIClient:
    """小红书 MCP API 统一封装"""
    
    def __init__(self, base_url: str = "http://localhost:18060/api/v1", 
                 timeout: int = 120):
        self.base_url = base_url
        self.timeout = timeout
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """统一请求方法"""
        url = f"{self.base_url}/{endpoint}"
        kwargs.setdefault('timeout', self.timeout)
        
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"请求超时: {endpoint}")
            return {'success': False, 'error': '请求超时'}
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {endpoint}, {e}")
            return {'success': False, 'error': str(e)}
    
    # ==================== 登录相关 ====================
    
    def check_login_status(self) -> Tuple[bool, Dict]:
        """检查登录状态
        
        Returns:
            (is_logged_in, data_dict)
        """
        result = self._request('GET', 'login/status')
        
        if result.get('success'):
            data = result.get('data', {})
            is_logged_in = data.get('is_logged_in', False)
            username = data.get('username', 'unknown')
            return is_logged_in, {
                'username': username,
                'message': result.get('message', '')
            }
        return False, {'error': result.get('error', '未知错误')}
    
    def get_login_status_simple(self) -> bool:
        """简单检查登录状态"""
        is_logged_in, _ = self.check_login_status()
        return is_logged_in
    
    # ==================== 发布功能 ====================
    
    def publish_note(self, title: str, content: str, images: Optional[List[str]] = None,
                     tags: Optional[List[str]] = None) -> Dict:
        """发布图文笔记
        
        Args:
            title: 标题 (不超过20字)
            content: 正文内容 (不超过1000字)
            images: 图片路径列表，支持本地路径或HTTP URL
            tags: 标签列表
        
        Returns:
            {'success': bool, 'post_id': str, 'error': str}
        """
        payload = {
            'title': title,
            'content': content
        }
        
        if images:
            payload['images'] = images if isinstance(images, list) else [images]  # type: ignore
        
        if tags:
            payload['tags'] = tags[:10]  # type: ignore
        
        result = self._request('POST', 'publish', json=payload)
        
        if result.get('success'):
            post_id = result.get('data', {}).get('post_id')
            logger.info(f"发布成功: {post_id}")
            return {'success': True, 'post_id': post_id}
        else:
            error = result.get('error', result.get('message', '发布失败'))
            logger.error(f"发布失败: {error}")
            return {'success': False, 'error': error}
    
    def publish_video(self, title: str, content: str, video_path: str,
                     tags: Optional[List[str]] = None) -> Dict:
        """发布视频笔记
        
        Args:
            title: 标题
            content: 正文内容
            video_path: 视频本地路径
            tags: 标签列表
        
        Returns:
            {'success': bool, 'post_id': str, 'error': str}
        """
        payload = {
            'title': title,
            'content': content,
            'video': video_path
        }
        
        if tags:
            payload['tags'] = tags[:10]  # type: ignore
        
        result = self._request('POST', 'publish/video', json=payload)
        
        if result.get('success'):
            post_id = result.get('data', {}).get('post_id')
            return {'success': True, 'post_id': post_id}
        else:
            return {'success': False, 'error': result.get('error', '发布失败')}
    
    # ==================== 搜索功能 ====================
    
    def search(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Dict]:
        """搜索小红书内容
        
        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量
        
        Returns:
            帖子列表 [{'id': str, 'title': str, 'user': dict, 'liked': bool, ...}]
        """
        payload = {
            'keyword': keyword,
            'page': page,
            'page_size': page_size
        }
        
        result = self._request('POST', 'search', json=payload)
        
        if result.get('success'):
            data = result.get('data', {})
            items = data.get('items', []) if isinstance(data, dict) else []
            logger.info(f"搜索'{keyword}'找到 {len(items)} 条结果")
            return items
        else:
            logger.error(f"搜索失败: {result.get('error')}")
            return []
    
    def search_feeds(self, keyword: str, limit: int = 10) -> List[Dict]:
        """简化搜索接口
        
        Args:
            keyword: 搜索关键词
            limit: 返回数量限制
        
        Returns:
            帖子列表
        """
        all_results = []
        for page in range(1, (limit // 20) + 2):
            results = self.search(keyword, page=page)
            if not results:
                break
            all_results.extend(results)
            if len(all_results) >= limit:
                break
        
        return all_results[:limit]
    
    # ==================== 内容列表 ====================
    
    def get_feed_list(self, limit: int = 20) -> List[Dict]:
        """获取首页推荐列表
        
        Args:
            limit: 返回数量
        
        Returns:
            帖子列表
        """
        payload = {'limit': limit}
        result = self._request('GET', 'feeds', json=payload)
        
        if result.get('success'):
            data = result.get('data', {})
            items = data.get('items', []) if isinstance(data, dict) else []
            return items
        return []
    
    # ==================== 帖子详情 ====================
    
    def get_feed_detail(self, feed_id: str, xsec_token: str) -> Dict:
        """获取帖子详情
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌 (从列表或搜索结果中获取)
        
        Returns:
            帖子详情字典
        """
        payload = {
            'feed_id': feed_id,
            'xsec_token': xsec_token
        }
        
        result = self._request('POST', 'feed/detail', json=payload)
        
        if result.get('success'):
            return result.get('data', {})
        else:
            logger.error(f"获取帖子详情失败: {result.get('error')}")
            return {}
    
    def get_post_stats(self, feed_id: str, xsec_token: str) -> Dict:
        """获取帖子互动数据
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
        
        Returns:
            {'likes': int, 'collects': int, 'comments': int, 'shares': int}
        """
        detail = self.get_feed_detail(feed_id, xsec_token)
        
        if not detail:
            return {'likes': 0, 'collects': 0, 'comments': 0, 'shares': 0}
        
        # 从详情中提取互动数据
        interact_info = detail.get('interact_info', {})
        
        return {
            'likes': int(interact_info.get('liked_count', 0)),
            'collects': int(interact_info.get('collected_count', 0)),
            'comments': int(interact_info.get('comment_count', 0)),
            'shares': int(interact_info.get('share_count', 0))
        }
    
    # ==================== 互动功能 ====================
    
    def post_comment(self, feed_id: str, xsec_token: str, content: str) -> Dict:
        """发表评论
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
            content: 评论内容
        
        Returns:
            {'success': bool, 'comment_id': str, 'error': str}
        """
        payload = {
            'feed_id': feed_id,
            'xsec_token': xsec_token,
            'content': content
        }
        
        result = self._request('POST', 'comment/publish', json=payload)
        
        if result.get('success'):
            comment_id = result.get('data', {}).get('comment_id')
            return {'success': True, 'comment_id': comment_id}
        else:
            return {'success': False, 'error': result.get('error', '评论失败')}
    
    def like_post(self, feed_id: str, xsec_token: str) -> Dict:
        """点赞帖子
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
        
        Returns:
            {'success': bool, 'error': str}
        """
        payload = {
            'feed_id': feed_id,
            'xsec_token': xsec_token,
            'action': 'like'
        }
        
        result = self._request('POST', 'interact', json=payload)
        
        if result.get('success'):
            return {'success': True}
        return {'success': False, 'error': result.get('error', '点赞失败')}
    
    def collect_post(self, feed_id: str, xsec_token: str) -> Dict:
        """收藏帖子
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
        
        Returns:
            {'success': bool, 'error': str}
        """
        payload = {
            'feed_id': feed_id,
            'xsec_token': xsec_token,
            'action': 'collect'
        }
        
        result = self._request('POST', 'interact', json=payload)
        
        if result.get('success'):
            return {'success': True}
        return {'success': False, 'error': result.get('error', '收藏失败')}
    
    # ==================== 用户信息 ====================
    
    def get_user_profile(self, user_id: str, xsec_token: Optional[str] = None) -> Dict:
        """获取用户主页信息
        
        Args:
            user_id: 用户ID
            xsec_token: 安全令牌 (可选)
        
        Returns:
            用户信息字典
        """
        payload = {'user_id': user_id}
        if xsec_token:
            payload['xsec_token'] = xsec_token
        
        result = self._request('POST', 'user/profile', json=payload)
        
        if result.get('success'):
            return result.get('data', {})
        return {}
    
    # ==================== 工具方法 ====================
    
    def extract_feed_info(self, feed_item: Dict) -> Dict:
        """从feed项中提取关键信息
        
        Args:
            feed_item: feed列表中的单项
        
        Returns:
            {'id': str, 'xsec_token': str, 'title': str, 'user': dict}
        """
        note_card = feed_item.get('note_card', {})
        
        return {
            'id': note_card.get('note_id', ''),
            'xsec_token': note_card.get('xsec_token', ''),
            'title': note_card.get('title', ''),
            'user': note_card.get('user', {}),
            'liked': note_card.get('interact_info', {}).get('liked', False),
            'collected': note_card.get('interact_info', {}).get('collected', False)
        }


# 全局客户端实例
_api_client = None

def get_xhs_client(base_url: str = "http://localhost:18060/api/v1") -> XHSAPIClient:
    """获取API客户端单例"""
    global _api_client
    if _api_client is None:
        _api_client = XHSAPIClient(base_url)
    return _api_client
