#!/bin/bash
# 小红书自动化系统管理脚本（监控增强版）

set -e

SERVICE_NAME="xhs-automation.service"
PROJECT_DIR="/home/ubuntu/xhs-automation"
VENV_PATH="$PROJECT_DIR/venv"
CONFIG_DIR="$PROJECT_DIR/config"

show_help() {
    echo "小红书自动化系统管理脚本（监控增强版）"
    echo "使用方法: $0 [命令]"
    echo ""
    echo "基础命令:"
    echo "  status     - 查看服务状态"
    echo "  start      - 启动服务"
    echo "  stop       - 停止服务"
    echo "  restart    - 重启服务"
    echo "  logs       - 查看服务日志"
    echo "  logs-follow - 实时查看日志"
    echo "  enable     - 启用开机启动"
    echo "  disable    - 禁用开机启动"
    echo "  docker     - 查看Docker容器状态"
    echo "  test       - 运行单次发布测试"
    echo ""
    echo "监控命令:"
    echo "  monitor-status  - 查看监控状态"
    echo "  monitor-test    - 测试监控系统"
    echo "  cookie-check    - 检查Cookie状态"
    echo "  system-check    - 检查系统状态"
    echo "  storage-check   - 检查存储状态"
    echo "  storage-cleanup - 运行存储清理"
    echo "  webhook-test    - 测试Webhook"
    echo ""
    echo "维护命令:"
    echo "  backup     - 备份发布记录和配置"
    echo "  update     - 更新代码和重启服务"
    echo "  install-monitoring - 安装监控功能"
    echo "  help       - 显示此帮助信息"
}

check_service() {
    echo "🔍 检查服务状态..."
    sudo systemctl status $SERVICE_NAME --no-pager -l | head -30
}

check_docker() {
    echo "🐳 检查Docker容器状态..."
    sudo docker ps | grep -E "xhs|xiaohongshu"
    echo ""
    echo "📊 容器日志最后20行:"
    sudo docker logs xhs-official --tail 20 2>/dev/null || echo "容器未运行"
}

run_monitoring() {
    cd $PROJECT_DIR
    source $VENV_PATH/bin/activate
    python scripts/monitoring.py "$@"
}

run_storage_cleanup() {
    cd $PROJECT_DIR
    source $VENV_PATH/bin/activate
    python scripts/storage_cleanup.py "$@"
}

case "$1" in
    # 基础命令
    status)
        check_service
        ;;
    start)
        echo "🚀 启动服务..."
        sudo systemctl start $SERVICE_NAME
        sleep 2
        check_service
        ;;
    stop)
        echo "🛑 停止服务..."
        sudo systemctl stop $SERVICE_NAME
        sleep 2
        check_service
        ;;
    restart)
        echo "🔄 重启服务..."
        sudo systemctl restart $SERVICE_NAME
        sleep 2
        check_service
        ;;
    logs)
        echo "📋 查看服务日志..."
        sudo journalctl -u $SERVICE_NAME -n 50 --no-pager
        ;;
    logs-follow)
        echo "📊 实时查看日志 (Ctrl+C退出)..."
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    enable)
        echo "✅ 启用开机启动..."
        sudo systemctl enable $SERVICE_NAME
        echo "已启用开机启动"
        ;;
    disable)
        echo "⛔ 禁用开机启动..."
        sudo systemctl disable $SERVICE_NAME
        echo "已禁用开机启动"
        ;;
    docker)
        check_docker
        ;;
    test)
        echo "🧪 运行单次发布测试..."
        cd $PROJECT_DIR
        source $VENV_PATH/bin/activate
        python scripts/xhs_automation_monitored.py oneshot
        ;;
    
    # 监控命令
    monitor-status)
        echo "📊 查看监控状态..."
        run_monitoring --full-check
        ;;
    monitor-test)
        echo "🧪 测试监控系统..."
        cd $PROJECT_DIR
        source $VENV_PATH/bin/activate
        python test_monitoring.py
        ;;
    cookie-check)
        echo "🍪 检查Cookie状态..."
        run_monitoring --check-cookie
        ;;
    system-check)
        echo "💻 检查系统状态..."
        run_monitoring --check-system
        ;;
    storage-check)
        echo "💾 检查存储状态..."
        run_storage_cleanup --check-disk
        ;;
    storage-cleanup)
        echo "🧹 运行存储清理..."
        run_storage_cleanup --full
        ;;
    webhook-test)
        echo "🔔 测试Webhook..."
        run_monitoring --test-webhook
        ;;
    
    # 维护命令
    backup)
        echo "💾 备份发布记录和配置..."
        BACKUP_DIR="$PROJECT_DIR/backup"
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_PATH="$BACKUP_DIR/backup_$TIMESTAMP"
        
        mkdir -p $BACKUP_PATH
        
        # 备份重要文件
        cp -r $PROJECT_DIR/logs $BACKUP_PATH/ 2>/dev/null || true
        cp -r $PROJECT_DIR/config $BACKUP_PATH/ 2>/dev/null || true
        cp $PROJECT_DIR/*.sh $BACKUP_PATH/ 2>/dev/null || true
        cp $PROJECT_DIR/*.py $BACKUP_PATH/ 2>/dev/null || true
        cp $PROJECT_DIR/*.md $BACKUP_PATH/ 2>/dev/null || true
        cp $PROJECT_DIR/requirements.txt $BACKUP_PATH/ 2>/dev/null || true
        
        # 备份Docker相关
        sudo docker inspect xhs-official > $BACKUP_PATH/docker_inspect.json 2>/dev/null || true
        
        echo "✅ 备份已完成: $BACKUP_PATH"
        echo "   包含: 日志、配置、脚本、Docker信息"
        
        # 创建压缩包
        cd $BACKUP_DIR
        tar -czf backup_$TIMESTAMP.tar.gz backup_$TIMESTAMP
        rm -rf backup_$TIMESTAMP
        echo "📦 压缩包: $BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
        ;;
    
    update)
        echo "🔄 更新系统..."
        cd $PROJECT_DIR
        echo "1. 更新Python依赖..."
        source $VENV_PATH/bin/activate
        pip install -r requirements.txt --upgrade 2>/dev/null || echo "无requirements.txt文件"
        
        echo "2. 重启服务..."
        sudo systemctl restart $SERVICE_NAME
        sleep 3
        
        echo "3. 验证更新..."
        check_service
        ;;
    
    install-monitoring)
        echo "🔧 安装监控功能..."
        chmod +x $PROJECT_DIR/setup_monitoring.sh
        $PROJECT_DIR/setup_monitoring.sh
        ;;
    
    help|*)
        show_help
        ;;
esac