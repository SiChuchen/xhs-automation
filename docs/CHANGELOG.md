# 版本历史

本文档记录 xiaohongshu-mcp 的版本更新历史，以及对应的文档更新记录。

---

## 文档维护说明

### 如何检查 MCP 更新

1. **GitHub Releases**: 定期查看 [https://github.com/xpzouying/xiaohongshu-mcp/releases](https://github.com/xpzouying/xiaohongshu-mcp/releases)

2. **GitHub Watch**: 关注项目以获取更新通知

3. **版本号规则**: 
   - 主版本号：重大功能变更
   - 次版本号：新功能添加
   - 修订号：Bug 修复

### 更新记录格式

```markdown
## [MCP版本号] - YYYY-MM-DD

### 新增
- 新增工具/功能

### 变更
- 现有功能变更

### 修复
- Bug 修复

### 文档更新
- 相关文档更新
```

---

## 更新记录

### [MCP v2.0.0] - 2025-XX-XX

#### 新增

- **13 个 MCP 工具**：
  1. `check_login_status` - 检查登录状态
  2. `get_login_qrcode` - 获取登录二维码
  3. `delete_cookies` - 删除 cookies
  4. `publish_content` - 发布图文
  5. `publish_with_video` - 发布视频
  6. `list_feeds` - 获取首页推荐
  7. `search_feeds` - 搜索内容
  8. `get_feed_detail` - 获取笔记详情
  9. `user_profile` - 获取用户主页
  10. `post_comment_to_feed` - 发表评论
  11. `reply_comment_in_feed` - 回复评论
  12. `like_feed` - 点赞/取消点赞
  13. `favorite_feed` - 收藏/取消收藏

- **搜索筛选功能**：
  - sort_by: 综合/最新/最多点赞/最多评论/最多收藏
  - note_type: 不限/视频/图文
  - publish_time: 不限/一天内/一周内/半年内
  - search_scope: 不限/已看过/未看过/已关注
  - location: 不限/同城/附近

- **评论加载配置**：
  - load_all_comments: 加载全部评论
  - limit: 限制评论数量
  - click_more_replies: 展开二级回复
  - reply_limit: 跳过过多回复
  - scroll_speed: 滚动速度

- **定时发布**：
  - 支持 1 小时至 14 天内的定时发布
  - ISO8601 格式

- **可见范围**：
  - 公开可见
  - 仅自己可见
  - 仅互关好友可见

- **原创声明**：
  - is_original 参数

#### MCP 服务变更

- 协议版本：2024-11-05
- 服务端口：18060
- 使用官方 MCP SDK

#### 文档更新

- 2026-03-02: 初始文档创建
  - MCP_API.md - 主文档
  - MCP_TOOLS.md - 工具详情
  - MCP_MODELS.md - 数据模型
  - MCP_PYTHON_SDK.md - Python SDK
  - CHANGELOG.md - 版本历史

---

## 待确认的历史版本

> 以下版本信息需要从 GitHub 历史中补充

### [MCP v1.x.x] - 待补充

---

## 常见问题

### Q: 如何确认当前使用的 MCP 版本？

```bash
# 查看 Docker 镜像版本
docker images | grep xiaohongshu-mcp

# 或在代码中查看
curl http://localhost:18060/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'
```

### Q: MCP 更新后需要做什么？

1. 更新 Docker 镜像
2. 检查是否有新功能
3. 更新本文档
4. 如有新工具，更新 MCP_TOOLS.md
5. 如有字段变更，更新 MCP_MODELS.md
6. 更新 CHANGELOG.md

### Q: 如何获取旧版本文档？

```bash
# 克隆仓库查看历史
git clone https://github.com/xpzouying/xiaohongshu-mcp.git
cd xiaohongshu-mcp
git log --oneline
```

---

## 相关链接

- [xiaohongshu-mcp GitHub](https://github.com/xpzouying/xiaohongshu-mcp)
- [MCP 官方文档](https://modelcontextprotocol.io/)
- [GitHub Releases](https://github.com/xpzouying/xiaohongshu-mcp/releases)
- [贡献指南](https://github.com/xpzouying/xiaohongshu-mcp/blob/main/CONTRIBUTING.md)

---

*最后更新: 2026-03-02*
