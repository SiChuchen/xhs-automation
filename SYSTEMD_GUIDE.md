# 小红书自动化系统 - Systemd 服务管理指南

## 📦 系统架构

```
系统服务 (systemd)
    ↓
小红书自动化服务 (xhs-automation.service)
    ↓ 通过HTTP API
小红书MCP容器 (xpzouying/xiaohongshu-mcp)
    ↓ 通过浏览器自动化
小红书平台
```

## 🚀 快速管理命令

### 使用管理脚本 (推荐)
```bash
cd /home/ubuntu/xhs-automation

# 查看状态
./manage.sh status

# 查看日志
./manage.sh logs

# 重启服务
./manage.sh restart

# 运行单次测试
./manage.sh test

# 查看Docker状态
./manage.sh docker
```

### 直接使用 systemctl 命令
```bash
# 查看服务状态
sudo systemctl status xhs-automation.service

# 启动服务
sudo systemctl start xhs-automation.service

# 停止服务
sudo systemctl stop xhs-automation.service

# 重启服务
sudo systemctl restart xhs-automation.service

# 查看实时日志
sudo journalctl -u xhs-automation.service -f

# 查看最近50条日志
sudo journalctl -u xhs-automation.service -n 50

# 启用开机启动
sudo systemctl enable xhs-automation.service

# 禁用开机启动
sudo systemctl disable xhs-automation.service
```

### Docker 容器管理
```bash
# 查看容器状态
sudo docker ps | grep xhs

# 查看容器日志
sudo docker logs xhs-official --tail 20

# 实时查看日志
sudo docker logs xhs-official -f

# 重启容器
sudo docker restart xhs-official

# 停止容器
sudo docker stop xhs-official

# 启动容器
sudo docker start xhs-official
```

## 🔧 服务配置文件

### Systemd 服务文件位置
```
/etc/systemd/system/xhs-automation.service
```

### 服务配置详情
```ini
[Unit]
Description=Xiaohongshu Automation Service - 林晓芯人设自动化发布
After=network.target docker.service
Requires=docker.service
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/xhs-automation
Environment="PATH=/home/ubuntu/xhs-automation/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/ubuntu/xhs-automation/venv/bin/python scripts/xhs_automation.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=xhs-automation
Environment="PYTHONUNBUFFERED=1"
Environment="TZ=Asia/Shanghai"

[Install]
WantedBy=multi-user.target
```

## 📊 监控与日志

### 日志文件位置
1. **Systemd 日志** - 通过 journalctl 查看
2. **应用日志** - `/home/ubuntu/xhs-automation/logs/automation.log`
3. **发布记录** - `/home/ubuntu/xhs-automation/logs/publish_records.json`
4. **Docker 日志** - 容器内部日志

### 关键监控指标
```bash
# 检查服务是否运行
sudo systemctl is-active xhs-automation.service

# 检查服务是否启用开机启动
sudo systemctl is-enabled xhs-automation.service

# 检查服务启动时间
sudo systemctl show xhs-automation.service --property=ActiveEnterTimestamp

# 检查内存使用
sudo systemctl status xhs-automation.service | grep Memory
```

## 🛠️ 故障排除

### 常见问题

#### 1. 服务无法启动
```bash
# 检查详细错误
sudo journalctl -u xhs-automation.service -n 100 --no-pager

# 检查Python依赖
cd /home/ubuntu/xhs-automation
source venv/bin/activate
python scripts/test_automation.py
```

#### 2. Docker 容器未运行
```bash
# 检查Docker服务
sudo systemctl status docker

# 启动容器
sudo docker start xhs-official

# 检查容器日志
sudo docker logs xhs-official
```

#### 3. 登录状态失效
```bash
# 检查cookies.json
ls -la /tmp/xhs-official/data/

# 重新登录（在Windows主机上）
# 运行 xiaohongshu-login-windows-amd64.exe
# 上传新的 cookies.json 到 /tmp/xhs-official/data/
```

#### 4. 图片上传失败
```bash
# 检查图片目录
ls -lh /tmp/xhs-official/images/

# 重新处理图片
cd /home/ubuntu/xhs-automation
source venv/bin/activate
python scripts/xhs_image_processor.py
```

## 🔄 维护任务

### 每日检查
```bash
# 1. 检查服务状态
./manage.sh status

# 2. 检查Docker容器
./manage.sh docker

# 3. 检查发布记录
cat logs/publish_records.json | jq '. | length'

# 4. 检查磁盘空间
df -h /home
```

### 每周维护
```bash
# 1. 备份发布记录
./manage.sh backup

# 2. 清理旧日志
sudo journalctl --vacuum-time=7d

# 3. 更新系统
sudo apt update && sudo apt upgrade -y

# 4. 更新Docker镜像
sudo docker pull xpzouying/xiaohongshu-mcp
sudo docker restart xhs-official
```

### 每月维护
```bash
# 1. 检查cookies有效期（约30天）
# 2. 重新扫码登录
# 3. 更新人物设定图片
# 4. 审核内容策略
```

## 📈 性能优化

### 资源限制配置（可选）
```ini
# 在 [Service] 部分添加
MemoryLimit=512M
CPUQuota=50%
```

### 日志轮转配置
创建 `/etc/systemd/journald.conf.d/xhs-automation.conf`:
```ini
[Journal]
MaxRetentionSec=1month
MaxFileSec=1day
SystemMaxUse=1G
```

## 🔐 安全建议

1. **定期更新cookies** - 每30天重新登录
2. **备份重要数据** - 定期备份发布记录和配置
3. **监控异常活动** - 检查日志中的错误和警告
4. **限制访问权限** - 确保只有授权用户可以访问服务
5. **更新依赖** - 定期更新Python包和Docker镜像

## 🚨 紧急恢复

### 服务完全崩溃
```bash
# 1. 停止所有相关服务
sudo systemctl stop xhs-automation.service
sudo docker stop xhs-official

# 2. 清理状态
sudo docker system prune -f

# 3. 重新启动
sudo docker start xhs-official
sudo systemctl start xhs-automation.service

# 4. 验证恢复
./manage.sh status
./manage.sh docker
```

### 数据丢失恢复
```bash
# 从备份恢复发布记录
cp /home/ubuntu/xhs-automation/backup/publish_records_*.json \
   /home/ubuntu/xhs-automation/logs/publish_records.json

# 重启服务
./manage.sh restart
```

## 📞 技术支持

### 获取帮助信息
```bash
# 显示所有可用命令
./manage.sh help

# 查看系统信息
uname -a
python --version
docker --version
```

### 调试信息收集
```bash
# 收集系统状态
./manage.sh status > debug_status.txt
./manage.sh docker >> debug_status.txt
sudo journalctl -u xhs-automation.service -n 100 >> debug_status.txt
sudo docker logs xhs-official --tail 100 >> debug_status.txt
```

---

**系统状态**: ✅ 运行中  
**最后检查**: $(date)  
**下一步**: 监控首次自动化发布（预计在下一个最佳发布时间）