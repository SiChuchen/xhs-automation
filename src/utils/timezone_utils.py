"""
时区工具模块 - 统一管理系统时区配置
"""

import os
import json
import logging
from zoneinfo import ZoneInfo
from datetime import datetime, time
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

_config: Optional[Dict] = None
_tz: Optional[ZoneInfo] = None


def _load_config() -> Dict:
    """从配置文件加载系统配置"""
    global _config
    if _config is None:
        config_path = Path(__file__).parent.parent / "config" / "system_config.json"
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    _config = json.load(f)
                logger.info(f"已加载系统配置: {config_path}")
            except Exception as e:
                logger.warning(f"加载配置文件失败: {e}, 使用默认配置")
                _config = {"timezone": "Asia/Shanghai"}
        else:
            _config = {"timezone": "Asia/Shanghai"}
            logger.info("未找到配置文件，使用默认时区: Asia/Shanghai")
    return _config


def get_timezone() -> ZoneInfo:
    """获取配置的时区"""
    global _tz
    if _tz is None:
        config = _load_config()
        tz_name = config.get("timezone", "Asia/Shanghai")
        try:
            _tz = ZoneInfo(tz_name)
        except Exception:
            logger.warning(f"无效时区 {tz_name}，使用默认 Asia/Shanghai")
            _tz = ZoneInfo("Asia/Shanghai")
    return _tz


def now() -> datetime:
    """获取配置时区的当前时间"""
    return datetime.now(get_timezone())


def current_hour() -> int:
    """获取配置时区的当前小时"""
    return now().hour


def current_minute() -> int:
    """获取配置时区的当前分钟"""
    return now().minute


def is_in_time_range(start: str, end: str) -> bool:
    """
    判断当前时间是否在指定时间段内
    
    Args:
        start: 开始时间 "HH:MM"
        end: 结束时间 "HH:MM"
    
    Returns:
        是否在时间范围内
    """
    current = now().time()
    start_time = time.fromisoformat(start)
    end_time = time.fromisoformat(end)
    
    if start_time <= end_time:
        return start_time <= current < end_time
    else:
        return current >= start_time or current < end_time


def get_schedule_period() -> str:
    """
    获取当前所处的调度时段
    
    Returns:
        "night_prefill" | "daytime" | "evening_peak"
    """
    config = _load_config()
    schedule = config.get("schedule", {})
    
    if is_in_time_range(schedule.get("night_prefill", {}).get("start", "00:00"),
                        schedule.get("night_prefill", {}).get("end", "06:00")):
        return "night_prefill"
    elif is_in_time_range(schedule.get("evening_peak", {}).get("start", "18:00"),
                         schedule.get("evening_peak", {}).get("end", "22:00")):
        return "evening_peak"
    else:
        return "daytime"


def reload_config():
    """重新加载配置"""
    global _config, _tz
    _config = None
    _tz = None
    _load_config()
