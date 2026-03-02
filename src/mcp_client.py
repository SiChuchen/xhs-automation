"""
小红书 MCP 客户端
使用 MCP 协议调用搜索、feeds 等功能
"""

import requests
import json
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class XHSMCPClient:
    """小红书 MCP 客户端"""
    
    def __init__(self, base_url: str = "http://localhost:18060"):
        self.base_url = base_url
        self.mcp_url = f"{base_url}/mcp"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.protocol_version = "2024-11-05"
        self.server_info: Dict = {}
        self.available_tools: Dict = {}
        self._session_id: Optional[str] = None
        self._initialize()
    
    def _request(self, method: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """发送 MCP 请求"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1
        }
        
        try:
            response = self.session.post(
                self.mcp_url, 
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=(5, 60)
            )
            response.raise_for_status()
            
            # Save session ID from response headers
            if "Mcp-Session-Id" in response.headers:
                self._session_id = response.headers["Mcp-Session-Id"]
                self.session.headers.update({"Mcp-Session-Id": self._session_id})
            
            result = response.json()
            
            if "error" in result:
                logger.error(f"MCP error: {result['error']}")
                return None
            
            return result.get("result")
        except Exception as e:
            logger.error(f"MCP request failed: {e}")
            return None
    
    def _initialize(self):
        """初始化 MCP 会话"""
        result = self._request("initialize", {
            "protocolVersion": self.protocol_version,
            "capabilities": {},
            "clientInfo": {
                "name": "xhs-automation",
                "version": "1.0.0"
            }
        })
        
        if result:
            self.server_info = result.get("serverInfo", {})
            logger.info(f"Connected to MCP server: {self.server_info}")
            
            tools_result = self._request("tools/list")
            if tools_result:
                tools = tools_result.get("tools", [])
                self.available_tools = {t["name"]: t for t in tools}
                logger.info(f"Available tools: {list(self.available_tools.keys())}")
        else:
            logger.error("Failed to initialize MCP session")
            self.available_tools = {}
    
    def call_tool(self, tool_name: str, arguments: Optional[Dict] = None) -> Any:
        """调用 MCP 工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
        
        Returns:
            工具执行结果
        """
        if not self.available_tools:
            logger.warning("No tools available, reinitializing...")
            self._initialize()
        
        if tool_name not in self.available_tools:
            logger.error(f"Tool not found: {tool_name}")
            return None
        
        result = self._request("tools/call", {
            "name": tool_name,
            "arguments": arguments or {}
        })
        
        if result and "content" in result:
            try:
                return json.loads(result["content"][0]["text"])
            except:
                return result
        return result
    
    def search(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Dict]:
        """搜索小红书内容
        
        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量
        
        Returns:
            搜索结果列表
        """
        result = self.call_tool("search_feeds", {
            "keyword": keyword
        })
        
        if result and isinstance(result, dict):
            feeds = result.get("feeds", [])
            return feeds
        return []
    
    def get_feeds(self, limit: int = 20) -> List[Dict]:
        """获取首页推荐
        
        Args:
            limit: 返回数量
        
        Returns:
            帖子列表
        """
        result = self.call_tool("list_feeds")
        
        if result and isinstance(result, dict):
            feeds = result.get("feeds", [])
            return feeds[:limit]
        return []
    
    def get_feed_detail(self, feed_id: str, xsec_token: str) -> Dict:
        """获取帖子详情
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
        
        Returns:
            帖子详情
        """
        result = self.call_tool("get_feed_detail", {
            "feed_id": feed_id,
            "xsec_token": xsec_token
        })
        
        return result if result else {}
    
    def like_feed(self, feed_id: str, xsec_token: str) -> bool:
        """点赞帖子
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
        
        Returns:
            是否成功
        """
        result = self.call_tool("like_feed", {
            "feed_id": feed_id,
            "xsec_token": xsec_token
        })
        return result is not None
    
    def favorite_feed(self, feed_id: str, xsec_token: str) -> bool:
        """收藏帖子
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
        
        Returns:
            是否成功
        """
        result = self.call_tool("favorite_feed", {
            "feed_id": feed_id,
            "xsec_token": xsec_token
        })
        return result is not None
    
    def post_comment(self, feed_id: str, xsec_token: str, content: str) -> bool:
        """发表评论
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
            content: 评论内容
        
        Returns:
            是否成功
        """
        result = self.call_tool("post_comment_to_feed", {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            "content": content
        })
        return result is not None
    
    def get_comments(self, feed_id: str, xsec_token: str, limit: int = 20) -> List[Dict]:
        """获取帖子评论
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
            limit: 评论数量
        
        Returns:
            评论列表
        """
        result = self.call_tool("get_feed_detail", {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            "limit": limit
        })
        
        if result and isinstance(result, dict):
            return result.get("comments", [])
        return []
    
    def get_user_profile(self, user_id: str, xsec_token: str) -> Dict:
        """获取用户信息
        
        Args:
            user_id: 用户ID
            xsec_token: 安全令牌
        
        Returns:
            用户信息
        """
        result = self.call_tool("user_profile", {
            "user_id": user_id,
            "xsec_token": xsec_token
        })
        
        return result if result else {}
    
    def check_login_status(self) -> bool:
        """检查登录状态"""
        result = self.call_tool("check_login_status")
        return result.get("is_logged_in", False) if result else False
    
    def list_available_tools(self) -> List[str]:
        """列出所有可用工具"""
        return list(self.available_tools.keys())

    # ==================== 发布功能 ====================
    
    def publish_content(self, title: str, content: str, images: List[str],
                       tags: Optional[List[str]] = None,
                       schedule_at: Optional[str] = None,
                       is_original: bool = False,
                       visibility: str = "公开可见") -> Dict:
        """发布图文内容
        
        Args:
            title: 标题（最多20个字）
            content: 正文内容（最多1000个字）
            images: 图片路径列表（至少1张），支持本地路径或HTTP URL
            tags: 话题标签列表
            schedule_at: 定时发布时间（ISO8601格式，如 2024-01-20T10:30:00+08:00）
            is_original: 是否声明原创
            visibility: 可见范围（公开可见/仅自己可见/仅互关好友可见）
        
        Returns:
            发布结果字典
        """
        params = {
            "title": title,
            "content": content,
            "images": images
        }
        
        if tags:
            params["tags"] = tags
        if schedule_at:
            params["schedule_at"] = schedule_at
        if is_original:
            params["is_original"] = True
        if visibility and visibility != "公开可见":
            params["visibility"] = visibility
        
        result = self.call_tool("publish_content", params)
        
        if result:
            return {
                "success": True,
                "title": result.get("title"),
                "status": result.get("status"),
                "images": result.get("images")
            }
        return {"success": False, "error": "发布失败"}
    
    def publish_video(self, title: str, content: str, video: str,
                     tags: Optional[List[str]] = None,
                     schedule_at: Optional[str] = None,
                     visibility: str = "公开可见") -> Dict:
        """发布视频内容
        
        Args:
            title: 标题（最多20个字）
            content: 正文内容
            video: 本地视频文件绝对路径
            tags: 话题标签列表
            schedule_at: 定时发布时间
            visibility: 可见范围
        
        Returns:
            发布结果字典
        """
        params = {
            "title": title,
            "content": content,
            "video": video
        }
        
        if tags:
            params["tags"] = tags
        if schedule_at:
            params["schedule_at"] = schedule_at
        if visibility and visibility != "公开可见":
            params["visibility"] = visibility
        
        result = self.call_tool("publish_with_video", params)
        
        if result:
            return {
                "success": True,
                "title": result.get("title"),
                "status": result.get("status"),
                "video": result.get("video")
            }
        return {"success": False, "error": "发布失败"}

    # ==================== 登录管理 ====================
    
    def get_login_qrcode(self) -> Dict:
        """获取登录二维码
        
        Returns:
            二维码信息字典，包含:
            - timeout: 超时时间
            - is_logged_in: 是否已登录
            - img: 二维码 Base64 图片数据
        """
        result = self.call_tool("get_login_qrcode")
        return result if result else {}
    
    def delete_cookies(self) -> Dict:
        """删除 cookies，重置登录状态
        
        Returns:
            操作结果字典
        """
        result = self.call_tool("delete_cookies")
        if result:
            return {
                "success": True,
                "message": result.get("message", "Cookies已删除")
            }
        return {"success": False, "error": "删除失败"}

    # ==================== 互动功能 ====================
    
    def reply_comment(self, feed_id: str, xsec_token: str, content: str,
                     comment_id: Optional[str] = None,
                     user_id: Optional[str] = None) -> Dict:
        """回复评论
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
            content: 回复内容
            comment_id: 目标评论ID（与 user_id 二选一）
            user_id: 目标评论用户ID（与 comment_id 二选一）
        
        Returns:
            回复结果字典
        """
        params = {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            "content": content
        }
        
        if comment_id:
            params["comment_id"] = comment_id
        if user_id:
            params["user_id"] = user_id
        
        result = self.call_tool("reply_comment_in_feed", params)
        
        if result:
            return {
                "success": True,
                "feed_id": result.get("feed_id"),
                "target_comment_id": result.get("target_comment_id"),
                "target_user_id": result.get("target_user_id")
            }
        return {"success": False, "error": "回复失败"}
    
    def unlike_feed(self, feed_id: str, xsec_token: str) -> Dict:
        """取消点赞
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
        
        Returns:
            操作结果字典
        """
        result = self.call_tool("like_feed", {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            "unlike": True
        })
        
        if result:
            return {"success": True, "feed_id": result.get("feed_id")}
        return {"success": False, "error": "取消点赞失败"}
    
    def unfavorite_feed(self, feed_id: str, xsec_token: str) -> Dict:
        """取消收藏
        
        Args:
            feed_id: 帖子ID
            xsec_token: 安全令牌
        
        Returns:
            操作结果字典
        """
        result = self.call_tool("favorite_feed", {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            "unfavorite": True
        })
        
        if result:
            return {"success": True, "feed_id": result.get("feed_id")}
        return {"success": False, "error": "取消收藏失败"}


_mcp_client: Optional[XHSMCPClient] = None

def get_mcp_client() -> XHSMCPClient:
    """获取 MCP 客户端单例"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = XHSMCPClient()
    return _mcp_client
