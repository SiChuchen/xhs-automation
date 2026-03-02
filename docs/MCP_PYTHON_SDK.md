# Python SDK 使用指南

本文档说明如何使用 `src/mcp_client.py` 调用小红书 MCP 服务。

## 目录

- [1. 快速开始](#1-快速开始)
- [2. 现有功能](#2-现有功能)
- [3. 扩展方法示例](#3-扩展方法示例)
- [4. 待实现功能](#4-待实现功能)
- [5. 最佳实践](#5-最佳实践)
- [6. 错误处理](#6-错误处理)

---

## 1. 快速开始

### 1.1 安装依赖

```bash
pip install requests
```

### 1.2 基本用法

```python
import sys
sys.path.insert(0, '/home/ubuntu/xhs-automation')

from src.mcp_client import get_mcp_client

# 获取 MCP 客户端单例
client = get_mcp_client()

# 检查登录状态
is_logged_in = client.check_login_status()
print(f"登录状态: {is_logged_in}")
```

### 1.3 初始化参数

```python
from src.mcp_client import XHSMCPClient

# 自定义 MCP 地址
client = XHSMCPClient(base_url="http://localhost:18060")
```

---

## 2. 现有功能

### 2.1 已实现的便捷方法

| 方法 | 功能 | 状态 |
|------|------|------|
| `check_login_status()` | 检查登录状态 | ✅ 已实现 |
| `get_login_qrcode()` | 获取登录二维码 | ✅ 已实现 |
| `delete_cookies()` | 删除 cookies | ✅ 已实现 |
| `publish_content()` | 发布图文 | ✅ 已实现 |
| `publish_video()` | 发布视频 | ✅ 已实现 |
| `search(keyword)` | 搜索内容 | ✅ 已实现 |
| `get_feeds(limit)` | 获取首页推荐 | ✅ 已实现 |
| `get_feed_detail(feed_id, xsec_token)` | 获取笔记详情 | ✅ 已实现 |
| `like_feed(feed_id, xsec_token)` | 点赞 | ✅ 已实现 |
| `unlike_feed(feed_id, xsec_token)` | 取消点赞 | ✅ 已实现 |
| `favorite_feed(feed_id, xsec_token)` | 收藏 | ✅ 已实现 |
| `unfavorite_feed(feed_id, xsec_token)` | 取消收藏 | ✅ 已实现 |
| `post_comment(feed_id, xsec_token, content)` | 发表评论 | ✅ 已实现 |
| `reply_comment(feed_id, xsec_token, content)` | 回复评论 | ✅ 已实现 |
| `get_comments(feed_id, xsec_token, limit)` | 获取评论 | ✅ 已实现 |
| `get_user_profile(user_id, xsec_token)` | 获取用户信息 | ✅ 已实现 |
| `call_tool(tool_name, arguments)` | 调用任意工具 | ✅ 已实现 |
| `list_available_tools()` | 列出可用工具 | ✅ 已实现 |

### 2.2 方法详解

#### 2.2.1 check_login_status()

检查当前登录状态。

```python
is_logged_in = client.check_login_status()
print(is_logged_in)  # True 或 False
```

#### 2.2.2 search(keyword)

搜索小红书内容。

```python
# 搜索 "编程" 相关内容
results = client.search("编程")

for feed in results:
    print(f"标题: {feed.get('title')}")
    print(f"ID: {feed.get('feed_id')}")
    print("---")
```

#### 2.2.3 get_feeds(limit)

获取首页推荐列表。

```python
# 获取前 10 条推荐
feeds = client.get_feeds(limit=10)

for feed in feeds:
    print(f"标题: {feed.get('title')}")
    print(f"作者: {feed.get('user', {}).get('nickname')}")
```

#### 2.2.4 get_feed_detail(feed_id, xsec_token)

获取笔记详情。

```python
# 先获取 feeds
feeds = client.get_feeds(limit=1)
feed = feeds[0]

# 获取详情
detail = client.get_feed_detail(
    feed['feed_id'],
    feed['xsec_token']
)

print(f"标题: {detail.get('title')}")
print(f"正文: {detail.get('content')}")
print(f"点赞数: {detail.get('interactions', {}).get('liked_count')}")
```

#### 2.2.5 like_feed(feed_id, xsec_token)

点赞笔记。

```python
feeds = client.get_feeds(limit=1)
feed = feeds[0]

success = client.like_feed(feed['feed_id'], feed['xsec_token'])
print(f"点赞结果: {success}")
```

#### 2.2.6 favorite_feed(feed_id, xsec_token)

收藏笔记。

```python
feeds = client.get_feeds(limit=1)
feed = feeds[0]

success = client.favorite_feed(feed['feed_id'], feed['xsec_token'])
print(f"收藏结果: {success}")
```

#### 2.2.7 post_comment(feed_id, xsec_token, content)

发表评论。

```python
feeds = client.get_feeds(limit=1)
feed = feeds[0]

success = client.post_comment(
    feed['feed_id'],
    feed['xsec_token'],
    "写得真好，收藏了！"
)
print(f"评论结果: {success}")
```

#### 2.2.8 get_comments(feed_id, xsec_token, limit)

获取评论列表。

```python
feeds = client.get_feeds(limit=1)
feed = feeds[0]

comments = client.get_comments(
    feed['feed_id'],
    feed['xsec_token'],
    limit=20
)

for comment in comments:
    print(f"评论内容: {comment.get('content')}")
    print(f"评论用户: {comment.get('user', {}).get('nickname')}")
```

#### 2.2.9 get_user_profile(user_id, xsec_token)

获取用户信息。

```python
feeds = client.get_feeds(limit=1)
feed = feeds[0]
user = feed['user']

profile = client.get_user_profile(
    user['user_id'],
    feed['xsec_token']
)

print(f"昵称: {profile.get('userBasicInfo', {}).get('nickname')}")
print(f"简介: {profile.get('userBasicInfo', {}).get('desc')}")
```

#### 2.2.10 call_tool(tool_name, arguments)

调用任意 MCP 工具。

```python
# 通用调用方式
result = client.call_tool("tool_name", {
    "param1": "value1",
    "param2": "value2"
})
```

---

## 3. 扩展方法示例

### 3.1 搜索带筛选条件

```python
def search_with_filters(client, keyword, sort_by="最多点赞", note_type="图文"):
    """带筛选条件的搜索"""
    result = client.call_tool("search_feeds", {
        "keyword": keyword,
        "filters": {
            "sort_by": sort_by,
            "note_type": note_type
        }
    })
    return result.get("feeds", [])

# 使用
feeds = search_with_filters(client, "Python", sort_by="最多点赞", note_type="图文")
```

### 3.2 获取全部评论

```python
def get_all_comments(client, feed_id, xsec_token, limit=50):
    """获取笔记的全部评论"""
    result = client.call_tool("get_feed_detail", {
        "feed_id": feed_id,
        "xsec_token": xsec_token,
        "load_all_comments": True,
        "limit": limit,
        "click_more_replies": True
    })
    return result.get("comments", [])

# 使用
feeds = client.get_feeds(limit=1)
feed = feeds[0]
comments = get_all_comments(client, feed['feed_id'], feed['xsec_token'], limit=30)
```

### 3.3 取消点赞/收藏

```python
def unlike_feed(client, feed_id, xsec_token):
    """取消点赞"""
    return client.call_tool("like_feed", {
        "feed_id": feed_id,
        "xsec_token": xsec_token,
        "unlike": True
    })

def unfavorite_feed(client, feed_id, xsec_token):
    """取消收藏"""
    return client.call_tool("favorite_feed", {
        "feed_id": feed_id,
        "xsec_token": xsec_token,
        "unfavorite": True
    })
```

### 3.4 自动互动流程

```python
def auto_interact(client, target_keyword, max_actions=10):
    """自动互动：搜索 -> 点赞 -> 收藏 -> 评论"""
    
    # 搜索目标内容
    feeds = client.search(target_keyword)
    
    actions_count = 0
    for feed in feeds[:max_actions]:
        feed_id = feed.get('feed_id')
        xsec_token = feed.get('xsec_token')
        
        if not feed_id or not xsec_token:
            continue
        
        # 点赞
        client.like_feed(feed_id, xsec_token)
        actions_count += 1
        
        # 收藏
        client.favorite_feed(feed_id, xsec_token)
        actions_count += 1
        
        # 评论（随机选择模板）
        import random
        comments = [
            "学到了！感谢分享~",
            "太强了，收藏了！",
            "这个真的有用，点赞👍"
        ]
        client.post_comment(feed_id, xsec_token, random.choice(comments))
        actions_count += 1
        
        print(f"已完成互动: {feed.get('title')}")
        
    return actions_count
```

---

## 4. 已实现功能（补充）

以下功能已在 `mcp_client.py` 中封装为便捷方法：

| 功能 | 方法名称 | 状态 | 说明 |
|------|---------|------|------|
| 发布图文 | `publish_content()` | ✅ 已实现 | 支持图片、标签、定时发布 |
| 发布视频 | `publish_video()` | ✅ 已实现 | 仅支持本地视频文件 |
| 获取登录二维码 | `get_login_qrcode()` | ✅ 已实现 | 返回 Base64 二维码图片 |
| 删除 cookies | `delete_cookies()` | ✅ 已实现 | 重置登录状态 |
| 回复评论 | `reply_comment()` | ✅ 已实现 | 回复指定评论 |
| 取消点赞 | `unlike_feed()` | ✅ 已实现 | 取消已点赞的帖子 |
| 取消收藏 | `unfavorite_feed()` | ✅ 已实现 | 取消已收藏的帖子 |

### 4.1 发布图文

```python
# 使用便捷方法
result = client.publish_content(
    title="测试标题",
    content="正文内容",
    images=["/path/to/image.jpg"],
    tags=["#测试", "#小红书"],
    is_original=True,
    visibility="公开可见"
)

print(result)
# {'success': True, 'title': '测试标题', 'status': '发布完成', 'images': 1}
```

### 4.2 发布视频

```python
result = client.publish_video(
    title="测试视频",
    content="视频正文",
    video="/path/to/video.mp4",
    tags=["#视频"]
)
```

### 4.3 获取登录二维码

```python
result = client.get_login_qrcode()
# result 包含:
# - timeout: 超时时间
# - is_logged_in: 是否已登录
# - img: 二维码 Base64 数据

if result.get("img"):
    print(f"请在 {result['timeout']} 内扫码登录")
    # 保存二维码图片
    import base64
    with open("qrcode.png", "wb") as f:
        f.write(base64.b64decode(result["img"]))
```

### 4.4 删除 cookies

```python
result = client.delete_cookies()
print(result)
# {'success': True, 'message': 'Cookies已删除'}
# 删除后需要重新登录
```

### 4.5 回复评论

```python
# 回复指定评论
result = client.reply_comment(
    feed_id="xxxxx",
    xsec_token="xxxxx",
    content="回复内容",
    comment_id="评论ID"
)

# 或回复用户（不指定评论ID）
result = client.reply_comment(
    feed_id="xxxxx",
    xsec_token="xxxxx",
    content="回复内容",
    user_id="用户ID"
)
```

### 4.6 取消点赞/收藏

```python
# 取消点赞
result = client.unlike_feed(feed_id, xsec_token)

# 取消收藏
result = client.unfavorite_feed(feed_id, xsec_token)
```

---

## 5. 最佳实践

### 5.1 错误重试机制

```python
import time

def call_with_retry(client, func, max_retries=3, delay=2):
    """带重试的调用"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            print(f"第 {attempt + 1} 次尝试失败: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise
```

### 5.2 会话管理

```python
# 避免重复创建客户端
# 推荐使用单例模式

from src.mcp_client import get_mcp_client

# 全局使用同一个客户端实例
client = get_mcp_client()

# 如果需要重新初始化
import src.mcp_client as mcp_module
mcp_module._mcp_client = None
client = get_mcp_client()
```

### 5.3 随机间隔

```python
import random
import time

def random_delay(min_seconds=3, max_seconds=10):
    """随机延迟，避免频繁操作"""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)

# 在连续操作之间添加延迟
for feed in feeds:
    process_feed(feed)
    random_delay()
```

### 5.4 日志记录

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 在关键操作处添加日志
logger.info(f"开始搜索关键词: {keyword}")
results = client.search(keyword)
logger.info(f"搜索完成，结果数量: {len(results)}")
```

---

## 6. 错误处理

### 6.1 常见错误类型

```python
try:
    client = get_mcp_client()
    result = client.search("关键词")
except requests.exceptions.ConnectionError:
    print("MCP 服务未启动，请检查 Docker 容器")
except requests.exceptions.Timeout:
    print("请求超时，请检查网络连接")
except Exception as e:
    print(f"未知错误: {e}")
```

### 6.2 返回值检查

```python
# 总是检查返回值
result = client.call_tool("tool_name", params)

if result is None:
    print("调用失败")
elif isinstance(result, dict):
    if "error" in result:
        print(f"业务错误: {result['error']}")
    else:
        print(f"成功: {result}")
```

---

## 7. 完整示例

```python
#!/usr/bin/env python3
"""
小红书 MCP 客户端使用示例
"""

import sys
import random
import time

sys.path.insert(0, '/home/ubuntu/xhs-automation')

from src.mcp_client import get_mcp_client

def main():
    # 初始化客户端
    client = get_mcp_client()
    
    # 1. 检查登录状态
    print("=" * 50)
    print("1. 检查登录状态")
    is_logged_in = client.check_login_status()
    print(f"登录状态: {'已登录' if is_logged_in else '未登录'}")
    
    if not is_logged_in:
        print("请先登录后再使用")
        return
    
    # 2. 获取首页推荐
    print("\n" + "=" * 50)
    print("2. 获取首页推荐")
    feeds = client.get_feeds(limit=5)
    print(f"获取到 {len(feeds)} 条推荐")
    
    for i, feed in enumerate(feeds, 1):
        print(f"  [{i}] {feed.get('title', '无标题')}")
    
    # 3. 搜索内容
    print("\n" + "=" * 50)
    print("3. 搜索内容")
    search_results = client.search("编程")
    print(f"搜索到 {len(search_results)} 条结果")
    
    # 4. 互动操作
    if feeds:
        feed = feeds[0]
        feed_id = feed.get('feed_id')
        xsec_token = feed.get('xsec_token')
        
        print("\n" + "=" * 50)
        print("4. 互动操作")
        
        # 点赞
        client.like_feed(feed_id, xsec_token)
        print("  ✓ 已点赞")
        time.sleep(1)
        
        # 收藏
        client.favorite_feed(feed_id, xsec_token)
        print("  ✓ 已收藏")
        time.sleep(1)
        
        # 评论
        comments = ["学到了！感谢分享~", "太强了，收藏了！", "点赞支持！"]
        client.post_comment(feed_id, xsec_token, random.choice(comments))
        print("  ✓ 已评论")
    
    print("\n" + "=" * 50)
    print("操作完成!")

if __name__ == "__main__":
    main()
```

---

*如需扩展 SDK 功能，请修改 `src/mcp_client.py` 并更新本文档。*
