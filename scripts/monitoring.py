#!/usr/bin/env python3
"""
小红书自动化系统监控模块
实现Webhook告警、Cookie监控、存储管理等功能
"""

import os
import sys
import json
import time
import logging
import subprocess
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MonitoringSystem:
    """监控系统主类"""
    
    def __init__(self, config_path: str = None):
        """初始化监控系统"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config',
                'monitoring_config.json'
            )
        
        self.config_path = config_path
        self.config = self._load_config()
        self.last_check_time = {}
        
        logger.info(f"监控系统初始化完成，配置文件: {config_path}")
    
    def _load_config(self) -> Dict:
        """加载监控配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"配置文件不存在: {self.config_path}，使用默认配置")
            return self._get_default_config()
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "webhooks": {"enabled": False},
            "cookie_monitoring": {"enabled": True},
            "storage_management": {"enabled": True},
            "system_monitoring": {"enabled": True}
        }
    
    def send_alert(self, title: str, message: str, level: str = "info") -> bool:
        """
        发送告警消息
        
        Args:
            title: 告警标题
            message: 告警消息
            level: 告警级别 (critical/warning/info)
            
        Returns:
            bool: 是否发送成功
        """
        logger.info(f"[{level.upper()}] {title}: {message}")
        
        # 发送到Webhook
        webhook_success = self._send_webhook(title, message, level)
        
        # 发送到飞书当前对话（如果有配置）
        feishu_success = self._send_feishu_direct(title, message, level)
        
        # 记录到本地日志文件
        self._log_alert(title, message, level)
        
        # 返回成功（只要任一渠道成功）
        return webhook_success or feishu_success
    
    def _send_feishu_direct(self, title: str, message: str, level: str) -> bool:
        """直接发送飞书消息到监控群"""
        try:
            import requests
            import json
            
            # 获取应用凭证
            app_id = os.environ.get('FEISHU_APP_ID', '')
            app_secret = os.environ.get('FEISHU_APP_SECRET', '')
            
            if not app_id or not app_secret:
                return False
            
            # 尝试读取保存的群ID
            chat_id_file = '/tmp/xhs_alert_chat_id'
            chat_id = None
            
            # 优先使用环境变量指定的群ID
            env_chat_id = os.environ.get('FEISHU_CHAT_ID', '')
            if env_chat_id:
                chat_id = env_chat_id
                logger.info(f"使用环境变量指定的飞书群ID: {chat_id}")
            elif os.path.exists(chat_id_file):
                with open(chat_id_file, 'r') as f:
                    chat_id = f.read().strip()
            else:
                # 默认使用 xhs_operator 机器人所在的群
                chat_id = 'oc_1deeea55261fa4a05457db70e6d5b879'
                logger.info(f"使用默认飞书群ID: {chat_id}")
            
            # 获取 access_token
            token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            token_resp = requests.post(token_url, json={
                "app_id": app_id,
                "app_secret": app_secret
            }, timeout=10)
            token_data = token_resp.json()
            
            if token_data.get("code") != 0:
                logger.warning(f"获取飞书token失败: {token_data.get('msg')}")
                return False
            
            access_token = token_data.get("tenant_access_token")
            
            # 如果没有保存的群ID，创建一个
            if not chat_id:
                create_chat_url = "https://open.feishu.cn/open-apis/im/v1/chats"
                user_id = os.environ.get('FEISHU_USER_ID', '')
                if user_id:
                    chat_resp = requests.post(create_chat_url, headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    }, json={
                        "name": "小红书监控告警",
                        "user_id_list": [user_id]
                    }, timeout=10)
                    chat_data = chat_resp.json()
                    if chat_data.get("code") == 0:
                        chat_id = chat_data["data"]["chat_id"]
                        # 保存群ID
                        with open(chat_id_file, 'w') as f:
                            f.write(chat_id)
            
            if not chat_id:
                return False
            
            # 发送消息到群
            msg_url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
            
            # 根据告警级别添加emoji
            emoji_map = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
            emoji = emoji_map.get(level, "📌")
            
            content = f"{emoji} **{title}**\n\n{message}"
            
            payload = {
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": content})
            }
            
            resp = requests.post(msg_url, headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=utf-8"
            }, json=payload, timeout=10)
            
            result = resp.json()
            if result.get("code") == 0:
                logger.info(f"飞书消息发送成功: {title}")
                return True
            else:
                logger.warning(f"飞书消息发送失败: {result.get('msg')}")
                return False
                
        except Exception as e:
            logger.debug(f"飞书直接消息发送跳过: {e}")
            return False
    
    def _send_webhook(self, title: str, message: str, level: str) -> bool:
        """发送Webhook告警"""
        webhook_config = self.config.get('webhooks', {})
        if not webhook_config.get('enabled', False):
            return False
        
        providers = webhook_config.get('providers', {})
        success = False
        
        for provider_name, provider_config in providers.items():
            if not provider_config.get('enabled', False):
                continue
            
            try:
                if provider_name == 'feishu':
                    success = self._send_feishu_webhook(title, message, level, provider_config) or success
                elif provider_name == 'dingtalk':
                    success = self._send_dingtalk_webhook(title, message, level, provider_config) or success
                elif provider_name == 'custom':
                    success = self._send_custom_webhook(title, message, level, provider_config) or success
                
            except Exception as e:
                logger.error(f"发送{provider_name} Webhook失败: {e}")
        
        return success
    
    def _send_feishu_webhook(self, title: str, message: str, level: str, config: Dict) -> bool:
        """发送飞书Webhook"""
        webhook_url = config.get('webhook_url', '')
        if not webhook_url:
            logger.warning("飞书Webhook URL未配置")
            return False
        
        # 构建消息
        color_map = {
            'critical': 'red',
            'warning': 'orange',
            'info': 'green'
        }
        color = color_map.get(level, 'gray')
        
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"[{level.upper()}] {title}"
                    },
                    "template": color
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "plain_text",
                            "content": message
                        }
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            }
                        ]
                    }
                ]
            }
        }
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"飞书Webhook发送成功")
            return True
        except Exception as e:
            logger.error(f"飞书Webhook发送失败: {e}")
            return False
    
    def _send_dingtalk_webhook(self, title: str, message: str, level: str, config: Dict) -> bool:
        """发送钉钉Webhook"""
        webhook_url = config.get('webhook_url', '')
        if not webhook_url:
            logger.warning("钉钉Webhook URL未配置")
            return False
        
        # 添加签名 (如果有secret)
        secret = config.get('secret', '')
        if secret:
            import hmac
            import hashlib
            import base64
            import urllib.parse
            
            timestamp = str(round(time.time() * 1000))
            sign_string = f"{timestamp}\n{secret}"
            hmac_code = hmac.new(secret.encode('utf-8'), sign_string.encode('utf-8'), digestmod=hashlib.sha256).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"
        
        # 构建消息
        payload = {
            "msgtype": "text",
            "text": {
                "content": f"[{level.upper()}] {title}\n{message}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }
        
        # 如果需要@所有人
        if config.get('at_all', False):
            payload["at"] = {"isAtAll": True}
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"钉钉Webhook发送成功")
            return True
        except Exception as e:
            logger.error(f"钉钉Webhook发送失败: {e}")
            return False
    
    def _send_custom_webhook(self, title: str, message: str, level: str, config: Dict) -> bool:
        """发送自定义Webhook"""
        webhook_url = config.get('webhook_url', '')
        if not webhook_url:
            logger.warning("自定义Webhook URL未配置")
            return False
        
        method = config.get('method', 'POST').upper()
        headers = config.get('headers', {})
        template = config.get('payload_template', '{"text": "{{message}}"}')
        
        # 替换模板变量
        formatted_message = template\
            .replace('{{title}}', title)\
            .replace('{{message}}', message)\
            .replace('{{level}}', level)\
            .replace('{{timestamp}}', datetime.now().isoformat())
        
        try:
            payload = json.loads(formatted_message)
        except json.JSONDecodeError:
            logger.error(f"自定义Webhook模板JSON解析失败: {formatted_message}")
            return False
        
        try:
            if method == 'POST':
                response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(webhook_url, json=payload, headers=headers, timeout=10)
            else:
                response = requests.get(webhook_url, params=payload, headers=headers, timeout=10)
            
            response.raise_for_status()
            logger.info(f"自定义Webhook发送成功")
            return True
        except Exception as e:
            logger.error(f"自定义Webhook发送失败: {e}")
            return False
    
    def _log_alert(self, title: str, message: str, level: str):
        """记录告警到本地日志文件"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        alert_log_path = os.path.join(log_dir, 'alerts.log')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_entry = f"[{timestamp}] [{level.upper()}] {title}: {message}\n"
        
        try:
            with open(alert_log_path, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"写入告警日志失败: {e}")
    
    def check_cookie_status(self) -> Dict:
        """检查Cookie状态"""
        cookie_config = self.config.get('cookie_monitoring', {})
        if not cookie_config.get('enabled', True):
            return {"status": "disabled"}
        
        cookie_path = cookie_config.get('cookie_path', '/tmp/xhs-official/data/cookies.json')
        warning_days = cookie_config.get('warning_days', 3)
        
        result = {
            "exists": False,
            "status": "unknown",
            "days_remaining": None,
            "expiry_date": None,
            "message": ""
        }
        
        try:
            # 检查文件是否存在
            if not os.path.exists(cookie_path):
                result["message"] = f"Cookie文件不存在: {cookie_path}"
                result["status"] = "missing"
                return result
            
            result["exists"] = True
            file_stat = os.stat(cookie_path)
            modify_time = datetime.fromtimestamp(file_stat.st_mtime)
            file_age_days = (datetime.now() - modify_time).days
            
            # 小红书Cookie有效期通常为30天
            cookie_lifetime_days = 30
            days_remaining = cookie_lifetime_days - file_age_days
            
            result["days_remaining"] = days_remaining
            expiry_date = modify_time + timedelta(days=cookie_lifetime_days)
            result["expiry_date"] = expiry_date.isoformat()
            
            if days_remaining <= 0:
                result["status"] = "expired"
                result["message"] = f"Cookie已过期 ({file_age_days}天前更新)"
                self.send_alert(
                    "Cookie已过期",
                    f"小红书Cookie已过期，需要重新扫码登录。文件: {cookie_path}",
                    "critical"
                )
            elif days_remaining <= warning_days:
                result["status"] = "expiring"
                result["message"] = f"Cookie将在{days_remaining}天后过期 ({file_age_days}天前更新)"
                self.send_alert(
                    "Cookie即将过期",
                    f"小红书Cookie将在{days_remaining}天后过期，建议提前重新登录。过期时间: {expiry_date.strftime('%Y-%m-%d')}",
                    "warning"
                )
            else:
                result["status"] = "valid"
                result["message"] = f"Cookie有效，剩余{days_remaining}天 ({file_age_days}天前更新)"
            
            return result
            
        except Exception as e:
            error_msg = f"检查Cookie状态失败: {e}"
            logger.error(error_msg)
            result["message"] = error_msg
            result["status"] = "error"
            return result
    
    def manage_storage(self) -> Dict:
        """管理存储空间"""
        storage_config = self.config.get('storage_management', {})
        if not storage_config.get('enabled', True):
            return {"status": "disabled"}
        
        result = {
            "log_cleanup": {"deleted": 0, "size_freed": 0},
            "image_cleanup": {"deleted": 0, "size_freed": 0},
            "total_freed": 0
        }
        
        try:
            # 清理旧日志
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
            retention_days = storage_config.get('log_retention_days', 30)
            deleted_logs = self._cleanup_old_files(log_dir, retention_days, ['.log', '.json'])
            result["log_cleanup"]["deleted"] = deleted_logs["count"]
            result["log_cleanup"]["size_freed"] = deleted_logs["size_freed"]
            
            # 清理旧图片 - 容器目录
            image_dir = '/tmp/xhs-official/images'
            image_retention_days = storage_config.get('image_retention_days', 7)
            deleted_images = self._cleanup_old_files(image_dir, image_retention_days, ['.jpg', '.jpeg', '.png'])
            result["image_cleanup"]["deleted"] = deleted_images["count"]
            result["image_cleanup"]["size_freed"] = deleted_images["size_freed"]
            
            # 清理 RunningHub 生成的图片
            runninghub_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'images/runninghub_generated')
            if os.path.exists(runninghub_dir):
                deleted_rh = self._cleanup_old_files(runninghub_dir, image_retention_days, ['.jpg', '.jpeg', '.png'])
                result["image_cleanup"]["deleted"] += deleted_rh["count"]
                result["image_cleanup"]["size_freed"] += deleted_rh["size_freed"]
            
            result["total_freed"] = deleted_logs["size_freed"] + deleted_images["size_freed"]
            
            # 检查目录大小
            log_size_mb = self._get_dir_size_mb(log_dir)
            image_size_mb = self._get_dir_size_mb(image_dir)
            runninghub_size_mb = self._get_dir_size_mb(runninghub_dir) if os.path.exists(runninghub_dir) else 0
            total_image_size_mb = image_size_mb + runninghub_size_mb
            
            max_log_size = storage_config.get('max_log_size_mb', 100)
            max_image_size = storage_config.get('max_image_dir_size_mb', 1024)
            
            if log_size_mb > max_log_size:
                warning_msg = f"日志目录大小({log_size_mb:.1f}MB)超过限制({max_log_size}MB)"
                self.send_alert("日志目录过大", warning_msg, "warning")
            
            if total_image_size_mb > max_image_size:
                warning_msg = f"图片目录过大: 容器({image_size_mb:.1f}MB) + RunningHub({runninghub_size_mb:.1f}MB) = {total_image_size_mb:.1f}MB > {max_image_size}MB"
                self.send_alert("图片目录过大", warning_msg, "warning")
            
            # 发送清理完成通知
            if result["total_freed"] > 0:
                self.send_alert(
                    "存储清理完成",
                    f"清理日志: {result['log_cleanup']['deleted']}个文件，释放{result['log_cleanup']['size_freed']}字节\n"
                    f"清理图片: {result['image_cleanup']['deleted']}个文件，释放{result['image_cleanup']['size_freed']}字节",
                    "info"
                )
            
            return result
            
        except Exception as e:
            error_msg = f"存储管理失败: {e}"
            logger.error(error_msg)
            self.send_alert("存储管理失败", error_msg, "critical")
            return {"status": "error", "message": error_msg}
    
    def _cleanup_old_files(self, directory: str, retention_days: int, extensions: List[str]) -> Dict:
        """清理指定目录中超过保留天数的文件"""
        if not os.path.exists(directory):
            return {"count": 0, "size_freed": 0}
        
        cutoff_time = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0
        freed_size = 0
        
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            
            # 检查扩展名
            if extensions and not any(filename.lower().endswith(ext) for ext in extensions):
                continue
            
            # 检查文件时间
            try:
                file_stat = os.stat(file_path)
                modify_time = datetime.fromtimestamp(file_stat.st_mtime)
                
                if modify_time < cutoff_time:
                    file_size = file_stat.st_size
                    os.remove(file_path)
                    deleted_count += 1
                    freed_size += file_size
                    logger.info(f"删除旧文件: {filename} (修改时间: {modify_time})")
            except Exception as e:
                logger.error(f"删除文件失败 {filename}: {e}")
        
        return {"count": deleted_count, "size_freed": freed_size}
    
    def _get_dir_size_mb(self, directory: str) -> float:
        """获取目录大小（MB）"""
        if not os.path.exists(directory):
            return 0
        
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except Exception:
                    pass
        
        return total_size / (1024 * 1024)
    
    def check_system_status(self) -> Dict:
        """检查系统状态"""
        system_config = self.config.get('system_monitoring', {})
        if not system_config.get('enabled', True):
            return {"status": "disabled"}
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "checks": {}
        }
        
        monitor_items = system_config.get('monitor_items', [])
        
        if 'service_status' in monitor_items:
            result["checks"]["service_status"] = self._check_service_status()
        
        if 'docker_container' in monitor_items:
            result["checks"]["docker_container"] = self._check_docker_container()
        
        if 'disk_usage' in monitor_items:
            result["checks"]["disk_usage"] = self._check_disk_usage()
        
        if 'memory_usage' in monitor_items:
            result["checks"]["memory_usage"] = self._check_memory_usage()
        
        if 'cpu_usage' in monitor_items:
            result["checks"]["cpu_usage"] = self._check_cpu_usage()
        
        # 发送关键告警
        self._process_system_alerts(result)
        
        return result
    
    def _check_service_status(self) -> Dict:
        """检查systemd服务状态"""
        try:
            # 检查xhs-automation服务
            output = subprocess.run(
                ['systemctl', 'is-active', 'xhs-automation.service'],
                capture_output=True,
                text=True,
                timeout=10
            )
            is_active = output.stdout.strip() == 'active'
            
            # 获取服务状态详情
            status_output = subprocess.run(
                ['systemctl', 'status', 'xhs-automation.service', '--no-pager'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return {
                "active": is_active,
                "status": output.stdout.strip(),
                "details": status_output.stdout[:500]  # 截取前500字符
            }
        except Exception as e:
            return {"active": False, "error": str(e)}
    
    def _check_docker_container(self) -> Dict:
        """检查Docker容器状态"""
        try:
            # 检查xhs-official容器
            ps_output = subprocess.run(
                ['sudo', 'docker', 'ps', '--filter', 'name=xhs-official', '--format', '{{.Names}}|{{.Status}}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            container_running = 'xhs-official' in ps_output.stdout
            
            result = {
                "running": container_running,
                "containers": []
            }
            
            if container_running:
                lines = ps_output.stdout.strip().split('\n')
                for line in lines:
                    if line:
                        name, status = line.split('|', 1)
                        result["containers"].append({"name": name, "status": status})
            
            return result
        except Exception as e:
            return {"running": False, "error": str(e)}
    
    def _check_disk_usage(self) -> Dict:
        """检查磁盘使用率"""
        try:
            output = subprocess.run(
                ['df', '-h', '/'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            lines = output.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 5:
                    usage_percent = int(parts[4].replace('%', ''))
                    return {
                        "usage_percent": usage_percent,
                        "total": parts[1],
                        "used": parts[2],
                        "available": parts[3],
                        "filesystem": parts[0]
                    }
            
            return {"usage_percent": 0, "error": "解析失败"}
        except Exception as e:
            return {"usage_percent": 0, "error": str(e)}
    
    def _check_memory_usage(self) -> Dict:
        """检查内存使用率"""
        try:
            output = subprocess.run(
                ['free', '-m'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            lines = output.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 6:
                    total = int(parts[1])
                    used = int(parts[2])
                    usage_percent = int((used / total) * 100) if total > 0 else 0
                    
                    return {
                        "usage_percent": usage_percent,
                        "total_mb": total,
                        "used_mb": used,
                        "free_mb": int(parts[3]),
                        "available_mb": int(parts[6]) if len(parts) > 6 else 0
                    }
            
            return {"usage_percent": 0, "error": "解析失败"}
        except Exception as e:
            return {"usage_percent": 0, "error": str(e)}
    
    def _check_cpu_usage(self) -> Dict:
        """检查CPU使用率"""
        try:
            # 使用/proc/stat计算CPU使用率
            with open('/proc/stat', 'r') as f:
                lines = f.readlines()
            
            for line in lines:
                if line.startswith('cpu '):
                    parts = line.split()
                    user = int(parts[1])
                    nice = int(parts[2])
                    system = int(parts[3])
                    idle = int(parts[4])
                    iowait = int(parts[5]) if len(parts) > 5 else 0
                    irq = int(parts[6]) if len(parts) > 6 else 0
                    softirq = int(parts[7]) if len(parts) > 7 else 0
                    
                    total = user + nice + system + idle + iowait + irq + softirq
                    used = total - idle
                    usage_percent = int((used / total) * 100) if total > 0 else 0
                    
                    return {
                        "usage_percent": usage_percent,
                        "user": user,
                        "system": system,
                        "idle": idle,
                        "total": total
                    }
            
            return {"usage_percent": 0, "error": "数据不可用"}
        except Exception as e:
            return {"usage_percent": 0, "error": str(e)}
    
    def _process_system_alerts(self, system_status: Dict):
        """处理系统状态告警"""
        system_config = self.config.get('system_monitoring', {})
        
        # 检查服务状态
        if 'service_status' in system_status['checks']:
            service_check = system_status['checks']['service_status']
            if not service_check.get('active', False):
                self.send_alert(
                    "服务停止",
                    f"xhs-automation服务已停止: {service_check.get('status', 'unknown')}",
                    "critical"
                )
        
        # 检查Docker容器
        if 'docker_container' in system_status['checks']:
            docker_check = system_status['checks']['docker_container']
            if not docker_check.get('running', False):
                self.send_alert(
                    "Docker容器停止",
                    "xhs-official容器未运行，小红书API服务不可用",
                    "critical"
                )
        
        # 检查磁盘使用率
        if 'disk_usage' in system_status['checks']:
            disk_check = system_status['checks']['disk_usage']
            threshold = system_config.get('disk_warning_threshold', 80)
            
            if 'usage_percent' in disk_check and disk_check['usage_percent'] >= threshold:
                self.send_alert(
                    "磁盘使用率过高",
                    f"磁盘使用率: {disk_check['usage_percent']}% (阈值: {threshold}%)",
                    "warning"
                )
        
        # 检查内存使用率
        if 'memory_usage' in system_status['checks']:
            memory_check = system_status['checks']['memory_usage']
            threshold = system_config.get('memory_warning_threshold', 85)
            
            if 'usage_percent' in memory_check and memory_check['usage_percent'] >= threshold:
                self.send_alert(
                    "内存使用率过高",
                    f"内存使用率: {memory_check['usage_percent']}% (阈值: {threshold}%)",
                    "warning"
                )
        
        # 检查CPU使用率
        if 'cpu_usage' in system_status['checks']:
            cpu_check = system_status['checks']['cpu_usage']
            threshold = system_config.get('cpu_warning_threshold', 90)
            
            if 'usage_percent' in cpu_check and cpu_check['usage_percent'] >= threshold:
                self.send_alert(
                    "CPU使用率过高",
                    f"CPU使用率: {cpu_check['usage_percent']}% (阈值: {threshold}%)",
                    "warning"
                )
    
    def run_comprehensive_check(self):
        """运行全面检查"""
        logger.info("开始全面系统检查...")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "cookie_status": self.check_cookie_status(),
            "system_status": self.check_system_status(),
            "storage_management": self.manage_storage()
        }
        
        # 生成检查报告
        report = self._generate_check_report(results)
        logger.info(f"全面检查完成: {report}")
        
        # 发送检查完成通知
        self.send_alert(
            "系统检查完成",
            f"检查结果: {report}",
            "info"
        )
        
        return results
    
    def _generate_check_report(self, results: Dict) -> str:
        """生成检查报告摘要"""
        cookie = results.get('cookie_status', {})
        system = results.get('system_status', {}).get('checks', {})
        storage = results.get('storage_management', {})
        
        # Cookie状态
        cookie_status = cookie.get('status', 'unknown')
        cookie_msg = cookie.get('message', '')
        
        # 服务状态
        service_status = "未知"
        if 'service_status' in system:
            service_check = system['service_status']
            service_status = "运行中" if service_check.get('active', False) else "停止"
        
        # Docker状态
        docker_status = "未知"
        if 'docker_container' in system:
            docker_check = system['docker_container']
            docker_status = "运行中" if docker_check.get('running', False) else "停止"
        
        # 磁盘使用率
        disk_usage = "未知"
        if 'disk_usage' in system:
            disk_check = system['disk_usage']
            disk_usage = f"{disk_check.get('usage_percent', 0)}%"
        
        # 存储清理
        storage_freed = storage.get('total_freed', 0)
        
        report_parts = []
        report_parts.append(f"Cookie: {cookie_status} ({cookie_msg})")
        report_parts.append(f"服务: {service_status}")
        report_parts.append(f"Docker: {docker_status}")
        report_parts.append(f"磁盘: {disk_usage}")
        if storage_freed > 0:
            report_parts.append(f"清理: {storage_freed}字节")
        
        return " | ".join(report_parts)

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='小红书自动化系统监控工具')
    parser.add_argument('--config', help='配置文件路径')
    parser.add_argument('--check-cookie', action='store_true', help='检查Cookie状态')
    parser.add_argument('--check-system', action='store_true', help='检查系统状态')
    parser.add_argument('--cleanup', action='store_true', help='清理存储空间')
    parser.add_argument('--full-check', action='store_true', help='运行全面检查')
    parser.add_argument('--test-webhook', action='store_true', help='测试Webhook发送')
    
    args = parser.parse_args()
    
    # 初始化监控系统
    monitor = MonitoringSystem(args.config)
    
    if args.check_cookie:
        result = monitor.check_cookie_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.check_system:
        result = monitor.check_system_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.cleanup:
        result = monitor.manage_storage()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.full_check:
        result = monitor.run_comprehensive_check()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.test_webhook:
        success = monitor.send_alert(
            "Webhook测试",
            "这是一条测试消息，用于验证Webhook配置是否正确。",
            "info"
        )
        print(f"Webhook测试{'成功' if success else '失败'}")
    
    else:
        # 默认运行全面检查
        result = monitor.run_comprehensive_check()
        print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()