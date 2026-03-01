#!/bin/bash
# 小红书自动化系统监控功能安装脚本

set -e

echo "🔧 小红书自动化系统监控功能安装脚本"
echo "=========================================="

# 检查是否以root运行（部分操作需要）
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  部分操作需要root权限，将使用sudo"
    SUDO="sudo"
else
    SUDO=""
fi

# 项目目录
PROJECT_DIR="/home/ubuntu/xhs-automation"
cd "$PROJECT_DIR"

echo "1. 检查现有配置..."
if [ ! -f "config/monitoring_config.json" ]; then
    echo "   ✅ 监控配置文件已存在"
else
    echo "   ℹ️  监控配置文件不存在，使用默认配置"
fi

echo "2. 测试监控模块..."
source venv/bin/activate
if python test_monitoring.py > /tmp/monitoring_test.log 2>&1; then
    echo "   ✅ 监控模块测试通过"
else
    echo "   ❌ 监控模块测试失败，查看日志: /tmp/monitoring_test.log"
    cat /tmp/monitoring_test.log
    exit 1
fi

echo "3. 安装logrotate配置..."
if [ -f "config/logrotate_xhs.conf" ]; then
    $SUDO cp config/logrotate_xhs.conf /etc/logrotate.d/xhs-automation
    $SUDO chmod 644 /etc/logrotate.d/xhs-automation
    echo "   ✅ logrotate配置已安装"
    
    # 测试logrotate配置
    if $SUDO logrotate -d /etc/logrotate.d/xhs-automation > /dev/null 2>&1; then
        echo "   ✅ logrotate配置语法正确"
    else
        echo "   ⚠️  logrotate配置可能有语法问题，请检查"
    fi
else
    echo "   ❌ logrotate配置文件不存在"
fi

echo "4. 配置cron定时任务..."
CRON_JOB="0 3 * * * cd $PROJECT_DIR && source venv/bin/activate && python scripts/storage_cleanup.py --full"
if crontab -l 2>/dev/null | grep -q "storage_cleanup.py"; then
    echo "   ✅ 存储清理cron任务已存在"
else
    (crontab -l 2>/dev/null; echo "# 小红书自动化系统存储清理"; echo "$CRON_JOB") | crontab -
    echo "   ✅ 存储清理cron任务已添加 (每天03:00运行)"
fi

echo "5. 更新systemd服务（监控增强版）..."
if [ -f "xhs-automation-monitored.service" ]; then
    echo "   检测到监控增强版服务文件"
    
    # 停止当前服务
    $SUDO systemctl stop xhs-automation.service 2>/dev/null || true
    
    # 备份原服务文件
    if [ -f "/etc/systemd/system/xhs-automation.service" ]; then
        $SUDO cp /etc/systemd/system/xhs-automation.service /etc/systemd/system/xhs-automation.service.backup
        echo "   ✅ 原服务文件已备份"
    fi
    
    # 安装新服务文件
    $SUDO cp xhs-automation-monitored.service /etc/systemd/system/xhs-automation.service
    $SUDO systemctl daemon-reload
    
    echo "   ✅ 监控增强版服务文件已安装"
    
    # 启动服务
    $SUDO systemctl start xhs-automation.service
    sleep 2
    
    if $SUDO systemctl is-active xhs-automation.service > /dev/null; then
        echo "   ✅ 服务启动成功"
        
        # 显示状态
        echo "   服务状态:"
        $SUDO systemctl status xhs-automation.service --no-pager | head -20
    else
        echo "   ❌ 服务启动失败，查看日志: sudo journalctl -u xhs-automation.service -n 30"
    fi
else
    echo "   ⚠️  监控增强版服务文件不存在，保持原服务"
    $SUDO systemctl restart xhs-automation.service
fi

echo "6. 配置Webhook（可选）..."
echo "   如需配置飞书/钉钉Webhook，请编辑: config/monitoring_config.json"
echo "   设置 webhooks.enabled=true 并填写相应配置"

echo "7. 创建管理脚本..."
if [ -f "manage.sh" ]; then
    chmod +x manage.sh
    echo "   ✅ 管理脚本已就绪"
    
    # 创建快捷方式
    if [ ! -f "/usr/local/bin/xhs-manage" ]; then
        $SUDO ln -sf "$PROJECT_DIR/manage.sh" /usr/local/bin/xhs-manage 2>/dev/null || true
        echo "   ✅ 创建快捷方式: xhs-manage"
    fi
fi

echo ""
echo "🎉 监控功能安装完成！"
echo ""
echo "📋 下一步操作:"
echo "   1. 配置Webhook（可选）:"
echo "      nano config/monitoring_config.json"
echo "   2. 验证监控系统:"
echo "      ./manage.sh status"
echo "      ./manage.sh docker"
echo "   3. 测试告警:"
echo "      python scripts/monitoring.py --test-webhook"
echo "   4. 查看监控日志:"
echo "      tail -f logs/alerts.log"
echo ""
echo "📊 监控功能已启用:"
echo "   • Webhook告警（需配置）"
echo "   • Cookie有效期监控（剩余30天告警）"
echo "   • 系统状态监控（服务、Docker、磁盘、内存、CPU）"
echo "   • 存储自动清理（日志保留30天，图片保留7天）"
echo "   • 定时健康检查（每小时一次）"
echo ""
echo "🔧 管理命令:"
echo "   ./manage.sh status      # 查看状态"
echo "   ./manage.sh logs        # 查看日志"
echo "   ./manage.sh restart     # 重启服务"
echo "   xhs-manage status       # 使用快捷方式"
echo ""
echo "⚠️  重要提醒:"
echo "   • Cookie将在30天后过期，系统会在过期前3天发送告警"
echo "   • 确保定期检查告警日志: logs/alerts.log"
echo "   • 如需紧急干预，系统会通过Webhook通知（如已配置）"