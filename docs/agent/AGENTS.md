# AGENTS.md - 林晓芯的小红书运营系统完全指南

> ⚠️ **当前状态**: 由于资源限制，部分Agent已暂时停用。系统保持独立运作。

## 🤖 Agent 团队通讯录

### ✅ 活跃成员

| ID | 名称 | 角色 | 工作空间 | 技能 | 飞书账号 |
|----|------|------|----------|------|----------|
| main | 01 (Zero-One) | 主助手 | workspace-main | 综合协调 | default |
| xhs_operator | 林晓芯 | 小红书运营 | workspace-xhs_operator | xiaohongshu-mcp | xhs_operator |
| system_architect | 金驭 | 系统架构师 | workspace-system_architect | github, docker-essentials | system_architect |

### ⏸️ 暂时停用成员

| ID | 名称 | 角色 |
|----|------|------|
| frontend_dev | 薰子 | 前端研发 |
| backend_dev | 贝尔摩德 | 后端研发 |
| cpp_dev | 薇尔莉特 | 底层研发 |
| dba | 雪乃 | 数据库工程师 |
| devops | 露娜 | 运维工程师 |
| qa | 团子 | 测试工程师 |
| security | 麦晓雯 | 安全工程师 |
| product_manager | 蛊 | 产品经理 |
| tech_writer | 蝶 | 文档编写 |
| project_manager | 克莱尔 | 项目经理 |

---

## 📱 小红书自动化运营系统

### 项目目录
`/home/ubuntu/xhs-automation`

### 🎯 系统能力

| 功能 | 说明 | 状态 |
|------|------|------|
| **定时自动发布** | 每天 09:00/12:00/18:00/21:00 自动发布 | ✅ |
| **AI 内容生成** | 使用 MiniMax 生成文案 (500-1000字) | ✅ |
| **AI 图片生成** | 使用 RunningHub 生成配图 | ✅ |
| **飞书告警** | 发布结果推送到飞书群 | ✅ |
| **容器健康检查** | 崩溃自动重启 | ✅ |
| **系统监控** | Cookie/磁盘/内存监控 | ✅ |

---

## 🚀 立即发帖命令

### 方式一：即时发布（立即发布，不等待定时）

```bash
cd /home/ubuntu/xhs-automation && python3 scripts/immediate_publish.py
```

### 方式二：手动触发自动化服务

```bash
# 重启自动化服务
sudo systemctl restart xhs-automation

# 强制立即执行一次发布检查
# 服务每60分钟检查一次，在最佳时间(09:00/12:00/18:00/21:00)会自动发布
```

### 方式三：查看发布记录

```bash
# 查看所有发布记录
cat /home/ubuntu/xhs-automation/logs/publish_records.json | python3 -m json.tool

# 查看今日发布
python3 -c "
import json
from datetime import datetime
data = json.load(open('/home/ubuntu/xhs-automation/logs/publish_records.json'))
today = str(datetime.now().date())
for r in data:
    if r['timestamp'][:10] == today:
        print(f\"{r['timestamp'][:16]} | {r['title'][:30]} | 成功: {r['success']}\")
"
```

---

## 🔧 日常运维命令

### 服务管理
```bash
# 查看服务状态
systemctl status xhs-automation

# 启动服务
sudo systemctl start xhs-automation

# 停止服务
sudo systemctl stop xhs-automation

# 重启服务
sudo systemctl restart xhs-automation
```

### 容器管理
```bash
# 检查容器状态
sudo docker ps --filter "name=xhs"

# 检查登录状态 (推荐使用 main.py)
python3 /home/ubuntu/xhs-automation/main.py status

# 或使用 curl
curl -s http://localhost:18060/api/v1/login/status | python3 -m json.tool

# 重启容器
sudo docker restart xhs-official

# 查看容器日志
sudo docker logs xhs-official --tail 100

# 容器自动重启已启用（--restart=always）
```

### 监控检查
```bash
# 运行系统检查
cd /home/ubuntu/xhs-automation && python3 scripts/monitoring.py --full-check

# 检查 Cookie 状态
cd /home/ubuntu/xhs-automation && python3 scripts/monitoring.py --check-cookie

# 测试飞书告警
cd /home/ubuntu/xhs-automation && python3 scripts/monitoring.py --test-webhook

# 查看实时日志
journalctl -u xhs-automation.service -f

# 查看告警日志
tail -50 /home/ubuntu/xhs-automation/logs/alerts.log
```

---

## 📊 查看系统状态

### 当前状态
```bash
# 检查所有状态
cd /home/ubuntu/xhs-automation && python3 -c "
import json
import os
from datetime import datetime

# 服务状态
print('=== 服务状态 ===')
os.system('systemctl is-active xhs-automation')

# Docker
print('\n=== Docker 容器 ===')
os.system('sudo docker ps --filter name=xhs --format \"{{.Names}}: {{.Status}}\"')

# Cookie
print('\n=== Cookie 状态 ===')
cookie_path = '/home/ubuntu/xhs-automation/docker/data/cookies.json'
if os.path.exists(cookie_path):
    age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cookie_path))).days
    print(f'有效，{30-age}天前更新，剩余{30-age}天')
else:
    print('Cookie文件不存在!')

# 发布记录
print('\n=== 今日发布 ===')
try:
    data = json.load(open('/home/ubuntu/xhs-automation/logs/publish_records.json'))
    today = str(datetime.now().date())
    today_posts = [r for r in data if r['timestamp'][:10] == today]
    success = sum(1 for r in today_posts if r.get('success'))
    print(f'今日发布: {len(today_posts)} 次, 成功: {success} 次')
except:
    print('无记录')
"
```

---

## ⚠️ 故障排查

### 发布失败常见原因

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `HTTP timeout` | 容器无响应 | `sudo docker restart xhs-official` |
| `Cookie expired` | 登录过期 | 需要重新扫码登录 |
| `Login failed` | 未登录 | 检查容器日志，手动登录 |
| `No image` | 图片生成失败 | 检查 RunningHub API |

### 紧急恢复
```bash
# 1. 重启容器
sudo docker restart xhs-official
sleep 5

# 2. 检查登录 (推荐)
python3 /home/ubuntu/xhs-automation/main.py status

# 3. 重启自动化服务
sudo systemctl restart xhs-automation

# 4. 查看日志
journalctl -u xhs-automation.service --since "1 minute ago" --no-pager
```

---

## 🎭 内容配置

### 人物设定
- **名称**: 林晓芯
- **昵称**: 杨枝甘露椰果红豆
- **性格**: 理工科女大、效率控、技术宅

### 内容模块（自动选择）
1. **academic_efficiency** (40%) - 编程技巧、工具推荐
2. **visual_creation** (30%) - AI绘画、游戏同人
3. **geek_daily** (20%) - 代码调试、极客装备
4. **hot_topics** (10%) - 行业趋势、技术热点

### 发布规则
- 每天最多发布 **2 次**
- 发布时间: **09:00 / 12:00 / 18:00 / 21:00**
- 发布间隔: 至少 **4 小时**
- 只统计**成功**发布计入每日限额

---

## 🔐 API 配置

### 环境变量（已配置）
```
# API Keys 请在 .env 文件中配置，请勿提交到版本控制
RUNNINGHUB_CONSUMER_API_KEY=your_key_here
RUNNINGHUB_ENTERPRISE_API_KEY=your_key_here
MINIMAX_API_KEY=your_key_here
FEISHU_APP_ID=your_app_id_here
```

> ⚠️ **敏感信息请配置在 `.env` 文件中，不要提交到版本控制**

### 飞书告警群
- 群名: `agents沟通`
- Chat ID: `oc_1deeea55261fa4a05457db70e6d5b879`

---

## 📁 关键路径

| 用途 | 路径 |
|------|------|
| 项目根目录 | `/home/ubuntu/xhs-automation` |
| Cookie 文件 | `/home/ubuntu/xhs-automation/docker/data/cookies.json` |
| 图片目录 | `/home/ubuntu/xhs-automation/images/` |
| RunningHub 图片 | `/home/ubuntu/xhs-automation/images/runninghub_generated/` |
| 发布记录 | `/home/ubuntu/xhs-automation/logs/publish_records.json` |
| 告警日志 | `/home/ubuntu/xhs-automation/logs/alerts.log` |
| 配置文件 | `/home/ubuntu/xhs-automation/config/publish_config.json` |

---

## 💬 典型对话示例

### 用户：帮我发一篇关于 Python 异步编程的笔记
```
我理解，你需要发布一篇关于 Python 异步编程的小红书笔记。

✅ 系统已就绪:
- 容器状态: 运行中
- Cookie: 有效
- 今日发布: 0/2 次

我现在执行即时发布命令...
```

### 用户：查看今天的发布情况
```
📊 今日发布统计 (2026-02-28):
- 发布次数: 1
- 成功次数: 1
- 最新笔记: "Python异步核心就三个关键字"

状态: 正常，今天还可以发布 1 篇
```

### 用户：系统好像出问题了
```
🔍 检查系统状态...

容器状态: ❌ 已停止
登录状态: ❌ 无法连接

正在尝试恢复...
- 重启容器: ✅
- 检查登录: ⏳

(如果需要手动登录，我会提示你)
```

---

*最后更新: 2026-02-28*
