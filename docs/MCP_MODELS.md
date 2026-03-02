# 数据模型定义

本文档详细定义 MCP 接口中使用的数据结构。

## 目录

- [1. Feed（帖子/笔记）](#1-feed帖子笔记)
- [2. User（用户）](#2-user用户)
- [3. Comment（评论）](#3-comment评论)
- [4. Interaction（互动数据）](#4-interaction互动数据)
- [5. 其他数据结构](#5-其他数据结构)

---

## 1. Feed（帖子/笔记）

### 1.1 Feed 对象

```typescript
interface Feed {
  // 基础信息
  feed_id: string;           // 笔记ID
  title: string;             // 标题
  desc: string;              // 描述/摘要
  content: string;           // 正文内容

  // 作者信息
  user: User;                // 用户对象

  // 媒体内容
  images: string[];          // 图片URL列表（图文笔记）
  video?: VideoInfo;         // 视频信息（视频笔记）

  // 互动数据
  interactions: Interaction;  // 互动数据

  // 标签信息
  tags: Tag[];               // 话题标签
  at_users?: User[];         // @用户列表

  // 位置信息
  location?: Location;       // 地理位置

  // 时间信息
  time: number;              // 发布时间（时间戳）
  formatted_time: string;    // 格式化时间

  // 令牌（用于后续操作）
  xsec_token: string;        // 访问令牌
  xsec_source: string;       // 来源标识

  // 其他
  note_type: number;         // 笔记类型：0-图文/1-视频/2-文字
  is_private: boolean;       // 是否私密
  is_friend: boolean;        // 是否好友
  is_red_book: boolean;      // 是否小红书号
}
```

### 1.2 VideoInfo（视频信息）

```typescript
interface VideoInfo {
  video_id: string;          // 视频ID
  url: string;               // 视频URL
  cover: string;             // 封面图
  duration: number;          // 时长（秒）
  width: number;             // 宽度
  height: number;           // 高度
  size: number;             // 文件大小（字节）
}
```

---

## 2. User（用户）

### 2.1 User 对象

```typescript
interface User {
  // 基础信息
  user_id: string;           // 用户ID
  nickname: string;          // 昵称
  avatar: string;             // 头像URL
  desc: string;               // 个人简介
  gender: number;            // 性别：0-未知/1-男/2-女

  // 认证信息
  auth_type?: string;         // 认证类型
  auth_info?: string;         // 认证信息

  // IP属地
  IPLocation?: string;       // IP属地

  // 社交关系
  follow_count: number;       // 关注数
  fans_count: number;        // 粉丝数
  collect_count?: number;     // 收藏数（被收藏）

  // 获赞与笔记
  liked_count: number;       // 获赞数
  note_count: number;        // 笔记数
  red_book_count?: number;   // 小红书号笔记数

  // 位置
  location?: string;          // 地区

  // 标签
  tags?: string[];            // 用户标签

  // 其他
  relation_status?: number;   // 关系状态：0-未关注/1-已关注/2-互关
  is_middle_sea?: boolean;   // 是否海中
  is_black?: boolean;        // 是否拉黑
  image_badge?: string;      // 头像徽章
}
```

### 2.2 UserBasicInfo（用户基本信息）

```typescript
interface UserBasicInfo {
  user_id: string;           // 用户ID
  nickname: string;          // 昵称
  avatar: string;             // 头像
  desc: string;              // 简介
  gender: number;            // 性别
  IPLocation: string;        // IP属地
  image_badge: string;       // 头像徽章
  type: string;              // 类型
  red_book_verified?: boolean; // 小红书认证
  verified?: boolean;        // 官方认证
  verified_content?: string;  // 认证内容
}
```

### 2.3 UserInteractions（用户互动统计）

```typescript
interface UserInteractions {
  count: number;              // 数量
  type: string;               // 类型
}
```

**type 可选值**:

| 值 | 说明 |
|----|------|
| follow | 关注 |
| fans | 粉丝 |
| like | 获赞 |
| collect | 收藏 |
| note | 笔记 |

---

## 3. Comment（评论）

### 3.1 Comment 对象

```typescript
interface Comment {
  // 基础信息
  comment_id: string;         // 评论ID
  content: string;            // 评论内容

  // 评论者信息
  user: User;                 // 评论用户
  user_id: string;            // 评论用户ID

  // 父评论信息
  parent_comment_id?: string; // 父评论ID（一级评论为空）
  root_comment_id?: string;  // 根评论ID

  // 互动数据
  like_count: number;        // 点赞数
  reply_count: number;       // 回复数

  // 时间
  create_time: number;       // 发布时间
  formatted_time: string;    // 格式化时间

  // 状态
  status: number;            // 状态码

  // 子评论
  sub_comments?: Comment[];  // 子评论列表（需要展开）
}
```

### 3.2 CommentLoadConfig（评论加载配置）

```typescript
interface CommentLoadConfig {
  // 是否点击"更多回复"按钮
  click_more_replies: boolean;

  // 回复数量阈值，超过这个数量的"更多"按钮将被跳过
  // 0 表示不跳过任何
  max_replies_threshold: number;

  // 最大加载评论数（.parent-comment数量）
  // 0 表示加载所有
  max_comment_items: number;

  // 滚动速度等级
  // slow: 慢速
  // normal: 正常
  // fast: 快速
  scroll_speed: string;
}
```

---

## 4. Interaction（互动数据）

### 4.1 Interaction 对象

```typescript
interface Interaction {
  // 互动计数
  liked_count: number;       // 点赞数
  collected_count: number;   // 收藏数
  comment_count: number;    // 评论数
  share_count: number;      // 分享数

  // 用户状态（当前用户是否已互动）
  liked: boolean;            // 是否已点赞
  collected: boolean;        // 是否已收藏

  // 播放数据（视频）
  play_count?: number;       // 播放数
  download_count?: number;   // 下载数
}
```

---

## 5. 其他数据结构

### 5.1 Tag（标签）

```typescript
interface Tag {
  id: string;                // 标签ID
  name: string;              // 标签名称
  type: number;             // 标签类型
  link: string;             // 话题链接
}
```

### 5.2 Location（位置）

```typescript
interface Location {
  // 位置名称
  name: string;             // 位置名称
  address: string;          // 详细地址

  // 坐标
  lat: number;              // 纬度
  lng: number;              // 经度

  // 其他
  country: string;          // 国家
  province: string;         // 省份
  city: string;             // 城市
  district: string;         // 区/县
}
```

### 5.3 FilterOption（搜索筛选选项）

```typescript
interface FilterOption {
  // 排序依据
  // 综合（默认）
  // 最新
  // 最多点赞
  // 最多评论
  // 最多收藏
  sort_by?: string;

  // 笔记类型
  // 不限（默认）
  // 视频
  // 图文
  note_type?: string;

  // 发布时间
  // 不限（默认）
  // 一天内
  // 一周内
  // 半年内
  publish_time?: string;

  // 搜索范围
  // 不限（默认）
  // 已看过
  // 未看过
  // 已关注
  search_scope?: string;

  // 位置距离
  // 不限（默认）
  // 同城
  // 附近
  location?: string;
}
```

### 5.4 PublishRequest（发布请求）

```typescript
interface PublishRequest {
  // 必填
  title: string;            // 标题（最多20字）
  content: string;           // 正文（最多1000字）
  images: string[];         // 图片列表（至少1张）

  // 可选
  tags?: string[];           // 话题标签
  schedule_at?: string;      // 定时发布时间（ISO8601）
  is_original?: boolean;     // 是否声明原创
  visibility?: string;      // 可见范围
}
```

### 5.5 LoginStatusResponse（登录状态响应）

```typescript
interface LoginStatusResponse {
  is_logged_in: boolean;     // 是否已登录
  username?: string;         // 用户昵称（已登录时）
}
```

### 5.6 LoginQrcodeResponse（登录二维码响应）

```typescript
interface LoginQrcodeResponse {
  timeout: string;          // 超时时间，如 "4m0s"
  is_logged_in: boolean;    // 是否已登录
  img?: string;             // 二维码 Base64 数据
}
```

### 5.7 PublishResponse（发布响应）

```typescript
interface PublishResponse {
  title: string;            // 标题
  content: string;          // 正文
  images?: number;          // 图片数量
  video?: string;          // 视频路径
  status: string;           // 状态："发布完成"
  post_id?: string;         // 帖子ID
}
```

---

## 字段类型速查表

| 类型 | 说明 | 可选值 |
|------|------|--------|
| number | 数字 | - |
| string | 字符串 | - |
| boolean | 布尔值 | true/false |
| object | 对象 | - |
| array | 数组 | [] |
| string[] | 字符串数组 | ["a", "b"] |

### 常见 number 类型

| 字段 | 值 | 说明 |
|------|-----|------|
| gender | 0 | 未知 |
| | 1 | 男 |
| | 2 | 女 |
| note_type | 0 | 图文 |
| | 1 | 视频 |
| | 2 | 文字 |
| relation_status | 0 | 未关注 |
| | 1 | 已关注 |
| | 2 | 互关 |

---

*数据模型定义基于 xiaohongshu-mcp v2.0.0，如有问题请提交 Issue。*
