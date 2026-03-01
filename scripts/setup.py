#!/usr/bin/env python3
"""
XHS Automation Interactive Setup Wizard
Interactive configuration system for Xiaohongshu automation.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

try:
    import requests
except ImportError:
    print("Installing requests...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests


CONFIG_DIR = Path.home() / ".xhs-automation" / "config"
PROJECT_DIR = Path("/home/ubuntu/xhs-automation")

PRESET_ROLES = {
    "hot_topic_hunter": {
        "name": "热门话题捕手",
        "name_en": "Hot Topic Hunter",
        "description": "自动检测并发布热门话题内容",
        "trending_sources": ["weibo", "xiaohongshu"],
        "auto_publish": True,
        "target_keywords": {
            "primary": ["热门话题", "今日热点", "爆款", "热搜"],
            "trending": ["微博热搜", "小红书热门", "抖音热门", "B站热门"]
        }
    },
    "tech_share": {
        "name": "技术分享专家",
        "name_en": "Tech Share Expert",
        "description": "分享编程技巧和科技资讯",
        "trending_sources": ["weibo"],
        "auto_publish": True,
        "target_keywords": {
            "primary": ["编程技巧", "效率工具", "AI工具", "学习方法"],
            "trending": ["开源项目", "技术教程", "编程语言"]
        }
    },
    "lifestyle_influencer": {
        "name": "生活方式博主",
        "name_en": "Lifestyle Influencer",
        "description": "分享生活美学和日常好物",
        "trending_sources": ["xiaohongshu"],
        "auto_publish": False,
        "target_keywords": {
            "primary": ["生活方式", "好物推荐", "家居美化", "美食分享"],
            "trending": ["小红书热门", "种草", "打卡"]
        }
    }
}


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_step(step: int, total: int, title: str):
    print(f"\n[{step}/{total}] {title}")
    print("-" * 40)


def input_with_default(prompt: str, default: str = "") -> str:
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    return input(f"{prompt}: ").strip()


def input_yes_no(prompt: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    while True:
        user_input = input(f"{prompt} [{default_str}]: ").strip().lower()
        if not user_input:
            return default
        if user_input in ["y", "yes"]:
            return True
        if user_input in ["n", "no"]:
            return False
        print("请输入 y 或 n")


def select_option(options: list, prompt: str = "请选择") -> int:
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        try:
            choice = int(input(f"{prompt}: ").strip())
            if 1 <= choice <= len(options):
                return choice
            print(f"请输入 1-{len(options)} 之间的数字")
        except ValueError:
            print("请输入有效的数字")


def check_docker() -> bool:
    print("\n检查 Docker 环境...")
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"  ✓ Docker 已安装: {result.stdout.strip()}")
            
            result = subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                timeout=5
            )
            print(f"  ✓ Docker daemon 运行正常")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    print("  ✗ Docker 未安装或未运行")
    return False


def check_network() -> bool:
    print("\n检查网络连接...")
    test_urls = [
        ("https://docker.io", "Docker Hub"),
        ("https://api.minimax.chat", "MiniMax API"),
        ("https://www.xiaohongshu.com", "小红书"),
    ]
    
    for url, name in test_urls:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code < 500:
                print(f"  ✓ {name} 可访问")
            else:
                print(f"  ✗ {name} 返回错误: {response.status_code}")
        except Exception as e:
            print(f"  ✗ {name} 无法访问")
    
    return True


def check_mcp_container() -> bool:
    print("\n检查 MCP 容器状态...")
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=xiaohongshu-mcp", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.stdout.strip():
            print(f"  ✓ MCP 容器运行中: {result.stdout.strip()}")
            
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=xiaohongshu-mcp", "--format", "{{.Ports}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            print(f"  端口映射: {result.stdout.strip()}")
            return True
    except Exception:
        pass
    print("  ✗ MCP 容器未运行")
    return False


def start_mcp_container() -> bool:
    print("\n启动 MCP 容器...")
    mirror = "crpi-hocnvtkomt7w9v8t.cn-beijing.personal.cr.aliyuncs.com/xpzouying/xiaohongshu-mcp"
    
    cmd = f"""docker run -d --name xiaohongshu-mcp \\
  -p 18060:18060 \\
  -v ~/.xhs-cookies:/app/data \\
  {mirror}"""
    
    print(f"执行命令:\n{cmd}")
    
    if input_yes_no("确认启动 MCP 容器?", default=True):
        try:
            subprocess.run(cmd, shell=True, check=True)
            print("  ✓ MCP 容器已启动")
            return True
        except subprocess.CalledProcessError as e:
            print(f"  ✗ 启动失败: {e}")
            return False
    return False


def configure_mcp_login() -> dict:
    print_header("MCP 登录配置")
    print("请选择登录方式:")
    
    options = [
        "粘贴 cookies.json 内容 (推荐)",
        "使用登录工具获取 cookies",
        "跳过 (稍后手动配置)"
    ]
    
    choice = select_option(options)
    
    if choice == 1:
        return configure_mcp_paste_cookies()
    elif choice == 2:
        return configure_mcp_login_tool()
    else:
        print("跳过 MCP 登录配置")
        return {}


def configure_mcp_paste_cookies() -> dict:
    print("\n请粘贴 cookies.json 内容:")
    print("(粘贴完成后按 Ctrl+D 或输入空行结束)")
    print("-" * 40)
    
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "":
                break
            lines.append(line)
        except EOFError:
            break
    
    if not lines:
        print("未收到任何内容")
        return {}
    
    content = "\n".join(lines)
    
    try:
        data = json.loads(content)
        
        cookies_path = CONFIG_DIR / "cookies.json"
        cookies_path.parent.mkdir(parents=True, exist_ok=True)
        cookies_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        
        print(f"  ✓ cookies 已保存到: {cookies_path}")
        return {"method": "paste", "cookies_path": str(cookies_path)}
    except json.JSONDecodeError as e:
        print(f"  ✗ JSON 解析失败: {e}")
        return {}


def configure_mcp_login_tool() -> dict:
    print("\n使用登录工具获取 cookies...")
    print("步骤:")
    print("  1. 在浏览器中打开小红书登录")
    print("  2. 获取 cookies (可使用浏览器扩展)")
    print("  3. 保存为 cookies.json 到配置目录")
    
    cookies_path = CONFIG_DIR / "cookies.json"
    cookies_path.parent.mkdir(parents=True, exist_ok=True)
    
    if cookies_path.exists():
        if input_yes_no("cookies.json 已存在，是否重新配置?", default=False):
            pass
        else:
            return {"method": "login_tool", "cookies_path": str(cookies_path)}
    
    print(f"\n请将 cookies.json 保存到: {cookies_path}")
    input("\n保存完成后按回车继续...")
    
    if cookies_path.exists():
        print("  ✓ cookies.json 已就绪")
        return {"method": "login_tool", "cookies_path": str(cookies_path)}
    else:
        print("  ✗ cookies.json 不存在")
        return {}


def configure_llm() -> dict:
    print_header("LLM 配置")
    
    print("\n选择 LLM 提供商:")
    provider_options = ["MiniMax (推荐)", "DeepSeek", "OpenAI", "跳过 (稍后配置)"]
    choice = select_option(provider_options)
    
    provider_configs = {
        1: {
            "provider": "minimax",
            "model": "MiniMax-M2.5",
            "base_url": "https://api.minimax.chat/v1",
            "temperature": 0.8,
            "max_tokens": 1000
        },
        2: {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "temperature": 0.8,
            "max_tokens": 1000
        },
        3: {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
            "temperature": 0.8,
            "max_tokens": 1000
        }
    }
    
    if choice == 4:
        return {}
    
    config = provider_configs[choice]
    
    print(f"\n请输入 {config['provider']} 的 API Key:")
    api_key = input("API Key: ").strip()
    
    if not api_key:
        print("  ✗ API Key 不能为空，跳过 LLM 配置")
        return {}
    
    config["api_key"] = api_key
    
    print("\n高级配置 (可选，直接回车使用默认值):")
    config["temperature"] = float(input_with_default("Temperature", str(config["temperature"])))
    config["max_tokens"] = int(input_with_default("Max Tokens", str(config["max_tokens"])))
    
    if input_yes_no("\n是否测试 LLM 连接?", default=True):
        if test_llm_connection(config):
            print(f"  ✓ LLM 连接测试成功!")
        else:
            print("  ✗ LLM 连接测试失败，请检查 API Key")
            if not input_yes_no("是否继续保存配置?", default=False):
                return {}
    
    print(f"\n  ✓ {config['provider']} 配置完成")
    return config


def test_llm_connection(config: dict) -> bool:
    """测试 LLM 连接"""
    try:
        import requests
        
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": config["model"],
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 10
        }
        
        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        return response.status_code == 200
    except Exception as e:
        print(f"  测试失败: {e}")
        return False


def configure_image_generation() -> dict:
    print_header("文生图配置")
    
    print("选择图片生成服务:")
    options = [
        "RunningHub (推荐，免费额度)",
        "DALL-E (OpenAI)",
        "跳过 (稍后配置)"
    ]
    choice = select_option(options)
    
    if choice == 3:
        return {}
    
    config = {"enabled": True, "provider": ""}
    
    if choice == 1:
        config["provider"] = "runninghub"
        print("\n请输入 RunningHub API Key:")
        api_key = input("API Key: ").strip()
        
        if not api_key:
            print("  ✗ API Key 不能为空，跳过配置")
            return {"enabled": False}
        
        config["api_key"] = api_key
        config["base_url"] = "https://www.runninghub.cn"
        config["default_style"] = input_with_default("默认风格", "真实摄影")
        config["default_size"] = input_with_default("默认尺寸 (1024x1024/768x1024/1024x768)", "1024x1024")
        
    elif choice == 2:
        config["provider"] = "dalle"
        print("\n请输入 OpenAI API Key:")
        api_key = input("API Key: ").strip()
        
        if not api_key:
            print("  ✗ API Key 不能为空，跳过配置")
            return {"enabled": False}
        
        config["api_key"] = api_key
        config["model"] = "dall-e-3"
        config["size"] = "1024x1024"
    
    print(f"\n  ✓ {config['provider']} 图片生成配置完成")
    return config


def generate_role_with_llm(llm_config: dict, image_config: dict) -> dict:
    """使用 LLM 生成角色设定"""
    print_header("AI 智能生成角色")
    print("描述你想要的角色，AI 会帮你生成详细设定")
    print("(输入 '退出' 结束对话生成)\n")
    
    system_prompt = """你是一个小红书运营助手，帮助用户创建角色设定。
根据用户的描述，生成一个完整的角色配置，包含：
- name: 中文名称
- name_en: 英文名称  
- description: 角色描述
- trending_sources: 趋势来源 (weibo/xiaohongshu)
- auto_publish: 是否自动发布 (true/false)
- target_keywords: 目标关键词 {primary: [], trending: []}

请用JSON格式输出，不要其他内容。"""

    conversation_history = [
        {"role": "system", "content": system_prompt}
    ]
    
    while True:
        user_input = input("\n请描述你想要的角色形象: ").strip()
        
        if not user_input:
            continue
        if user_input in ["退出", "exit", "q"]:
            print("已退出AI生成模式")
            return {}
        
        conversation_history.append({"role": "user", "content": user_input})
        
        print("\nAI 正在生成...")
        response = call_llm(llm_config, conversation_history)
        
        if not response:
            print("生成失败，请重试或输入 '退出' 结束")
            continue
        
        conversation_history.append({"role": "assistant", "content": response})
        
        try:
            role_config = parse_llm_response(response)
            if role_config:
                print("\n" + "=" * 40)
                print("生成的角色设定:")
                print("=" * 40)
                print(f"  名称: {role_config.get('name', '')}")
                print(f"  英文名: {role_config.get('name_en', '')}")
                print(f"  描述: {role_config.get('description', '')}")
                print(f"  趋势来源: {', '.join(role_config.get('trending_sources', []))}")
                print(f"  自动发布: {'是' if role_config.get('auto_publish') else '否'}")
                print(f"  关键词: {role_config.get('target_keywords', {})}")
                print("=" * 40)
                
                if input_yes_no("\n是否满意?", default=True):
                    role_config["type"] = "ai_generated"
                    return role_config
                else:
                    print("\n请描述需要修改的地方，AI 会帮你调整:")
        except Exception as e:
            print(f"解析失败: {e}")
            if not input_yes_no("是否重试?", default=True):
                return {}


def call_llm(config: dict, messages: list) -> str:
    """调用 LLM API"""
    try:
        import requests
        
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": config["model"],
            "messages": messages,
            "temperature": config.get("temperature", 0.8),
            "max_tokens": config.get("max_tokens", 1000)
        }
        
        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            print(f"API错误: {response.status_code}")
            return ""
    except Exception as e:
        print(f"调用失败: {e}")
        return ""


def parse_llm_response(text: str) -> dict:
    """解析 LLM 返回的 JSON"""
    import re
    
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        return json.loads(json_match.group())
    return {}


def configure_role(llm_config: dict = None, image_config: dict = None) -> dict:
    print_header("角色配置")
    print("选择角色配置方式:")
    
    options = ["选择预设角色", "AI 智能生成角色", "手动创建自定义角色", "稍后配置"]
    
    if llm_config and llm_config.get("api_key"):
        options.insert(2, "AI 智能生成角色")
    
    choice = select_option(options)
    
    if choice == 1:
        return select_preset_role()
    elif choice == 2 and llm_config:
        return generate_role_with_llm(llm_config, image_config)
    elif choice == 3 or (choice == 2 and not llm_config):
        return create_custom_role()
    else:
        return {}


def select_preset_role() -> dict:
    print("\n选择预设角色:")
    
    role_list = list(PRESET_ROLES.items())
    for i, (key, role) in enumerate(role_list, 1):
        print(f"  {i}. {role['name']} ({role['name_en']})")
        print(f"     {role['description']}")
    
    choice = select_option(role_list)
    
    key, role = role_list[choice - 1]
    print(f"\n已选择: {role['name']}")
    
    return {
        "type": "preset",
        "key": key,
        "name": role["name"],
        "name_en": role["name_en"],
        "description": role["description"],
        "trending_sources": role["trending_sources"],
        "auto_publish": role["auto_publish"],
        "target_keywords": role["target_keywords"]
    }


def create_custom_role() -> dict:
    print("\n创建自定义角色:")
    
    name = input_with_default("角色名称 (中文)", "我的自动化助手")
    name_en = input_with_default("角色名称 (英文)", "My Automation Bot")
    description = input_with_default("角色描述", "自动发布内容")
    
    print("\n选择趋势来源:")
    source_options = ["微博", "小红书", "微博+小红书"]
    source_choice = select_option(source_options)
    
    trending_sources = {
        1: ["weibo"],
        2: ["xiaohongshu"],
        3: ["weibo", "xiaohongshu"]
    }[source_choice]
    
    print("\n是否启用自动发布?")
    auto_publish = input_yes_no("auto_publish", default=False)
    
    print("\n设置目标关键词 (用逗号分隔):")
    primary_kw = input_with_default("主要关键词", "热门话题,今日热点")
    primary_keywords = [k.strip() for k in primary_kw.split(",") if k.strip()]
    
    print("设置趋势关键词 (用逗号分隔):")
    trending_kw = input_with_default("趋势关键词", "微博热搜,小红书热门")
    trending_keywords = [k.strip() for k in trending_kw.split(",") if k.strip()]
    
    return {
        "type": "custom",
        "name": name,
        "name_en": name_en,
        "description": description,
        "trending_sources": trending_sources,
        "auto_publish": auto_publish,
        "target_keywords": {
            "primary": primary_keywords,
            "trending": trending_keywords
        }
    }


def configure_auto_interact() -> dict:
    print_header("自动互动配置")
    
    enabled = input_yes_no("是否启用自动互动功能?", default=True)
    
    if not enabled:
        return {"enabled": False}
    
    config = {
        "enabled": True,
        "daily_comment_limit": int(input_with_default("每日评论上限", "15")),
        "daily_like_limit": int(input_with_default("每日点赞上限", "20")),
        "daily_collect_limit": int(input_with_default("每日收藏上限", "10")),
        "min_interval_seconds": int(input_with_default("最小间隔(秒)", "5")),
        "max_interval_seconds": int(input_with_default("最大间隔(秒)", "15")),
    }
    
    print("\n设置主要关键词 (用逗号分隔):")
    primary_kw = input_with_default("主要关键词", "编程技巧,效率工具,AI工具,学习方法")
    config["target_keywords"] = {
        "primary": [k.strip() for k in primary_kw.split(",") if k.strip()],
        "trending": []
    }
    
    print("\n设置趋势关键词 (用逗号分隔):")
    trending_kw = input_with_default("趋势关键词", "开学,实习,春招,秋招")
    config["target_keywords"]["trending"] = [k.strip() for k in trending_kw.split(",") if k.strip()]
    
    print("\n评论模板 (用逗号分隔):")
    templates_input = input_with_default(
        "评论模板",
        "学到了！感谢分享~,太强了，收藏了！,这个真的有用，点赞👍"
    )
    config["comment_templates"] = [t.strip() for t in templates_input.split(",") if t.strip()]
    
    use_llm_comment = input_yes_no("是否使用 LLM 生成评论?", default=True)
    config["comment_llm_enabled"] = use_llm_comment
    
    print("\n  ✓ 自动互动配置完成")
    return config


def configure_trending() -> dict:
    print_header("趋势话题配置")
    
    print("\n选择趋势来源:")
    source_options = ["微博 + 小红书", "仅微博", "仅小红书", "跳过"]
    choice = select_option(source_options)
    
    sources = {
        1: ["weibo", "xiaohongshu"],
        2: ["weibo"],
        3: ["xiaohongshu"],
        4: []
    }[choice]
    
    if not sources:
        return {"enabled": False}
    
    config = {
        "enabled": True,
        "sources": sources,
        "fetch_interval_minutes": int(input_with_default("获取间隔(分钟)", "30")),
        "max_topics": int(input_with_default("每次获取话题数", "10")),
    }
    
    return config


def save_config(configs: dict):
    print_header("保存配置")
    
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"配置目录: {CONFIG_DIR}")
    
    config_files = {
        "mcp": "mcp_config.json",
        "llm": "llm_config.json",
        "image": "image_config.json",
        "role": "role_config.json",
        "auto_interact": "auto_interact_config.json",
        "trending": "trending_config.json"
    }
    
    for key, filename in config_files.items():
        if configs.get(key):
            filepath = CONFIG_DIR / filename
            filepath.write_text(
                json.dumps(configs[key], indent=2, ensure_ascii=False)
            )
            print(f"  ✓ 已保存: {filename}")
    
    config_index = CONFIG_DIR / "config.json"
    config_index.write_text(json.dumps({
        "version": "1.0",
        "config_dir": str(CONFIG_DIR),
        "project_dir": str(PROJECT_DIR)
    }, indent=2))
    print(f"  ✓ 已保存: config.json")
    
    print(f"\n所有配置已保存到: {CONFIG_DIR}")


def create_symlink():
    if PROJECT_DIR.exists():
        link_path = PROJECT_DIR / "config" / "user_config"
        if link_path.is_symlink() or link_path.exists():
            return
        
        if input_yes_no(f"\n是否创建配置软链接到项目目录?", default=True):
            try:
                link_path.symlink_to(CONFIG_DIR)
                print(f"  ✓ 已创建软链接: {link_path} -> {CONFIG_DIR}")
            except Exception as e:
                print(f"  ✗ 创建软链接失败: {e}")


def print_summary(configs: dict):
    print_header("配置完成!")
    
    print("\n📋 配置摘要:")
    print("-" * 40)
    
    if configs.get("mcp"):
        print(f"  MCP: {configs['mcp'].get('method', 'unknown')}")
    else:
        print("  MCP: 未配置")
    
    if configs.get("llm"):
        llm = configs["llm"]
        print(f"  LLM: {llm.get('provider', 'Unknown')} - {llm.get('model', '')}")
    
    if configs.get("image"):
        img = configs["image"]
        if img.get("enabled"):
            print(f"  文生图: {img.get('provider', 'Unknown')}")
    
    if configs.get("role"):
        role = configs["role"]
        print(f"  角色: {role.get('name', 'Unknown')} ({role.get('name_en', '')})")
    
    if configs.get("auto_interact"):
        ai = configs["auto_interact"]
        status = "启用" if ai.get("enabled") else "禁用"
        print(f"  自动互动: {status}")
    
    if configs.get("trending"):
        td = configs["trending"]
        if td.get("enabled"):
            print(f"  趋势话题: {', '.join(td.get('sources', []))}")
    
    print("\n📁 配置目录:", CONFIG_DIR)
    print("\n🚀 下一步:")
    print("  1. 运行 MCP 容器: docker start xiaohongshu-mcp")
    print("  2. 测试配置: python main.py status")
    print("  3. 启动自动任务: python scripts/auto_interact_task.py")


def main():
    print_header("XHS Automation 配置向导")
    print("欢迎使用小红书自动化配置向导!")
    print("本向导将帮助您完成环境检测、MCP配置、角色设置等")
    
    if input_yes_no("\n是否开始配置?", default=True) is False:
        print("已退出配置")
        return
    
    configs = {}
    total_steps = 7
    current_step = 0
    
    current_step += 1
    print_step(current_step, total_steps, "环境检测")
    check_docker()
    check_network()
    check_mcp_container()
    
    if not check_mcp_container():
        if input_yes_no("是否启动 MCP 容器?", default=True):
            start_mcp_container()
    
    current_step += 1
    print_step(current_step, total_steps, "MCP 登录配置")
    configs["mcp"] = configure_mcp_login()
    
    current_step += 1
    print_step(current_step, total_steps, "LLM 配置")
    configs["llm"] = configure_llm()
    
    current_step += 1
    print_step(current_step, total_steps, "文生图配置")
    configs["image"] = configure_image_generation()
    
    current_step += 1
    print_step(current_step, total_steps, "角色配置")
    configs["role"] = configure_role(configs.get("llm"), configs.get("image"))
    
    current_step += 1
    print_step(current_step, total_steps, "自动互动配置")
    configs["auto_interact"] = configure_auto_interact()
    
    current_step += 1
    print_step(current_step, total_steps, "趋势话题配置")
    configs["trending"] = configure_trending()
    
    save_config(configs)
    create_symlink()
    print_summary(configs)


if __name__ == "__main__":
    main()
