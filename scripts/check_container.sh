#!/bin/bash
# 小红书容器健康检查与自动恢复脚本
# 用法: 添加到 crontab: * * * * * /home/ubuntu/xhs-automation/scripts/check_container.sh

CONTAINER_NAME="xhs-official"
API_PORT=18060
LOG_FILE="/home/ubuntu/xhs-automation/logs/container_health.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查容器是否运行
check_container() {
    if ! sudo docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log "❌ 容器未运行，尝试启动..."
        sudo docker start "$CONTAINER_NAME"
        sleep 3
        
        if sudo docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            log "✅ 容器已启动"
        else
            log "❌ 容器启动失败"
            exit 1
        fi
    else
        # 检查容器健康状态
        STATUS=$(sudo docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "none")
        if [ "$STATUS" = "unhealthy" ]; then
            log "⚠️ 容器健康检查失败，重启中..."
            sudo docker restart "$CONTAINER_NAME"
        fi
    fi
}

# 检查 API 是否响应
check_api() {
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${API_PORT}/api/v1/login/status" --connect-timeout 5 || echo "000")
    
    if [ "$HTTP_CODE" = "200" ]; then
        log "✅ API 正常响应"
        return 0
    else
        log "⚠️ API 无响应 (HTTP: $HTTP_CODE)，重启容器..."
        sudo docker restart "$CONTAINER_NAME"
        sleep 5
        return 1
    fi
}

# 主流程
log "========== 开始健康检查 =========="
check_container
check_api
log "========== 健康检查完成 =========="
