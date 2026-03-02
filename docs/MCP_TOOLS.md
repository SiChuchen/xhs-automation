# MCP 工具详情

本文档详细说明所有 13 个 MCP 工具的接口定义。

## 目录

- [1. 登录管理](#1-登录管理)
- [2. 内容发布](#2-内容发布)
- [3. 内容获取](#3-内容获取)
- [4. 用户互动](#4-用户互动)

---

## 1. 登录管理

### 1.1 check_login_status

检查小红书登录状态。

```json
{
  "name": "check_login_status",
  "description": "检查小红书登录状态"
}
```

**参数**: 无

**返回示例**:

```json
{
  "is_logged_in": true,
  "username": "用户昵称"
}
```

**返回字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| is_logged_in | boolean | 是否已登录 |
| username | string | 用户昵称（已登录时） |

---

### 1.2 get_login_qrcode

获取登录二维码，用于扫码登录。

```json
{
  "name": "get_login_qrcode",
  "description": "获取登录二维码（返回 Base64 图片和超时时间）"
}
```

**参数**: 无

**返回示例**:

```json
{
  "timeout": "4m0s",
  "is_logged_in": false,
  "img": "data:image/png;base64,..."
}
```

**返回字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| timeout | string | 二维码超时时间 |
| is_logged_in | boolean | 是否已登录 |
| img | string | 二维码 Base64 图片数据 |

---

### 1.3 delete_cookies

删除 cookies 文件，重置登录状态。

```json
{
  "name": "delete_cookies",
  "description": "删除 cookies 文件，重置登录状态。删除后需要重新登录。"
}
```

**参数**: 无

**返回示例**:

```json
{
  "message": "Cookies 已成功删除，登录状态已重置。"
}
```

---

## 2. 内容发布

### 2.1 publish_content

发布小红书图文内容。

```json
{
  "name": "publish_content",
  "description": "发布小红书图文内容"
}
```

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| title | string | ✅ | 内容标题（最多20个字） |
| content | string | ✅ | 正文内容（最多1000个字） |
| images | string[] | ✅ | 图片路径列表（至少1张） |
| tags | string[] | ❌ | 话题标签列表 |
| schedule_at | string | ❌ | 定时发布时间（ISO8601格式） |
| is_original | boolean | ❌ | 是否声明原创 |
| visibility | string | ❌ | 可见范围：公开可见/仅自己可见/仅互关好友可见 |

**参数详细说明**:

- **images**: 支持两种方式
  - HTTP/HTTPS 图片链接：`["https://example.com/image.jpg"]`
  - 本地图片绝对路径（推荐）：`["/Users/user/Pictures/image.jpg"]`

- **schedule_at**: ISO8601 格式
  - 示例：`2024-01-20T10:30:00+08:00`
  - 范围：当前时间 + 1小时 至 当前时间 + 14天

- **visibility**: 
  - 公开可见（默认）
  - 仅自己可见
  - 仅互关好友可见

**返回示例**:

```json
{
  "title": "测试标题",
  "content": "正文内容",
  "images": 1,
  "status": "发布完成"
}
```

---

### 2.2 publish_with_video

发布小红书视频内容（仅支持本地单个视频文件）。

```json
{
  "name": "publish_with_video",
  "description": "发布小红书视频内容（仅支持本地单个视频文件）"
}
```

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| title | string | ✅ | 内容标题（最多20个字） |
| content | string | ✅ | 正文内容 |
| video | string | ✅ | 本地视频绝对路径 |
| tags | string[] | ❌ | 话题标签列表 |
| schedule_at | string | ❌ | 定时发布时间 |
| visibility | string | ❌ | 可见范围 |

**注意**: 
- video 参数仅支持本地视频文件绝对路径
- 不支持 HTTP 链接
- 建议视频文件大小不超过 1GB
- 视频处理时间较长，请耐心等待

**返回示例**:

```json
{
  "title": "测试视频",
  "content": "视频正文",
  "video": "/path/to/video.mp4",
  "status": "发布完成"
}
```

---

## 3. 内容获取

### 3.1 list_feeds

获取首页推荐列表。

```json
{
  "name": "list_feeds",
  "description": "获取首页 Feeds 列表"
}
```

**参数**: 无

**返回示例**:

```json
{
  "feeds": [
    {
      "feed_id": "xxxxx",
      "title": "笔记标题",
      "desc": "笔记描述",
      "user": {
        "user_id": "xxxxx",
        "nickname": "用户昵称",
        "avatar": "头像URL"
      },
      "interactions": {
        "liked_count": 100,
        "collected_count": 50,
        "comment_count": 10
      },
      "images": ["图片URL列表"],
      "xsec_token": "用于获取详情的令牌",
      "xsec_source": "pc_feed"
    }
  ],
  "count": 20
}
```

---

### 3.2 search_feeds

搜索小红书内容。

```json
{
  "name": "search_feeds",
  "description": "搜索小红书内容（需要已登录）"
}
```

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| keyword | string | ✅ | 搜索关键词 |
| filters | object | ❌ | 筛选选项 |

**filters 筛选选项**:

| 字段 | 类型 | 说明 | 可选值 |
|------|------|------|--------|
| sort_by | string | 排序依据 | 综合/最新/最多点赞/最多评论/最多收藏 |
| note_type | string | 笔记类型 | 不限/视频/图文 |
| publish_time | string | 发布时间 | 不限/一天内/一周内/半年内 |
| search_scope | string | 搜索范围 | 不限/已看过/未看过/已关注 |
| location | string | 位置距离 | 不限/同城/附近 |

**调用示例**:

```python
result = client.call_tool("search_feeds", {
    "keyword": "编程",
    "filters": {
        "sort_by": "最多点赞",
        "note_type": "图文",
        "publish_time": "一周内"
    }
})
```

---

### 3.3 get_feed_detail

获取小红书笔记详情，包括内容、图片、作者信息、互动数据及评论。

```json
{
  "name": "get_feed_detail",
  "description": "获取小红书笔记详情，返回笔记内容、图片、作者信息、互动数据（点赞/收藏/分享数）及评论列表。默认返回前10条一级评论，如需更多评论请设置load_all_comments=true"
}
```

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| feed_id | string | ✅ | 小红书笔记ID |
| xsec_token | string | ✅ | 访问令牌 |
| load_all_comments | boolean | ❌ | 是否加载全部评论 |
| limit | number | ❌ | 加载的一级评论数量（默认20） |
| click_more_replies | boolean | ❌ | 是否展开二级回复 |
| reply_limit | number | ❌ | 跳过回复数过多的评论（默认10） |
| scroll_speed | string | ❌ | 滚动速度：slow/normal/fast |

**注意**: 
- `feed_id` 和 `xsec_token` 从 Feed 列表或搜索结果中获取
- `load_all_comments=true` 时才处理其他评论相关参数

**返回字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| feed_id | string | 笔记ID |
| title | string | 标题 |
| content | string | 正文 |
| user | object | 作者信息 |
| images | string[] | 图片列表 |
| interactions | object | 互动数据 |
| comments | object[] | 评论列表 |

---

## 4. 用户互动

### 4.1 user_profile

获取指定用户的主页信息。

```json
{
  "name": "user_profile",
  "description": "获取指定的小红书用户主页，返回用户基本信息，关注、粉丝、获赞量及其笔记内容"
}
```

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| user_id | string | ✅ | 小红书用户ID |
| xsec_token | string | ✅ | 访问令牌 |

**返回字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| userBasicInfo | object | 用户基本信息 |
| - nickname | string | 昵称 |
| - avatar | string | 头像URL |
| - desc | string | 简介 |
| - gender | number | 性别：0未知/1男/2女 |
| - IPLocation | string | IP属地 |
| interactions | object[] | 互动数据 |
| - count | number | 数量 |
| - type | string | 类型：关注/粉丝/获赞/笔记 |
| feeds | object[] | 用户笔记列表 |

---

### 4.2 post_comment_to_feed

发表评论到小红书笔记。

```json
{
  "name": "post_comment_to_feed",
  "description": "发表评论到小红书笔记"
}
```

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| feed_id | string | ✅ | 小红书笔记ID |
| xsec_token | string | ✅ | 访问令牌 |
| content | string | ✅ | 评论内容 |

**返回示例**:

```json
{
  "feed_id": "xxxxx",
  "success": true,
  "message": "评论发表成功"
}
```

---

### 4.3 reply_comment_in_feed

回复小红书笔记下的指定评论。

```json
{
  "name": "reply_comment_in_feed",
  "description": "回复小红书笔记下的指定评论"
}
```

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| feed_id | string | ✅ | 小红书笔记ID |
| xsec_token | string | ✅ | 访问令牌 |
| content | string | ✅ | 回复内容 |
| comment_id | string | ❌ | 目标评论ID（与 user_id 二选一） |
| user_id | string | ❌ | 目标评论用户ID（与 comment_id 二选一） |

**注意**: comment_id 和 user_id 至少提供一个

**返回示例**:

```json
{
  "feed_id": "xxxxx",
  "target_comment_id": "xxxxx",
  "target_user_id": "xxxxx",
  "success": true,
  "message": "评论回复成功"
}
```

---

### 4.4 like_feed

为指定笔记点赞或取消点赞。

```json
{
  "name": "like_feed",
  "description": "为指定笔记点赞或取消点赞（如已点赞将跳过点赞，如未点赞将跳过取消点赞）"
}
```

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| feed_id | string | ✅ | 小红书笔记ID |
| xsec_token | string | ✅ | 访问令牌 |
| unlike | boolean | ❌ | 是否取消点赞（true为取消，默认false） |

**返回示例**:

```json
{
  "feed_id": "xxxxx",
  "success": true,
  "message": "点赞成功或已点赞"
}
```

**注意**: 
- 如已点赞再点赞会跳过，如未点赞取消点赞也会跳过
- 不会返回错误

---

### 4.5 favorite_feed

收藏指定笔记或取消收藏。

```json
{
  "name": "favorite_feed",
  "description": "收藏指定笔记或取消收藏（如已收藏将跳过收藏，如未收藏将跳过取消收藏）"
}
```

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| feed_id | string | ✅ | 小红书笔记ID |
| xsec_token | string | ✅ | 访问令牌 |
| unfavorite | boolean | ❌ | 是否取消收藏（true为取消，默认false） |

**返回示例**:

```json
{
  "feed_id": "xxxxx",
  "success": true,
  "message": "收藏成功或已收藏"
}
```

---

## 附录：错误处理

### 常见错误

| 错误信息 | 说明 | 解决方案 |
|---------|------|---------|
| 检查登录状态失败 | MCP 服务未启动 | 检查 Docker 容器状态 |
| 缺少 feed_id 参数 | 未提供必要参数 | 从 Feed 列表获取 ID |
| 标题长度超过限制 | 小红书规则 | 标题不超过 20 个字 |
| 定时发布时间格式错误 | 格式不正确 | 使用 ISO8601 格式 |

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 参数错误 |
| 500 | 服务器内部错误 |
| 502 | 网关错误（MCP 服务未启动） |
