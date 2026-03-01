# 小红书自动化运营项目重构方案

## 一、项目概述

基于现有 xhs-automation 项目进行重构和功能扩展。

## 二、数据库设计（SQLite）

### 表结构

```sql
-- 表1: 发布记录 (posts)
CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT,
    title TEXT,
    content TEXT,
    image_path TEXT,
    tags TEXT,
    module TEXT,
    topic TEXT,
    published_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT
);

-- 表2: 帖子互动数据 (post_analytics)
CREATE TABLE post_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT,
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    likes INTEGER DEFAULT 0,
    collects INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    UNIQUE(post_id, fetched_at)
);

-- 表3: 互动历史 (interactions)
CREATE TABLE interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_post_id TEXT,
    target_keyword TEXT,
    action TEXT,
    content TEXT,
    status TEXT,
    interacted_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 表4: 搜索缓存 (search_cache)
CREATE TABLE search_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT UNIQUE,
    results_json TEXT,
    searched_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 自动清理策略
- 保留30天数据
- 每日凌晨3点执行清理

## 三、功能模块

### 1. API统一封装 (src/xhs_api_client.py)
- check_login_status()
- publish_note()
- search()
- get_feed_list()
- get_feed_detail()
- post_comment()
- get_user_profile()

### 2. 数据分析 (src/analytics.py)
- get_post_stats()
- get_account_summary()
- get_top_posts()

### 3. 自动互动 (src/auto_interact.py)
- 每日评论/点赞/收藏任务
- LLM生成评论内容
- 随机延迟避免风控

## 四、目录结构

```
xhs-automation/
├── config/
│   ├── publish_config.json
│   ├── runninghub_config.json
│   ├── monitoring_config.json
│   ├── prompt_templates.json      [新增]
│   ├── database_config.json       [新增]
│   └── auto_interact_config.json  [新增]
├── src/                           [新增]
│   ├── __init__.py
│   ├── xhs_api_client.py
│   ├── content_generator.py
│   ├── image_generator.py
│   ├── analytics.py
│   ├── auto_interact.py
│   └── database.py
├── data/                          [新增]
│   └── xhs_data.db
├── scripts/
├── logs/
├── images/
├── requirements.txt
├── main.py                        [新增]
└── README.md
```

## 五、配置文件

### config/database_config.json
```json
{
  "database_path": "data/xhs_data.db",
  "retention_days": 30,
  "auto_cleanup": true,
  "cleanup_interval_hours": 24,
  "max_db_size_mb": 100
}
```

### config/auto_interact_config.json
```json
{
  "enabled": true,
  "daily_comment_limit": 15,
  "daily_like_limit": 20,
  "daily_collect_limit": 10,
  "min_interval_seconds": 5,
  "max_interval_seconds": 15,
  "target_keywords": {
    "primary": ["编程技巧", "效率工具", "AI工具", "学习方法"],
    "trending": ["开学", "实习", "考证", "春招"]
  },
  "comment_llm_enabled": true
}
```

### config/prompt_templates.json
```json
{
  "content_generation": {
    "academic_efficiency": {
      "system_prompt": "你是一个20岁计算机专业女大学生...",
      "title_templates": ["关于{topic}，我想说...", "{topic}的正确打开方式"]
    }
  },
  "image_generation": {
    "academic_efficiency": "教育插图风格，{topic}，简洁专业",
    "geek_daily": "科技感场景，{topic}，现代极客风格"
  },
  "comment_generation": {
    "system_prompt": "你是一个热情、有趣的小红书用户...",
    "templates": ["学到了！感谢分享~ 🐶", "太强了，收藏了！"]
  }
}
```

## 六、实施计划

| 阶段 | 任务 |
|------|------|
| Phase 1 | 创建项目结构 + 数据库模块 |
| Phase 2 | 实现 xhs_api_client.py 统一封装 |
| Phase 3 | 实现搜索 + 帖子数据获取功能 |
| Phase 4 | 实现自动互动模块 |
| Phase 5 | 封装提示词模板 + 配置化 |
| Phase 6 | 创建入口脚本 + 重构现有代码 |
| Phase 7 | 编写 README + 测试 |

## 七、确认的问题

- 数据库存储位置: data/xhs_data.db (项目子目录)
- 互动频率: 每日评论15次, 点赞20次, 收藏10次
- 评论内容: LLM生成 + 固定模板备用
