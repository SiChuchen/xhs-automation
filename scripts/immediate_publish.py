#!/usr/bin/env python3
"""
小红书即时发布脚本
用户要求时立即执行发帖，绕过所有时间限制
"""

import os
import sys
import json
import logging
import subprocess
import time
import argparse
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImmediatePublisher:
    """即时发布器，绕过所有时间限制"""
    
    def __init__(self, config_path=None, soul_path=None):
        """
        初始化即时发布器
        
        Args:
            config_path: 配置文件路径，默认使用标准路径
            soul_path: 灵魂文件路径，默认使用标准路径
        """
        # 设置默认路径
        if config_path is None:
            config_path = "/home/ubuntu/xhs-automation/config/publish_config.json"
        if soul_path is None:
            soul_path = "/home/ubuntu/xhs-automation/config/soul.md"
        
        self.config_path = config_path
        self.soul_path = soul_path
        
        # 确保soul文件存在
        if not os.path.exists(soul_path):
            logger.warning(f"灵魂文件不存在: {soul_path}，创建临时文件")
            with open(soul_path, 'w', encoding='utf-8') as f:
                f.write("# 林晓芯的灵魂\n\n理工科女大、效率控、技术宅、微社恐、逻辑严密")
        
        # 导入必要的模块
        try:
            from scripts.xhs_automation_monitored import CharacterPersona
            self.CharacterPersona = CharacterPersona
            logger.info("✅ CharacterPersona 导入成功")
        except ImportError as e:
            logger.error(f"导入CharacterPersona失败: {e}")
            raise
        
        # 初始化人物设定
        self.persona = None
        self._init_persona()
        
        # MCP API设置
        self.base_url = "http://localhost:18060"
        self.api_url = f"{self.base_url}/api/v1"
        
        logger.info("🔄 即时发布器初始化完成")
    
    def _init_persona(self):
        """初始化人物设定"""
        try:
            self.persona = self.CharacterPersona(self.config_path, self.soul_path)
            logger.info(f"✅ 人物设定初始化成功: {self.persona.character['name']}")
        except Exception as e:
            logger.error(f"初始化人物设定失败: {e}")
            raise
    
    def check_login_status(self):
        """检查登录状态"""
        import requests
        
        try:
            response = requests.get(f"{self.api_url}/login/status", timeout=30)
            data = response.json()
            
            if data.get('success') and data.get('data', {}).get('is_logged_in'):
                logger.info(f"✅ 登录状态正常: {data.get('data', {}).get('username')}")
                return True
            else:
                logger.warning(f"⚠️ 登录状态异常: {data}")
                return False
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False
    
    def generate_content(self, module=None, topic=None):
        """
        生成内容
        
        Args:
            module: 指定内容模块，如未指定则随机选择
            topic: 指定话题，如未指定则随机选择
            
        Returns:
            tuple: (module, topic, title, content, image_path, tags)
        """
        # 如果未指定模块或话题，随机选择
        if module is None or topic is None:
            module, topic, tags = self.persona.get_random_topic()
        else:
            # 获取指定模块的标签
            tags = self.persona.content_modules.get(module, {}).get('tags', [])
            if not tags:
                # 如果模块不存在或没有标签，使用默认标签
                tags = ["#技术分享", "#效率工具", "#大学生活"]
        
        # 生成标题和内容
        title, content, image_prompt = self.persona.generate_content(module, topic)
        
        # 选择图片（使用增强版图片管理器，优先尝试AI生成）
        image_path = None
        if self.persona.image_manager:
            try:
                # 统一图片优化和复制函数
                def optimize_and_copy_to_container(source_path, target_name=None):
                    """
                    统一流程：优化图片并复制到容器目录
                    返回容器内路径
                    """
                    # 生成目标文件名
                    if target_name is None:
                        base_name = os.path.basename(source_path)
                        name_without_ext = os.path.splitext(base_name)[0]
                        target_name = f"{name_without_ext}_1080.jpg"
                    
                    # 容器内路径
                    container_path = f"/app/images/{target_name}"
                    
                    # 主机目标路径
                    docker_dir = "/home/ubuntu/xhs-automation/images"
                    os.makedirs(docker_dir, exist_ok=True)
                    host_path = f"{docker_dir}/{target_name}"
                    
                    # 优化图片（强制使用1080尺寸）
                    try:
                        subprocess.run([
                            "python3", "scripts/optimize_images.py",
                            source_path, "-o", host_path, "-s", "720"
                        ], cwd="/home/ubuntu/xhs-automation", capture_output=True, timeout=60)
                        logger.info(f"✅ 图片已优化: {host_path}")
                    except Exception as e:
                        logger.warning(f"图片优化失败，尝试直接复制: {e}")
                        # 直接复制作为后备
                        try:
                            import shutil
                            # 如果是PNG，转换为JPG
                            if source_path.endswith('.png'):
                                from PIL import Image
                                with Image.open(source_path) as img:
                                    if img.mode == 'RGBA':
                                        background = Image.new('RGB', img.size, (255, 255, 255))
                                        background.paste(img, mask=img.split()[3])
                                        img = background
                                    img.save(host_path, 'JPEG', quality=85)
                            else:
                                shutil.copy2(source_path, host_path)
                            logger.info(f"✅ 图片已复制: {host_path}")
                        except Exception as copy_error:
                            logger.error(f"图片复制失败: {copy_error}")
                            return None
                    
                    return container_path
                
                # 优先使用 RunningHub 根据内容生成适配图片
                image_path = None
                generated_source = None
                try:
                    # 使用新的重试方法（包含视觉描述词提取）
                    if self.persona.image_manager and hasattr(self.persona.image_manager, 'generate_image_with_retry'):
                        logger.info(f"🎨 正在为内容生成适配图片(视觉描述词): {topic}")
                        result = self.persona.image_manager.generate_image_with_retry(
                            module=module,
                            topic=topic,
                            prompt=image_prompt,  # 传入文案作为提示词
                            max_retries=3,
                            retry_delay=5
                        )
                        # 处理不一致的返回值：可能是 (path, detail) 或 just path
                        if isinstance(result, tuple):
                            image_path = result[0]
                        else:
                            image_path = result
                        
                        if image_path and os.path.exists(image_path):
                            # 复制到容器目录
                            target_name = f"ai_{int(time.time())}.jpg"
                            image_path = optimize_and_copy_to_container(image_path, target_name)
                            logger.info(f"✅ AI生成图片: {image_path}")
                    elif self.persona.image_manager and hasattr(self.persona.image_manager, 'runninghub_client'):
                        # 备用：使用旧方法
                        runninghub = self.persona.image_manager.runninghub_client
                        logger.info(f"🎨 正在为内容生成适配图片(旧方法): {topic}")
                        result = runninghub.generate_image_for_topic(
                            topic=topic,
                            module=module,
                            style="卡通风格" if module == "academic_efficiency" else "高质量插图"
                        )
                        if result.get("success"):
                            generated_source = result.get("image_paths", [""])[0]
                            if generated_source:
                                # 生成与话题相关的文件名
                                safe_topic = module  # 使用模块名而非话题
                                target_name = f"ai_{int(time.time())}.jpg"
                                image_path = optimize_and_copy_to_container(generated_source, target_name)
                                logger.info(f"✅ AI生成图片: {image_path}")
                except Exception as e:
                    logger.warning(f"AI图片生成失败: {e}")
                
                # 如果没有生成图片，使用本地备用图片并优化
                if not image_path:
                    backup_sources = {
                        "academic_efficiency": "/home/ubuntu/xhs-automation/images/苗族服饰.png",  # 13MB
                        "visual_creation": "/home/ubuntu/xhs-automation/images/故宫.png",         # 13MB
                        "geek_daily": "/home/ubuntu/xhs-automation/images/断桥残雪.png",          # 12MB
                    }
                    backup_source = backup_sources.get(module, "/home/ubuntu/xhs-automation/images/test_simple.jpg")
                    
                    if os.path.exists(backup_source):
                        # 优化备用图片
                        safe_topic = module  # 使用模块名而非话题
                        target_name = f"ai_{int(time.time())}.jpg"
                        image_path = optimize_and_copy_to_container(backup_source, target_name)
                        logger.info(f"📷 备用图片已优化: {image_path}")
                    else:
                        image_path = "/app/images/test_simple_720.jpg"
                        logger.warning(f"使用默认小图: {image_path}")
                logger.info(f"✅ 图片选择完成: {os.path.basename(image_path) if image_path else '无图片'}")
                
                # 如果选择了PNG图片，尝试使用JPG版本（避免上传超时）
                if image_path and image_path.endswith('.png'):
                    jpg_path = image_path.replace('.png', '.jpg')
                    host_jpg_path = jpg_path.replace('/images/', '/home/ubuntu/xhs-automation/images/')
                    if os.path.exists(host_jpg_path):
                        logger.info(f"🔄 使用JPG版本替代PNG: {os.path.basename(jpg_path)}")
                        image_path = jpg_path
                        
            except Exception as e:
                logger.error(f"图片选择失败: {e}")
                image_path = None
        
        # 强制使用小图片并修复路径为 /app/images/
        if not image_path:
            # 强制使用小图片列表（优先使用最小的）
            character_images = [
                "/app/images/test_simple_720.jpg",      # 14KB - 最小的测试图
                "/app/images/test.jpg",             # 14KB
                "/app/images/test_vertical.jpg",    # 22KB
                "/app/images/character_original_vertical.jpg",  # 121K
                "/app/images/001原画.jpg",         # 85K
                "/app/images/001赛博版.jpg",       # 139K
                "/app/images/character_cyber_vertical.jpg",     # 189K
                "/app/images/001原画.png",         # 5.4MB（备用）
                "/app/images/001赛博版.png",        # 6.4MB（备用）
            ]
            
            for img_path in character_images:
                host_img_path = img_path.replace("/app/images/", "/home/ubuntu/xhs-automation/images/")
                if os.path.exists(host_img_path):
                    image_path = img_path
                    logger.info(f"📷 选择备用图片: {os.path.basename(image_path)}")
                    break
            
            if not image_path:
                logger.warning("⚠️ 未找到合适图片，本次发布不使用图片")
        
        return module, topic, title, content, image_path, tags
    
    def publish_content(self, title, content, image_path, tags):
        """发布内容到小红书"""
        import requests
        
        # 规范化图片路径
        if image_path:
            # 如果只是文件名，添加/images/前缀
            if '/' not in image_path:
                image_path = f"/app/images/{image_path}"
                logger.info(f"🔄 规范化图片路径: {image_path}")
            # 确保路径以/images/开头（容器内路径）
            elif not image_path.startswith('/images/'):
                # 如果是主机路径，转换为容器路径
                if image_path.startswith('/home/ubuntu/xhs-automation/images/'):
                    image_path = image_path.replace('/home/ubuntu/xhs-automation/images/', '/images/')
                    logger.info(f"🔄 转换主机路径为容器路径: {image_path}")
        
        # 准备请求数据
        payload = {
            "title": title,
            "content": content,
            "images": [image_path] if image_path else [],
            "tags": tags[:10]  # 限制标签数量
        }
        
        logger.info(f"📤 发布内容: {title}")
        logger.info(f"   图片路径: {image_path if image_path else '无图片'}")
        logger.info(f"   标签: {', '.join(tags[:3])}...")
        
        try:
            response = requests.post(
                f"{self.api_url}/publish",
                json=payload,
                timeout=120
            )
            data = response.json()
            
            if data.get('success'):
                logger.info(f"✅ 发布成功! Post ID: {data.get('data', {}).get('post_id', 'Unknown')}")
                return {
                    "success": True,
                    "post_id": data.get('data', {}).get('post_id'),
                    "data": data
                }
            else:
                error_msg = data.get('error', '未知错误')
                logger.error(f"❌ 发布失败: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "data": data
                }
                
        except Exception as e:
            logger.error(f"❌ 发布请求失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def record_publish_result(self, result, module, topic, title, image_path):
        """记录发布结果"""
        record_file = "/home/ubuntu/xhs-automation/logs/immediate_publish.json"
        
        # 确保目录存在
        os.makedirs(os.path.dirname(record_file), exist_ok=True)
        
        record = {
            "timestamp": datetime.now().isoformat(),
            "trigger": "user_immediate",
            "module": module,
            "topic": topic,
            "title": title,
            "image": image_path,
            "success": result.get('success', False),
            "post_id": result.get('post_id'),
            "error": result.get('error')
        }
        
        try:
            # 读取现有记录
            records = []
            if os.path.exists(record_file):
                with open(record_file, 'r', encoding='utf-8') as f:
                    records = json.load(f)
            
            # 添加新记录
            records.append(record)
            
            # 保存记录（保留最近100条）
            if len(records) > 100:
                records = records[-100:]
            
            with open(record_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📝 发布记录已保存: {record_file}")
            
        except Exception as e:
            logger.error(f"保存发布记录失败: {e}")
    
    def publish_immediate(self, module=None, topic=None):
        """
        立即发布（用户要求）
        
        Args:
            module: 指定内容模块
            topic: 指定话题
            
        Returns:
            dict: 发布结果
        """
        logger.info("🚀 执行用户要求的即时发布...")
        
        # 1. 检查登录状态
        if not self.check_login_status():
            return {
                "success": False,
                "error": "登录状态异常，请检查cookies"
            }
        
        # 2. 生成内容
        module, topic, title, content, image_path, tags = self.generate_content(module, topic)
        
        # 3. 发布内容
        result = self.publish_content(title, content, image_path, tags)
        
        # 4. 记录结果
        self.record_publish_result(result, module, topic, title, image_path)
        
        return result
    
    def publish_random(self):
        """发布随机内容（默认行为）"""
        return self.publish_immediate(module=None, topic=None)
    
    def publish_with_topic(self, topic, module=None):
        """
        发布指定话题的内容
        
        Args:
            topic: 指定话题
            module: 指定模块（可选）
            
        Returns:
            dict: 发布结果
        """
        logger.info(f"发布指定话题: {topic}")
        return self.publish_immediate(module=module, topic=topic)


def quick_check_login():
    """快速检查登录状态（不加载任何模块，节省资源）"""
    import requests
    try:
        response = requests.get("http://localhost:18060/api/v1/login/status", timeout=30)
        data = response.json()
        if data.get('success') and data.get('data', {}).get('is_logged_in'):
            return True, data.get('data', {}).get('username', 'unknown')
        return False, None
    except Exception as e:
        return False, str(e)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="小红书即时发布工具")
    parser.add_argument("--topic", help="指定话题")
    parser.add_argument("--module", help="指定内容模块")
    parser.add_argument("--list-modules", action="store_true", help="列出所有可用模块和话题")
    parser.add_argument("--check-login", action="store_true", help="只检查登录状态")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    
    args = parser.parse_args()
    
    try:
        # 对于 --check-login 和正常发布，先快速检查登录状态（节省资源）
        if args.check_login or args.topic or not any([args.list_modules, args.stats]):
            print("🔍 快速检查登录状态...")
            login_ok, login_info = quick_check_login()
            if not login_ok:
                print(f"❌ 登录状态异常: {login_info}")
                print("请确保小红书容器正在运行且已登录")
                sys.exit(1)
            print(f"✅ 登录状态正常: {login_info}")
            
            # 如果只是检查登录，退出
            if args.check_login:
                return
        
        # 初始化发布器（登录检查通过后才加载重资源模块）
        print("📦 初始化发布器...")
        publisher = ImmediatePublisher()
        
        # 列出模块和话题
        if args.list_modules:
            print("📋 可用内容模块:")
            for module_name, module_data in publisher.persona.content_modules.items():
                print(f"\n  {module_name} (权重: {module_data['weight']})")
                print(f"    话题: {', '.join(module_data['topics'])}")
                print(f"    标签: {', '.join(module_data['tags'][:3])}...")
            return
        
        # 只检查登录状态
        if args.check_login:
            status = publisher.check_login_status()
            print(f"登录状态: {'✅ 正常' if status else '❌ 异常'}")
            return
        
        # 显示统计信息
        if args.stats:
            print("📊 即时发布统计:")
            record_file = "/home/ubuntu/xhs-automation/logs/immediate_publish.json"
            if os.path.exists(record_file):
                with open(record_file, 'r', encoding='utf-8') as f:
                    records = json.load(f)
                print(f"  总发布次数: {len(records)}")
                success_count = sum(1 for r in records if r.get('success'))
                print(f"  成功次数: {success_count}")
                print(f"  成功率: {success_count/len(records)*100:.1f}%" if records else "0%")
                
                # 最近5次发布
                if records:
                    print(f"\n  最近5次发布:")
                    for i, record in enumerate(records[-5:]):
                        status = "✅" if record.get('success') else "❌"
                        print(f"    {i+1}. {record['timestamp'][:16]} - {record['title']} {status}")
            else:
                print("  尚无发布记录")
            return
        
        # 执行发布
        if args.topic:
            result = publisher.publish_with_topic(args.topic, args.module)
        else:
            result = publisher.publish_random()
        
        # 输出结果
        print("\n" + "="*60)
        if result.get('success'):
            print("🎉 即时发布成功!")
            print(f"   帖子ID: {result.get('post_id', 'Unknown')}")
        else:
            print("❌ 即时发布失败")
            print(f"   错误: {result.get('error', '未知错误')}")
        print("="*60)
        
        # 返回适当的退出代码
        sys.exit(0 if result.get('success') else 1)
        
    except Exception as e:
        logger.error(f"即时发布执行失败: {e}")
        print(f"❌ 程序执行异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()