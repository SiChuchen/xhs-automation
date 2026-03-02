# TOOLS.md - 林晓芯的运营工具箱

## 🔧 系统检查工具

### 1. 快速状态检查
```bash
# 一键检查所有状态（推荐）
bash /home/ubuntu/xhs-automation/scripts/check_container.sh
```

### 2. Python 脚本工具

#### 监控模块
```bash
# 完整系统检查
python3 /home/ubuntu/xhs-automation/scripts/monitoring.py --full-check

# Cookie 状态检查
python3 /home/ubuntu/xhs-automation/scripts/monitoring.py --check-cookie

# 系统状态检查
python3 /home/ubuntu/xhs-automation/scripts/monitoring.py --check-system

# 存储清理
python3 /home/ubuntu/xhs-automation/scripts/monitoring.py --cleanup

# 测试告警
python3 /home/ubuntu/xhs-automation/scripts/monitoring.py --test-webhook
```

### 3. 即时发布
```bash
# 立即发布一篇笔记（不等待定时）
python3 /home/ubuntu/xhs-automation/scripts/immediate_publish.py
```

---

## 🎨 图片生成工具

### RunningHub 模块
位置: `/home/ubuntu/runninghub-image-generator/`

```bash
# 基本使用
cd /home/ubuntu/runninghub-image-generator
python3 run.py "一只可爱的猫咪"

# 小红书竖版
python3 run.py "Python教程" --xiaohongshu

# 指定分辨率
python3 run.py "风景画" --resolution 4k

# 使用种子复现
python3 run.py "科技海报" --seed 12345

# 查看统计
python3 run.py --stats
```

### Python API 调用
```python
from runninghub_image_generator import RunningHubImageGenerator

gen = RunningHubImageGenerator(
    consumer_api_key="your_key",
    enterprise_api_key="backup_key"
)

# 生成图片
result = gen.generate("猫咪图片", aspect_ratio="9:16", resolution="2k")
print(result['image_path'])
```

---

## 📱 MCP 容器 API (官方推荐协议)

### 基础端点
- **MCP 协议端点 (推荐)**: `http://localhost:18060/mcp`
- **HTTP API 端点 (旧版)**: `http://localhost:18060/api/v1`

### MCP 协议调用方式

项目已封装 Python SDK，使用官方推荐的 MCP 协议：

```python
from src import get_mcp_client

client = get_mcp_client()

# 检查登录状态
is_logged_in = client.check_login_status()

# 发布图文
result = client.publish_content(
    title="笔记标题",
    content="笔记正文",
    images=["/path/to/image.jpg"],
    tags=["#标签"]
)

# 搜索内容
results = client.search("关键词")

# 获取首页推荐
feeds = client.get_feeds(limit=10)

# 互动操作
client.like_feed(feed_id, xsec_token)
client.favorite_feed(feed_id, xsec_token)
client.post_comment(feed_id, xsec_token, "评论内容")
client.reply_comment(feed_id, xsec_token, "回复内容", comment_id="xxx")

# 获取详情
detail = client.get_feed_detail(feed_id, xsec_token)
profile = client.get_user_profile(user_id, xsec_token)
```

### MCP 工具列表 (13个)

| 工具 | 功能 |
|------|------|
| `check_login_status` | 检查登录状态 |
| `get_login_qrcode` | 获取登录二维码 |
| `delete_cookies` | 删除 cookies |
| `publish_content` | 发布图文 |
| `publish_with_video` | 发布视频 |
| `list_feeds` | 获取首页推荐 |
| `search_feeds` | 搜索内容 |
| `get_feed_detail` | 获取笔记详情 |
| `user_profile` | 获取用户主页 |
| `post_comment_to_feed` | 发表评论 |
| `reply_comment_in_feed` | 回复评论 |
| `like_feed` | 点赞/取消点赞 |
| `favorite_feed` | 收藏/取消收藏 |

### 命令行工具

```bash
# 检查登录状态
python3 /home/ubuntu/xhs-automation/main.py status

# 搜索内容
python3 /home/ubuntu/xhs-automation/main.py search "关键词" --limit 10

# 发布笔记
python3 /home/ubuntu/xhs-automation/main.py publish \
  -t "标题" \
  -c "内容" \
  -i "/path/to/image.jpg" \
  --tags "标签1,标签2"

# 自动互动
python3 /home/ubuntu/xhs-automation/main.py interact

# 查看统计
python3 /home/ubuntu/xhs-automation/main.py stats
```

### 旧版 HTTP API (仅供兼容)

```bash
# 检查登录状态
curl http://localhost:18060/api/v1/login/status

# 发布笔记 (需要 JSON body)
curl -X POST http://localhost:18060/api/v1/publish \
  -H "Content-Type: application/json" \
  -d '{
    "title": "笔记标题",
    "content": "笔记正文",
    "images": ["/path/to/image1.jpg"]
  }'

# 获取笔记信息
curl http://localhost:18060/api/v1/notes

# 搜索话题
curl "http://localhost:18060/api/v1/search?keyword=AI绘画"
```

---

## 🐳 Docker 命令别名

```bash
# 检查容器
alias xhs-ps='sudo docker ps --filter "name=xhs"'

# 查看日志
alias xhs-logs='sudo docker logs xhs-official -f'

# 重启
alias xhs-restart='sudo docker restart xhs-official'

# 登录状态
alias xhs-status='curl -s http://localhost:18060/api/v1/login/status | python3 -m json.tool'
```

---

## 📊 日志分析

### 发布记录分析
```bash
# 统计成功率
python3 -c "
import json
data = json.load(open('/home/ubuntu/xhs-automation/logs/publish_records.json'))
total = len(data)
success = sum(1 for r in data if r.get('success'))
print(f'总发布: {total}, 成功: {success}, 成功率: {success/total*100:.1f}%')
"

# 最近失败记录
python3 -c "
import json
data = json.load(open('/home/ubuntu/xhs-automation/logs/publish_records.json'))
for r in data[-5:]:
    if not r.get('success'):
        print(f\"{r['timestamp'][:16]} | {r.get('error', 'unknown error')[:50]}\")
"
```

### 告警日志
```bash
# 查看最近告警
tail -20 /home/ubuntu/xhs-automation/logs/alerts.log

# 按级别过滤
grep CRITICAL /home/ubuntu/xhs-automation/logs/alerts.log
grep WARNING /home/ubuntu/xhs-automation/logs/alerts.log
```

---

## ⚡ 快速操作模板

### 模板1：检查系统健康
```bash
#!/bin/bash
echo "=== 系统健康检查 ==="
echo -n "服务: "; systemctl is-active xhs-automation
echo -n "容器: "; sudo docker ps --filter name=xhs --format "{{.Status}}"
echo -n "API: "; curl -s -o /dev/null -w "%{http_code}" http://localhost:18060/api/v1/login/status
echo -n "Cookie: "; [ -f /home/ubuntu/xhs-automation/docker/data/cookies.json ] && echo "OK" || echo "MISSING"
```

### 模板2：强制发布
```bash
#!/bin/bash
# 强制立即发布（清空今日记录后）
python3 -c "import json; data=json.load(open('/home/ubuntu/xhs-automation/logs/publish_records.json')); json.dump([r for r in data if r.get('success')], open('/home/ubuntu/xhs-automation/logs/publish_records.json','w'))"
cd /home/ubuntu/xhs-automation && python3 scripts/immediate_publish.py
```

---

## 🔐 敏感信息

### API Keys（已配置在 .env）
- `RUNNINGHUB_CONSUMER_API_KEY`: 消费级 API
- `RUNNINGHUB_ENTERPRISE_API_KEY`: 企业级 API（备用）
- `MINIMAX_API_KEY`: MiniMax 大模型
- `FEISHU_APP_ID`: 飞书应用 ID
- `FEISHU_APP_SECRET`: 飞书应用密钥

### 配置文件位置
- `.env`: `/home/ubuntu/xhs-automation/.env`
- `publish_config.json`: `/home/ubuntu/xhs-automation/config/publish_config.json`
- `monitoring_config.json`: `/home/ubuntu/xhs-automation/config/monitoring_config.json`

---

*最后更新: 2026-02-28*
