# 小红书自动化运营系统

基于 xiaohongshu-mcp 实现的小红书自动化内容发布与运营系统。

## 系统概述

本系统通过小红书 MCP (Model Context Protocol) 官方 Docker 镜像实现自动化内容发布、搜索、互动等操作，支持：

- 🤖 **自动化发布**：定时发布笔记，支持 AI 生成内容
- 🔍 **智能搜索**：关键词搜索与缓存
- 👍 **自动互动**：自动评论、点赞、收藏增加曝光
- 📊 **数据统计**：发布记录与效果追踪
- 🎯 **热门话题**：自动获取微博/小红书热门话题
- ⚙️ **交互式配置**：可视化配置向导

## 快速开始

### 方式一：交互式配置向导（推荐）

```bash
cd /home/ubuntu/xhs-automation
python3 main.py setup
```

按照向导提示完成：
1. 环境检测（Docker、网络、MCP容器）
2. MCP 登录配置（粘贴 cookies 或使用登录工具）
3. LLM 配置（MiniMax/DeepSeek/OpenAI）- 配置完成后可测试连接
4. 文生图配置（RunningHub/DALL-E）
5. 角色配置（预设角色 / AI智能生成 / 手动创建）
6. 自动互动配置
7. 热门话题配置

### 方式二：手动配置

```bash
# 1. 克隆项目
git clone <repository-url>
cd xhs-automation

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动 MCP 容器
docker run -d --name xiaohongshu-mcp \
  -p 18060:18060 \
  -v ~/.xhs-cookies:/app/data \
  crpi-hocnvtkomt7w9v8t.cn-beijing.personal.cr.aliyuncs.com/xpzouying/xiaohongshu-mcp

# 5. 配置登录
# 方法1: 粘贴 cookies.json 内容
# 方法2: 使用登录工具
docker exec -it xiaohongshu-mcp xiaohongshu-login

# 6. 检查状态
python3 main.py status
```

## 命令行工具

### 基础命令

```bash
# 检查登录状态
python3 main.py status

# 搜索内容
python3 main.py search "关键词" --limit 10

# 发布笔记
python3 main.py publish -t "标题" -c "内容" -i "/path/to/image.jpg" --tags "标签1,标签2"

# 自动互动（评论、点赞、收藏）
python3 main.py interact

# 查看统计数据
python3 main.py stats --days 7 --top 5

# 清理数据库
python3 main.py cleanup --days 30 --vacuum
```

### 交互式配置

```bash
# 启动交互式配置向导
python3 main.py setup
```

### AI 智能生成角色

配置好 LLM 后，在角色配置阶段可以选择「AI 智能生成角色」：

```bash
# 在配置向导中选择:
# 4. 角色配置 -> 选择: AI 智能生成角色

# 输入示例:
# "我想要一个分享编程知识和AI工具的科技博主"
# "我想要一个分享美食和生活方式的小姐姐"
```

AI 会根据你的描述生成完整的角色设定，包括：
- 中英文名称
- 角色描述
- 趋势来源选择
- 目标关键词

如果不满意，可以继续对话让 AI 修改，直到满意为止。

### 热门话题

```bash
# 获取所有热门话题
python3 main.py trending

# 仅获取微博热搜
python3 main.py trending --source weibo

# 仅获取小红书热门
python3 main.py trending --source xiaohongshu

# 按关键词过滤
python3 main.py trending --keyword "AI,编程"

# 保存到文件
python3 main.py trending --output trending.json
```

## 项目结构

```
xhs-automation/
├── config/                     # 配置文件
│   ├── publish_config.json     # 发布配置
│   ├── runninghub_config.json  # AI生图配置
│   ├── monitoring_config.json  # 监控告警配置
│   ├── llm_config.json         # LLM配置
│   ├── auto_interact_config.json # 自动互动配置
│   └── prompt_templates.json  # 提示词模板
├── src/                       # 核心代码
│   ├── __init__.py
│   ├── database.py            # SQLite 数据库模块
│   ├── xhs_api_client.py      # API 客户端封装
│   ├── mcp_client.py          # MCP 协议客户端
│   ├── auto_interact.py       # 自动互动模块
│   └── analytics.py           # 数据分析模块
├── scripts/                   # 运维脚本
│   ├── setup.py               # 交互式配置向导
│   ├── trending_fetcher.py    # 热门话题获取器
│   ├── auto_interact_task.py  # 定时互动任务
│   ├── llm_content_generator.py # AI内容生成
│   └── ...
├── data/                      # 数据存储
│   └── xhs_data.db            # SQLite 数据库
├── images/                    # 图片目录
├── main.py                    # 命令行入口
└── requirements.txt
```

## 配置说明

### 用户配置目录

所有用户配置保存在 `~/.xhs-automation/config/`：

```
~/.xhs-automation/config/
├── config.json              # 主配置
├── mcp_config.json         # MCP 配置
├── llm_config.json         # LLM 配置
├── image_config.json       # 文生图配置
├── role_config.json        # 角色配置
├── auto_interact_config.json # 自动互动配置
├── trending_config.json    # 热门话题配置
└── cookies.json            # 登录 cookies
```

### 自动互动配置

编辑 `config/auto_interact_config.json`：

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
    "trending": ["开学", "实习", "春招", "秋招"]
  },
  "comment_templates": [
    "学到了！感谢分享~",
    "太强了，收藏了！",
    "这个真的有用，点赞👍"
  ],
  "comment_llm_enabled": true
}
```

### LLM 配置

编辑 `config/llm_config.json`：

```json
{
  "provider": "minimax",
  "model": "MiniMax-M2.5",
  "api_key": "your-api-key",
  "base_url": "https://api.minimax.chat/v1",
  "temperature": 0.8,
  "max_tokens": 1000
}
```

### 文生图配置

编辑 `config/image_config.json`：

```json
{
  "enabled": true,
  "provider": "runninghub",
  "api_key": "your-runninghub-api-key",
  "base_url": "https://www.runninghub.cn",
  "default_style": "真实摄影",
  "default_size": "1024x1024"
}
```

支持的提供商：
- **RunningHub**: 免费额度，推荐使用
- **DALL-E**: OpenAI 的图像生成服务

### 预设角色

系统内置 3 个预设角色：

| 角色 | 说明 |
|------|------|
| 热门话题捕手 | 自动检测并发布热门话题内容 |
| 技术分享专家 | 分享编程技巧和科技资讯 |
| 生活方式博主 | 分享生活美学和日常好物 |

## MCP 配置详解

### MCP 登录方式

#### 方式一：粘贴 cookies.json（推荐）

```bash
# 运行配置向导，选择"粘贴 cookies.json 内容"
python3 main.py setup

# 或手动保存 cookies 到 ~/.xhs-automation/config/cookies.json
```

cookies.json 格式：
```json
{
  "a1": "your-cookie-a1",
  "webId": "your-webid",
  ...
}
```

#### 方式二：使用登录工具

```bash
docker exec -it xiaohongshu-mcp xiaohongshu-login
```

#### 方式三：MCP Inspector

```bash
# 启动 MCP Inspector
npx @modelcontextprotocol/inspector
```

### MCP 容器管理

```bash
# 启动容器
docker start xiaohongshu-mcp

# 停止容器
docker stop xiaohongshu-mcp

# 查看日志
docker logs xiaohongshu-mcp

# 重新登录
docker exec -it xiaohongshu-mcp xiaohongshu-login
```

## Docker 环境

### 使用国内镜像

如果 Docker Hub 访问缓慢，可使用阿里云镜像：

```bash
docker pull crpi-hocnvtkomt7w9v8t.cn-beijing.personal.cr.aliyuncs.com/xpzouying/xiaohongshu-mcp

docker run -d --name xiaohongshu-mcp \
  -p 18060:18060 \
  -v ~/.xhs-cookies:/app/data \
  crpi-hocnvtkomt7w9v8t.cn-beijing.personal.cr.aliyuncs.com/xpzouying/xiaohongshu-mcp
```

### 网络检测

配置向导会自动检测网络连接，包括：
- Docker Hub
- MiniMax API
- 小红书官网

如遇网络问题，可配置代理或使用国内镜像。

## 定时任务

### 自动互动任务

```bash
# 添加 crontab 任务
crontab -e

# 每天 9:00-21:00 每小时执行一次
0 9-21 * * * cd /home/ubuntu/xhs-automation && python3 scripts/auto_interact_task.py >> logs/auto_interact.log 2>&1
```

### 热门话题获取

```bash
# 每 30 分钟获取一次热门话题
*/30 * * * * cd /home/ubuntu/xhs-automation && python3 scripts/trending_fetcher.py --output data/trending.json >> logs/trending.log 2>&1
```

## 故障排除

### 登录状态失效

```bash
# 重新扫码登录
docker exec -it xiaohongshu-mcp xiaohongshu-login

# 检查登录状态
python3 main.py status
```

### 容器连接问题

```bash
# 检查容器状态
docker ps | grep xiaohongshu

# 查看容器日志
docker logs xiaohongshu-mcp

# 重新启动容器
docker restart xiaohongshu-mcp
```

### MCP 连接问题

```bash
# 检查 MCP 端口
curl http://localhost:18060/health

# 或使用 Python 测试
python3 -c "from src.mcp_client import get_mcp_client; c = get_mcp_client(); print(c.test_connection())"
```

### 数据库问题

```bash
# 清理旧数据
python3 main.py cleanup --days 30 --vacuum

# 查看数据库大小
ls -lh data/xhs_data.db
```

## 更新日志

### 2026-03-01

- 新增交互式配置向导 (`python main.py setup`)
  - 重新调整配置顺序：LLM → 文生图 → 角色
  - LLM 配置完成后可测试连接
  - 新增 AI 智能生成角色功能（对话式，可多次修改）
  - 新增文生图配置（RunningHub/DALL-E）
- 新增热门话题获取器 (`python main.py trending`)
- 新增 MCP 协议客户端
- 新增数据分析模块
- CLI 命令优化

## 相关链接

- [xiaohongshu-mcp 项目](https://github.com/xpzouying/xiaohongshu-mcp)
- [MCP 协议文档](https://modelcontextprotocol.io/)

## 许可证

MIT License
