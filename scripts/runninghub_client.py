#!/usr/bin/env python3
"""
RunningHub API Python 客户端
用于小红书自动化系统的AI图片生成
"""

import os
import sys
import json
import time
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests

# 配置日志
logger = logging.getLogger(__name__)

class RunningHubClient:
    """RunningHub API 客户端"""
    
    def __init__(self, 
                 api_key: str = None,
                 consumer_api_key: str = None,
                 enterprise_api_key: str = None,
                 base_url: str = "https://www.runninghub.cn",
                 output_dir: str = "/home/ubuntu/xhs-automation/images/runninghub_generated"):
        """
        初始化 RunningHub 客户端
        
        Args:
            api_key: 企业级API密钥 (可选)
            consumer_api_key: 消费级API密钥 (优先使用)
            enterprise_api_key: 企业级共享API密钥 (备用)
            base_url: API基础URL
            output_dir: 图片输出目录
        """
        # 支持双API Key配置：优先消费级，失败时切换到企业级
        self.consumer_api_key = consumer_api_key or api_key
        self.enterprise_api_key = enterprise_api_key
        
        # 当前使用的API Key
        self.api_key = self.consumer_api_key
        self.current_api_type = "consumer"  # consumer 或 enterprise
        
        if not self.api_key and not self.enterprise_api_key:
            raise ValueError("必须提供API密钥（consumer_api_key 或 enterprise_api_key）")
        
        self.base_url = base_url.rstrip('/')
        self.output_dir = Path(output_dir)
        
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 默认工作流配置（可根据需要覆盖）
        self.default_workflow_id = "2027074632334970882"
        self.default_workflow_json = "/home/ubuntu/else/runninghub-t2i/scc 文生图_api.json"
        
        # 成本跟踪
        self.cost_per_task = 0.200  # 消费级
        self.total_cost = 0.0
        self.task_count = 0
        
        # 缓存已生成的图片（基于提示词哈希）
        self.image_cache = {}
        
        # 会话保持
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Xiaohongshu-Automation/1.0',
            'Content-Type': 'application/json'
        })
        
        logger.info(f"RunningHub客户端初始化完成 (主API: 消费级, 备用: {'企业级' if self.enterprise_api_key else '无'})")
        logger.info(f"每张图片成本: {self.cost_per_task}元")
        logger.info(f"输出目录: {self.output_dir}")
    
    def _switch_to_enterprise(self) -> bool:
        """切换到企业级API"""
        if not self.enterprise_api_key:
            logger.error("企业级API Key未配置，无法切换")
            return False
        
        if self.current_api_type == "enterprise":
            logger.warning("当前已使用企业级API，无法再次切换")
            return False
        
        logger.warning("消费级API不可用，切换到企业级API")
        self.api_key = self.enterprise_api_key
        self.current_api_type = "enterprise"
        self.cost_per_task = 0.800  # 企业级成本
        logger.info(f"已切换到企业级API，每张图片成本: {self.cost_per_task}元")
        return True
    
    def _is_api_unavailable_error(self, error: Exception) -> bool:
        """判断是否是API不可用错误（需要切换备用API）"""
        error_str = str(error).lower()
        
        # API认证/权限错误
        api_unavailable_patterns = [
            "token_invalid",
            "token_expired",
            "unauthorized",
            "invalid api key",
            "api key invalid",
            "access denied",
            "forbidden",
        ]
        
        # 网络连接错误
        connection_errors = [
            "connection refused",
            "connection timeout",
            "connection error",
            "timeout",
            "failed to connect",
            "network error",
            "reset by peer",
            "ssl error",
        ]
        
        for pattern in api_unavailable_patterns + connection_errors:
            if pattern in error_str:
                return True
        
        return False
    
    def _load_workflow_json(self, workflow_json_path: str = None) -> Dict:
        """加载工作流JSON配置"""
        if workflow_json_path is None:
            workflow_json_path = self.default_workflow_json
        
        try:
            with open(workflow_json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"工作流文件不存在: {workflow_json_path}")
            raise
        except Exception as e:
            logger.error(f"加载工作流JSON失败: {e}")
            raise
    
    def _find_text_node(self, workflow_data: Dict) -> Tuple[str, str]:
        """在工作流中查找文本输入节点"""
        # 首先查找CR Text节点
        for node_id, node_content in workflow_data.items():
            if node_content.get('class_type') == 'CR Text':
                return node_id, 'text'
        
        # 如果没有找到CR Text节点，查找其他文本字段
        for node_id, node_content in workflow_data.items():
            inputs = node_content.get('inputs', {})
            for field_name, field_value in inputs.items():
                if isinstance(field_value, str) and len(field_value) > 10:
                    return node_id, field_name
        
        raise ValueError("在工作流中未找到文本输入节点")
    
    def _create_node_modifications(self, 
                                  workflow_data: Dict, 
                                  prompt: str,
                                  width: int = None,
                                  height: int = None,
                                  aspect_ratio: str = None,
                                  resolution: str = None,
                                  seed: int = None) -> List[Dict]:
        """创建节点修改列表"""
        modifications = []
        
        # 1. 修改文本提示词
        text_node_id, text_field_name = self._find_text_node(workflow_data)
        modifications.append({
            "nodeId": text_node_id,
            "fieldName": text_field_name,
            "fieldValue": prompt
        })
        
        # 2. 查找并修改尺寸参数
        for node_id, node_content in workflow_data.items():
            inputs = node_content.get('inputs', {})
            
            # 设置宽高比 (aspectRatio)
            if aspect_ratio and 'aspectRatio' in inputs:
                modifications.append({
                    "nodeId": node_id,
                    "fieldName": "aspectRatio",
                    "fieldValue": aspect_ratio
                })
            
            # 设置分辨率 (resolution)
            if resolution and 'resolution' in inputs:
                modifications.append({
                    "nodeId": node_id,
                    "fieldName": "resolution",
                    "fieldValue": resolution
                })
            elif not resolution and (width or height):
                # 根据宽高自动选择合适的分辨率
                if width and height:
                    if width >= 2048 or height >= 2048:
                        resolution = "4k"
                    elif width >= 1024 or height >= 1024:
                        resolution = "2k"
                    else:
                        resolution = "1k"
                    
                    if 'resolution' in inputs:
                        modifications.append({
                            "nodeId": node_id,
                            "fieldName": "resolution",
                            "fieldValue": resolution
                        })
            
            # 设置种子 (seed)
            if seed is not None and 'seed' in inputs:
                modifications.append({
                    "nodeId": node_id,
                    "fieldName": "seed",
                    "fieldValue": str(seed)
                })
        
        return modifications
    
    def _call_api(self, endpoint: str, data: Dict, method: str = "POST") -> Dict:
        """调用 RunningHub API"""
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            'Host': 'www.runninghub.cn',
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                timeout=180
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"API调用超时: {endpoint}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"API调用失败: {endpoint}, 错误: {e}")
            raise
    
    def generate_image(self,
                      prompt: str,
                      workflow_id: str = None,
                      workflow_json: str = None,
                      width: int = 1024,
                      height: int = 1024,
                      aspect_ratio: str = None,
                      resolution: str = None,
                      seed: int = None,
                      use_rtx4090: bool = False,
                      cache_key: str = None,
                      _retry_with_enterprise: bool = False) -> Dict:
        """
        生成图片
        
        Args:
            prompt: 图片提示词
            workflow_id: 工作流ID (默认使用配置的)
            workflow_json: 工作流JSON路径 (默认使用配置的)
            width: 图片宽度 (像素) - 已弃用，使用 aspect_ratio 代替
            height: 图片高度 (像素) - 已弃用，使用 aspect_ratio 代替
            aspect_ratio: 宽高比，如 "9:16"(竖版), "16:9"(横版), "1:1"(方形)
            resolution: 分辨率，如 "1k", "2k", "4k"
            seed: 随机种子，用于生成可复现的图片
            use_rtx4090: 是否使用RTX 4090实例
            cache_key: 缓存键，如果提供且命中缓存则返回缓存的图片
            _retry_with_enterprise: 内部参数，是否正在使用企业级重试
        
        Returns:
            Dict: 包含生成结果的信息
        """
        start_time = time.time()
        
        # 检查缓存
        if cache_key and cache_key in self.image_cache:
            cached_image = self.image_cache[cache_key]
            if os.path.exists(cached_image['path']):
                logger.info(f"使用缓存图片: {cache_key}")
                return cached_image
        
        # 准备参数
        if workflow_id is None:
            workflow_id = self.default_workflow_id
        
        # 加载工作流配置
        workflow_data = self._load_workflow_json(workflow_json)
        
        # 创建节点修改
        modifications = self._create_node_modifications(
            workflow_data, prompt, width, height, aspect_ratio, resolution, seed
        )
        
        logger.info(f"生成图片: '{prompt[:50]}...' [API: {self.current_api_type}]")
        logger.debug(f"节点修改: {modifications}")
        
        try:
            # 1. 创建任务
            create_data = {
                "apiKey": self.api_key,
                "workflowId": workflow_id,
                "nodeInfoList": modifications
            }
            
            if use_rtx4090:
                create_data["use_rtx4090"] = True
            
            create_result = self._call_api("/task/openapi/create", create_data)
            
            if create_result.get("code") != 0:
                error_msg = create_result.get("msg", "未知错误")
                raise ValueError(f"创建任务失败: {error_msg}")
            
            task_id = create_result["data"]["taskId"]
            logger.info(f"任务创建成功: {task_id}")
            
            # 2. 轮询任务状态
            max_attempts = 36  # 最多等待180秒 (36 * 5秒)
            outputs = None
            
            for attempt in range(max_attempts):
                time.sleep(5)  # 每5秒检查一次
                
                poll_data = {
                    "apiKey": self.api_key,
                    "taskId": task_id
                }
                
                try:
                    poll_result = self._call_api("/task/openapi/outputs", poll_data)
                    
                    # 任务完成（成功返回结果）
                    if poll_result.get("code") == 0 and poll_result.get("data"):
                        if isinstance(poll_result["data"], list) and len(poll_result["data"]) > 0:
                            outputs = poll_result["data"]
                            logger.info(f"任务完成，获取到 {len(outputs)} 个输出")
                            break
                        
                        # 检查任务状态
                        task_status = poll_result["data"].get("taskStatus")
                        if task_status in ["RUNNING", "QUEUED"]:
                            if attempt % 5 == 0:  # 每10秒记录一次
                                logger.info(f"任务状态: {task_status} (尝试 {attempt + 1}/{max_attempts})")
                            continue
                        else:
                            logger.info(f"任务状态: {task_status}")
                            break
                    
                    # 任务仍在运行中 (code 804)
                    elif poll_result.get("code") == 804:
                        if attempt % 5 == 0:
                            logger.info(f"任务运行中 (尝试 {attempt + 1}/{max_attempts})")
                        continue
                    
                    # 其他错误
                    else:
                        error_msg = poll_result.get("msg", "未知错误")
                        logger.warning(f"轮询返回错误: {error_msg}")
                        if attempt >= max_attempts - 1:
                            raise ValueError(f"任务轮询失败: {error_msg}")
                        continue
                        
                except Exception as poll_error:
                    logger.warning(f"轮询失败 (尝试 {attempt + 1}): {poll_error}")
                    if attempt >= max_attempts - 1:
                        raise
            
            if not outputs:
                raise TimeoutError(f"任务轮询超时: {task_id}")
            
            # 3. 下载图片
            saved_paths = []
            for i, output in enumerate(outputs):
                if output.get("fileUrl"):
                    image_url = output["fileUrl"]
                    
                    # 生成文件名
                    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
                    timestamp = int(time.time())
                    filename = f"runninghub_{prompt_hash}_{timestamp}_{i}.png"
                    save_path = self.output_dir / filename
                    
                    # 下载图片
                    logger.info(f"下载图片: {os.path.basename(filename)}")
                    try:
                        image_response = requests.get(image_url, timeout=30)
                        image_response.raise_for_status()
                        
                        with open(save_path, 'wb') as f:
                            f.write(image_response.content)
                        
                        # 验证图片文件
                        if save_path.stat().st_size > 1000:  # 至少1KB
                            saved_paths.append(str(save_path))
                            logger.info(f"图片保存到: {save_path} ({save_path.stat().st_size // 1024}KB)")
                        else:
                            logger.warning(f"图片文件太小，可能下载失败: {save_path}")
                    except Exception as download_error:
                        logger.error(f"下载图片失败: {download_error}")
                        continue
            
            if not saved_paths:
                raise ValueError("任务完成但未成功下载图片")
            
            # 4. 更新成本和统计
            self.task_count += 1
            self.total_cost += self.cost_per_task
            
            generation_time = time.time() - start_time
            
            result = {
                "success": True,
                "task_id": task_id,
                "image_paths": saved_paths,
                "prompt": prompt,
                "cost": self.cost_per_task,
                "generation_time": round(generation_time, 2),
                "cache_key": cache_key,
                "output_dir": str(self.output_dir)
            }
            
            # 保存到缓存
            if cache_key:
                self.image_cache[cache_key] = {
                    "path": saved_paths[0],
                    "prompt": prompt,
                    "task_id": task_id,
                    "cost": self.cost_per_task,
                    "generated_at": time.time(),
                    "generation_time": generation_time
                }
            
            logger.info(f"✅ 图片生成成功: {saved_paths[0]} (成本: {self.cost_per_task}元, 时间: {generation_time:.1f}秒)")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 图片生成失败: {e}")
            
            # 检查是否是API不可用错误，且可以切换到企业级API
            if not _retry_with_enterprise and self._is_api_unavailable_error(e):
                if self._switch_to_enterprise():
                    logger.info("尝试使用企业级API重新生成...")
                    # 递归调用，使用企业级API
                    return self.generate_image(
                        prompt=prompt,
                        workflow_id=workflow_id,
                        workflow_json=workflow_json,
                        width=width,
                        height=height,
                        use_rtx4090=use_rtx4090,
                        cache_key=cache_key,
                        _retry_with_enterprise=True
                    )
            
            return {
                "success": False,
                "error": str(e),
                "prompt": prompt,
                "generation_time": round(time.time() - start_time, 2)
            }
    
    def generate_image_for_topic(self,
                               topic: str,
                               module: str = None,
                               style: str = "卡通风格",
                               width: int = 1024,
                               height: int = 1024) -> Dict:
        """
        为特定话题生成图片（小红书专用）
        
        Args:
            topic: 话题/主题
            module: 内容模块 (影响图片风格)
            style: 图片风格
            width: 图片宽度
            height: 图片高度
        
        Returns:
            Dict: 生成结果
        """
        # 根据模块和话题生成优化提示词
        if module == "academic_efficiency":
            prompt = f"与'{topic}'相关的教育插图，清晰易懂，适合学习分享，{style}"
        elif module == "visual_creation":
            prompt = f"'{topic}'主题的艺术创作，创意设计，高质量细节，{style}"
        elif module == "geek_daily":
            prompt = f"'{topic}'相关的技术场景，极客风格，现代感，{style}"
        elif module == "hot_topics":
            prompt = f"'{topic}'主题的现代插图，社交媒体风格，吸引眼球，{style}"
        else:
            prompt = f"'{topic}'，{style}，高质量图片"
        
        # 添加小红书优化
        prompt += "，适合小红书分享，高分辨率，美观"
        
        # 使用缓存键（话题+模块+风格）
        cache_key = hashlib.md5(f"{topic}_{module}_{style}".encode()).hexdigest()
        
        return self.generate_image(
            prompt=prompt,
            width=width,
            height=height,
            cache_key=cache_key
        )
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_tasks": self.task_count,
            "total_cost": round(self.total_cost, 3),
            "avg_cost_per_task": self.cost_per_task,
            "cached_images": len(self.image_cache),
            "output_dir": str(self.output_dir),
            "api_type": self.current_api_type
        }
    
    def clear_cache(self):
        """清空缓存"""
        self.image_cache.clear()
        logger.info("图片缓存已清空")
    
    def save_cache_info(self, filepath: str = None):
        """保存缓存信息到文件"""
        if filepath is None:
            filepath = self.output_dir / "cache_info.json"
        
        cache_info = {
            "cache_size": len(self.image_cache),
            "total_cost": self.total_cost,
            "task_count": self.task_count,
            "cached_images": list(self.image_cache.keys()),
            "timestamp": datetime.now().isoformat()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cache_info, f, ensure_ascii=False, indent=2)
        
        logger.info(f"缓存信息保存到: {filepath}")


# 使用示例和测试
if __name__ == "__main__":
    import argparse
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description="RunningHub客户端测试")
    parser.add_argument("--prompt", help="图片提示词", default="一只戴着帽子的猫，卡通风格")
    parser.add_argument("--topic", help="话题", default=None)
    parser.add_argument("--module", help="内容模块", default="visual_creation")
    parser.add_argument("--api-key", help="API密钥", default=None)
    parser.add_argument("--consumer-key", help="消费级API密钥", default="8d80d8df1e5d4585916c929c20db31ee")
    parser.add_argument("--stats", help="显示统计信息", action="store_true")
    
    args = parser.parse_args()
    
    # 初始化客户端
    try:
        client = RunningHubClient(
            consumer_api_key=args.consumer_key or args.api_key,
            output_dir="/tmp/runninghub_test"
        )
        
        if args.stats:
            stats = client.get_stats()
            print("📊 RunningHub客户端统计:")
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        elif args.topic:
            print(f"为话题生成图片: {args.topic} ({args.module})")
            result = client.generate_image_for_topic(
                topic=args.topic,
                module=args.module,
                style="卡通风格"
            )
        else:
            print(f"生成图片: '{args.prompt}'")
            result = client.generate_image(prompt=args.prompt)
        
        if not args.stats:
            if result["success"]:
                print(f"✅ 生成成功!")
                print(f"   图片路径: {result['image_paths'][0]}")
                print(f"   任务ID: {result['task_id']}")
                print(f"   成本: {result['cost']}元")
                print(f"   时间: {result['generation_time']}秒")
            else:
                print(f"❌ 生成失败: {result['error']}")
            
            # 显示统计
            stats = client.get_stats()
            print(f"\n📊 统计: 总计 {stats['total_tasks']}次, 成本 {stats['total_cost']}元")
    
    except Exception as e:
        print(f"❌ 客户端初始化或执行失败: {e}")
        sys.exit(1)