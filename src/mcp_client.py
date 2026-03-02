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


_mcp_client: Optional[XHSMCPClient] = None

def get_mcp_client() -> XHSMCPClient:
    """获取 MCP 客户端单例"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = XHSMCPClient()
    return _mcp_client
