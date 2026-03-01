"""
ComfyUI Workflow 集成
支持复杂工作流的动态参数注入
"""

import os
import json
import logging
import base64
import requests
from typing import Dict, List, Optional, Any
from pathlib import Path
from PIL import Image
import io

logger = logging.getLogger(__name__)


class ComfyUIWorkflow:
    """ComfyUI 工作流执行器"""
    
    DEFAULT_TEMPLATE_DIR = "config/workflows"
    
    def __init__(self, api_url: str = None, auth: str = None):
        self.api_url = api_url or os.environ.get("COMFYUI_API_URL", "http://127.0.0.1:8188")
        self.auth = auth
        self.template = None
        self.last_prompt_id = None
        self.history = {}
    
    def load_template(self, template_path: str) -> Dict:
        """加载工作流模板"""
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"模板不存在: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = json.load(f)
        
        logger.info(f"已加载工作流模板: {template_path}")
        return self.template
    
    def load_template_by_name(self, name: str) -> Dict:
        """按名称加载模板"""
        template_path = os.path.join(self.DEFAULT_TEMPLATE_DIR, f"{name}.json")
        return self.load_template(template_path)
    
    def inject_prompt(self, node_id: str, prompt: str) -> bool:
        """注入提示词到指定节点"""
        if not self.template:
            raise ValueError("请先加载模板")
        
        if "nodes" in self.template:
            for node in self.template["nodes"]:
                if str(node.get("id")) == node_id:
                    if "properties" not in node:
                        node["properties"] = {}
                    node["properties"]["text"] = prompt
                    logger.info(f"已注入提示词到节点 {node_id}")
                    return True
        
        if node_id in self.template:
            self.template[node_id]["inputs"]["text"] = prompt
            return True
        
        logger.warning(f"未找到节点: {node_id}")
        return False
    
    def inject_seed(self, node_id: str, seed: int = -1) -> bool:
        """注入种子到 KSampler 节点"""
        if not self.template:
            raise ValueError("请先加载模板")
        
        seed = seed if seed > 0 else int.from_bytes(os.urandom(4), 'big')
        
        if "nodes" in self.template:
            for node in self.template["nodes"]:
                if str(node.get("id")) == node_id:
                    if "widgets_values" in node:
                        node["widgets_values"][0] = seed
                        logger.info(f"已注入种子到节点 {node_id}: {seed}")
                        return True
        
        logger.warning(f"未找到 KSampler 节点: {node_id}")
        return False
    
    def inject_lora(self, node_id: str, lora_name: str, strength: float = 1.0) -> bool:
        """注入 LoRA 到加载器节点"""
        if not self.template:
            raise ValueError("请先加载模板")
        
        if "nodes" in self.template:
            for node in self.template["nodes"]:
                if str(node.get("id")) == node_id:
                    if "widgets_values" in node:
                        node["widgets_values"] = [lora_name, "model", strength, "clip", strength]
                        logger.info(f"已注入 LoRA: {lora_name} 到节点 {node_id}")
                        return True
        
        logger.warning(f"未找到 LoRA 节点: {node_id}")
        return False
    
    def inject_controlnet(self, node_id: str, image_path: str) -> bool:
        """注入 ControlNet 参考图"""
        if not self.template:
            raise ValueError("请先加载模板")
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片不存在: {image_path}")
        
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        if "nodes" in self.template:
            for node in self.template["nodes"]:
                if str(node.get("id")) == node_id:
                    node["properties"]["image"] = image_data
                    logger.info(f"已注入 ControlNet 图片到节点 {node_id}")
                    return True
        
        logger.warning(f"未找到 ControlNet 节点: {node_id}")
        return False
    
    def inject_image(self, node_id: str, image_path: str) -> bool:
        """注入输入图片"""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片不存在: {image_path}")
        
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        if "nodes" in self.template:
            for node in self.template["nodes"]:
                if str(node.get("id")) == node_id:
                    if "properties" not in node:
                        node["properties"] = {}
                    node["properties"]["image"] = image_data
                    logger.info(f"已注入图片到节点 {node_id}")
                    return True
        
        return False
    
    def execute(self, prompt: Dict = None) -> str:
        """执行工作流"""
        if prompt is None:
            prompt = self.template
        
        url = f"{self.api_url}/prompt"
        
        data = {
            "prompt": prompt
        }
        
        headers = {"Content-Type": "application/json"}
        if self.auth:
            headers["Authorization"] = f"Bearer {self.auth}"
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            self.last_prompt_id = result.get("prompt_id")
            logger.info(f"工作流已提交: {self.last_prompt_id}")
            return self.last_prompt_id
            
        except requests.RequestException as e:
            logger.error(f"工作流执行失败: {e}")
            raise
    
    def get_history(self, prompt_id: str = None) -> Dict:
        """获取执行历史"""
        prompt_id = prompt_id or self.last_prompt_id
        if not prompt_id:
            raise ValueError("请提供 prompt_id")
        
        url = f"{self.api_url}/history/{prompt_id}"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"获取历史失败: {e}")
            return {}
    
    def get_images(self, node_id: str, prompt_id: str = None) -> List[str]:
        """获取输出图片 (Base64)"""
        prompt_id = prompt_id or self.last_prompt_id
        if not prompt_id:
            raise ValueError("请提供 prompt_id")
        
        history = self.get_history(prompt_id)
        
        images = []
        if prompt_id in history:
            outputs = history[prompt_id].get("outputs", {})
            for node_id_str, node_output in outputs.items():
                if node_output.get("images"):
                    for img in node_output["images"]:
                        images.append(img)
        
        return images
    
    def download_image(self, node_id: str, output_path: str, prompt_id: str = None) -> str:
        """下载输出图片到文件"""
        images = self.get_images(node_id, prompt_id)
        
        if not images:
            raise ValueError("未找到输出图片")
        
        image_info = images[0]
        filename = image_info.get("filename")
        
        url = f"{self.api_url}/view"
        params = {"filename": filename}
        
        if image_info.get("subfolder"):
            params["subfolder"] = image_info["subfolder"]
        
        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"图片已保存: {output_path}")
            return output_path
            
        except requests.RequestException as e:
            logger.error(f"下载图片失败: {e}")
            raise
    
    def download_and_process_image(
        self, 
        node_id: str, 
        output_path: str, 
        prompt_id: str = None,
        process: bool = True,
        target_size: tuple = (1080, 1440),
        max_size_kb: int = 1024
    ) -> tuple[bool, str]:
        """
        下载并处理图片 (整合校验+裁剪+压缩)
        
        Args:
            node_id: 节点ID
            output_path: 输出路径
            prompt_id: 提示ID
            process: 是否处理图片
            target_size: 目标尺寸
            max_size_kb: 最大文件大小
        
        Returns:
            (success, message)
        """
        from .image_processor import process_and_verify_image
        
        temp_path = output_path + ".tmp"
        
        try:
            self.download_image(node_id, temp_path, prompt_id)
            
            if process:
                success, msg = process_and_verify_image(
                    temp_path,
                    output_path,
                    target_size=target_size,
                    max_size_kb=max_size_kb
                )
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return success, msg
            else:
                if temp_path != output_path:
                    os.rename(temp_path, output_path)
                return True, "ok"
                
        except Exception as e:
            logger.error(f"下载并处理图片失败: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False, str(e)
    
    def wait_for_completion(self, prompt_id: str = None, timeout: int = 300, interval: int = 2) -> bool:
        """等待工作流完成"""
        import time
        
        prompt_id = prompt_id or self.last_prompt_id
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            history = self.get_history(prompt_id)
            
            if prompt_id in history:
                status = history[prompt_id].get("status", {})
                if status.get("completed", False):
                    return True
                if status.get("errored", False):
                    logger.error(f"工作流执行出错: {status.get('message')}")
                    return False
            
            time.sleep(interval)
        
        logger.warning(f"等待超时: {timeout}秒")
        return False
    
    def execute_and_wait(self, prompt: Dict = None, timeout: int = 300) -> Dict:
        """执行并等待完成"""
        prompt_id = self.execute(prompt)
        
        if self.wait_for_completion(prompt_id, timeout):
            return self.get_history(prompt_id)
        
        return {}


class RunningHubWorkflow(ComfyUIWorkflow):
    """RunningHub 工作流 (兼容 ComfyUI API)"""
    
    def __init__(self, api_key: str = None):
        super().__init__()
        self.api_key = api_key or os.environ.get("RUNNINGHUB_API_KEY")
        self.base_url = "https://api.runninghub.com"
    
    def execute(self, workflow_id: str, params: Dict) -> Dict:
        """执行 RunningHub 工作流"""
        url = f"{self.base_url}/workflow/{workflow_id}/run"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "inputs": params
        }
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=120)
            response.raise_for_status()
            result = response.json()
            
            self.last_prompt_id = result.get("task_id")
            logger.info(f"RunningHub 任务已提交: {self.last_prompt_id}")
            return result
            
        except requests.RequestException as e:
            logger.error(f"RunningHub 执行失败: {e}")
            raise
    
    def get_task_status(self, task_id: str = None) -> Dict:
        """获取任务状态"""
        task_id = task_id or self.last_prompt_id
        if not task_id:
            raise ValueError("请提供 task_id")
        
        url = f"{self.base_url}/task/{task_id}"
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"获取任务状态失败: {e}")
            return {}


def execute_workflow(
    template_path: str,
    prompt: str = None,
    seed: int = -1,
    lora: str = None,
    output_path: str = None
) -> str:
    """便捷函数: 执行工作流并返回图片"""
    workflow = ComfyUIWorkflow()
    workflow.load_template(template_path)
    
    if prompt:
        workflow.inject_prompt("prompt", prompt)
    
    if seed > 0:
        workflow.inject_seed("ksampler", seed)
    
    if lora:
        workflow.inject_lora("lora_loader", lora)
    
    workflow.execute()
    
    if output_path:
        workflow.download_image("save_image", output_path)
        return output_path
    
    return workflow.get_images("save_image")[0]


def execute_runninghub_workflow(workflow_id: str, params: Dict) -> Dict:
    """便捷函数: 执行 RunningHub 工作流"""
    hub = RunningHubWorkflow()
    return hub.execute(workflow_id, params)
