#!/bin/bash
# 小红书自动化系统管理脚本

set -e

SERVICE_NAME="xhs-automation.service"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$PROJECT_DIR/venv"

show_help() {
    echo "小红书自动化系统管理脚本"
    echo "使用方法: $0 [命令]"
    echo ""
    echo "命令:"
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
    echo "  backup     - 备份发布记录"
    echo "  update     - 更新代码和重启服务"
    echo "  help       - 显示此帮助信息"
}

check_service() {
    echo "检查服务状态..."
    sudo systemctl status $SERVICE_NAME --no-pager -l | head -30
}

check_docker() {
    echo "检查Docker容器状态..."
    sudo docker ps | grep xhs
    echo ""
    echo "容器日志最后20行:"
    sudo docker logs xhs-official --tail 20 2>/dev/null || echo "容器未运行"
}

case "$1" in
    status)
        check_service
        ;;
    start)
        echo "启动服务..."
        sudo systemctl start $SERVICE_NAME
        sleep 2
        check_service
        ;;
    stop)
        echo "停止服务..."
        sudo systemctl stop $SERVICE_NAME
        sleep 2
        check_service
        ;;
    restart)
        echo "重启服务..."
        sudo systemctl restart $SERVICE_NAME
        sleep 2
        check_service
        ;;
    logs)
        echo "查看服务日志..."
        sudo journalctl -u $SERVICE_NAME -n 50 --no-pager
        ;;
    logs-follow)
        echo "实时查看日志 (Ctrl+C退出)..."
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    enable)
        echo "启用开机启动..."
        sudo systemctl enable $SERVICE_NAME
        echo "已启用开机启动"
        ;;
    disable)
        echo "禁用开机启动..."
        sudo systemctl disable $SERVICE_NAME
        echo "已禁用开机启动"
        ;;
    docker)
        check_docker
        ;;
    test)
        echo "运行单次发布测试..."
        cd $PROJECT_DIR
        source $VENV_PATH/bin/activate
        python scripts/xhs_automation.py oneshot
        ;;
    backup)
        echo "备份发布记录..."
        BACKUP_DIR="$PROJECT_DIR/backup"
        mkdir -p $BACKUP_DIR
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        cp $PROJECT_DIR/logs/publish_records.json $BACKUP_DIR/publish_records_$TIMESTAMP.json 2>/dev/null || echo "无发布记录可备份"
        echo "备份已保存到: $BACKUP_DIR/publish_records_$TIMESTAMP.json"
        ;;
    update)
        echo "更新系统..."
        cd $PROJECT_DIR
        echo "1. 拉取最新代码..."
        # 这里可以添加git pull等更新逻辑
        echo "2. 更新Python依赖..."
        source $VENV_PATH/bin/activate
        pip install -r requirements.txt 2>/dev/null || echo "无requirements.txt文件"
        echo "3. 重启服务..."
        sudo systemctl restart $SERVICE_NAME
        sleep 3
        check_service
        ;;
    help|*)
        show_help
        ;;
esac
