# 小红书 MCP 接口文档

本项目基于 [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) 实现，文档维护于 `xhs-automation/docs/` 目录。

## 目录

- [1. 概述](./MCP_API.md#1-概述)
- [2. 工具列表](./MCP_TOOLS.md)
- [3. 数据模型](./MCP_MODELS.md)
- [4. Python SDK](./MCP_PYTHON_SDK.md)
- [5. 版本历史](./CHANGELOG.md)

---

## 1. 概述

### 1.1 MCP 服务介绍

MCP (Model Context Protocol) 是小红书官方提供的自动化接口服务，支持：

- 🤖 登录状态管理
- 📝 内容发布（图文/视频）
- 🔍 内容搜索与推荐
- 👍 互动操作（点赞/收藏/评论）
- 👤 用户信息获取

### 1.2 服务地址

```
MCP 地址: http://localhost:18060/mcp
```

### 1.3 连接方式

**HTTP 方式（推荐）**

```bash
# 测试连接
curl -X POST http://localhost:18060/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'
```

**Docker 环境**

```bash
# 在 Docker 容器内使用
http://host.docker.internal:18060/mcp
```

### 1.4 MCP 协议版本

```
Protocol Version: 2024-11-05
Server Version: 2.0.0
```

---

## 2. 快速开始

### 2.1 启动 MCP 服务

```bash
# 使用 Docker 启动
docker run -d --name xiaohongshu-mcp \
  -p 18060:18060 \
  -v ~/.xhs-cookies:/app/data \
  xpzouying/xiaohongshu-mcp
```

### 2.2 Python 调用方式（官方推荐 MCP 协议）

项目统一使用 `src.mcp_client`（MCP 协议），这是官方推荐的接入方式。

```python
from src import get_mcp_client

client = get_mcp_client()

# 检查登录状态
is_logged_in = client.check_login_status()

# 发布图文
result = client.publish_content(
    title="测试标题",
    content="正文内容",
    images=["/path/to/image.jpg"],
    tags=["#测试", "#小红书"]
)

# 搜索内容
results = client.search("关键词")

# 点赞/收藏/评论
client.like_feed(feed_id, xsec_token)
client.favorite_feed(feed_id, xsec_token)
client.post_comment(feed_id, xsec_token, "评论内容")
```

---

## 3. 工具分类

| 分类 | 工具数量 | 工具列表 |
|------|---------|---------|
| 登录管理 | 3 | check_login_status, get_login_qrcode, delete_cookies |
| 内容发布 | 2 | publish_content, publish_with_video |
| 内容获取 | 3 | list_feeds, search_feeds, get_feed_detail |
| 用户互动 | 5 | user_profile, post_comment_to_feed, reply_comment_in_feed, like_feed, favorite_feed |

**共计: 13 个 MCP 工具**

详细接口定义请参阅 [MCP_TOOLS.md](./MCP_TOOLS.md)

---

## 4. 数据模型

主要数据结构包括：

- **Feed**: 帖子/笔记
- **User**: 用户信息
- **Comment**: 评论
- **Interaction**: 互动数据（点赞/收藏/分享/评论数）

详细数据结构请参阅 [MCP_MODELS.md](./MCP_MODELS.md)

---

## 5. Python SDK

项目已封装 `src/mcp_client.py`，提供便捷的 Python 调用接口。

详细使用说明请参阅 [MCP_PYTHON_SDK.md](./MCP_PYTHON_SDK.md)

---

## 6. 注意事项

### 6.1 小红书限制

- 标题：最多 20 个字
- 正文：最多 1000 个字
- 每天建议发布：不超过 50 篇
- 定时发布：支持 1 小时至 14 天

### 6.2 风险提示

- 账号需实名认证
- 避免频繁操作，建议添加随机间隔
- 禁止引流、纯搬运内容

---

## 7. 相关链接

- [xiaohongshu-mcp GitHub](https://github.com/xpzouying/xiaohongshu-mcp)
- [MCP 官方文档](https://modelcontextprotocol.io/)
- [项目计划](../PROJECT_PLAN.md)

---

*文档维护说明：请定期查看 [GitHub Releases](https://github.com/xpzouying/xiaohongshu-mcp/releases) 获取 MCP 更新，并在 [CHANGELOG.md](./CHANGELOG.md) 中记录更新内容。*
