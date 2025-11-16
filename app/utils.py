# -*- coding: utf-8 -*-
"""
Coze模块工具函数
提供通用的工具函数和辅助方法
"""

import uuid
import time
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union, List

from .exceptions import CozeValidationError
from .logging_config import get_coze_logger


def generate_session_id() -> str:
    """
    生成唯一的会话ID
    
    Returns:
        str: 会话ID
    """
    timestamp = str(int(time.time() * 1000))
    random_part = str(uuid.uuid4()).replace('-', '')[:8]
    return f"coze_session_{timestamp}_{random_part}"


def generate_chat_id() -> str:
    """
    生成唯一的聊天ID
    
    Returns:
        str: 聊天ID
    """
    timestamp = str(int(time.time() * 1000))
    random_part = str(uuid.uuid4()).replace('-', '')[:8]
    return f"coze_chat_{timestamp}_{random_part}"


def generate_task_id() -> str:
    """
    生成唯一的任务ID
    
    Returns:
        str: 任务ID
    """
    return str(uuid.uuid4())


def get_current_timestamp() -> datetime:
    """
    获取当前UTC时间戳
    
    Returns:
        datetime: 当前时间
    """
    return datetime.now(timezone.utc)


def format_timestamp(dt: datetime) -> str:
    """
    格式化时间戳为ISO格式字符串
    
    Args:
        dt: 时间对象
    
    Returns:
        str: ISO格式时间字符串
    """
    return dt.isoformat()


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    解析ISO格式时间字符串
    
    Args:
        timestamp_str: ISO格式时间字符串
    
    Returns:
        datetime: 时间对象
    """
    try:
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except ValueError as e:
        raise CozeValidationError(
            message=f"Invalid timestamp format: {timestamp_str}",
            field="timestamp",
            value=timestamp_str
        ) from e


def safe_json_dumps(data: Any, default_value: str = "{}") -> str:
    """
    安全的JSON序列化
    
    Args:
        data: 要序列化的数据
        default_value: 序列化失败时的默认值
    
    Returns:
        str: JSON字符串
    """
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as e:
        logger = get_coze_logger()
        logger.warning(f"JSON serialization failed: {e}, using default value")
        return default_value


def safe_json_loads(json_str: str, default_value: Any = None) -> Any:
    """
    安全的JSON反序列化
    
    Args:
        json_str: JSON字符串
        default_value: 反序列化失败时的默认值
    
    Returns:
        Any: 反序列化后的数据
    """
    try:
        return json.loads(json_str)
    except (TypeError, ValueError, json.JSONDecodeError) as e:
        logger = get_coze_logger()
        logger.warning(f"JSON deserialization failed: {e}, using default value")
        return default_value


def validate_message(message: str, max_length: int = 4000) -> bool:
    """
    验证消息内容
    
    Args:
        message: 消息内容
        max_length: 最大长度
    
    Returns:
        bool: 验证是否通过
    
    Raises:
        CozeValidationError: 验证失败时抛出
    """
    if not isinstance(message, str):
        raise CozeValidationError(
            message="Message must be a string",
            field="message",
            value=type(message).__name__
        )
    
    if not message.strip():
        raise CozeValidationError(
            message="Message cannot be empty",
            field="message",
            value=message
        )
    
    if len(message) > max_length:
        raise CozeValidationError(
            message=f"Message length exceeds maximum {max_length} characters",
            field="message",
            value=len(message)
        )
    
    return True


def validate_session_id(session_id: str) -> bool:
    """
    验证会话ID格式
    
    Args:
        session_id: 会话ID
    
    Returns:
        bool: 验证是否通过
    
    Raises:
        CozeValidationError: 验证失败时抛出
    """
    if not isinstance(session_id, str):
        raise CozeValidationError(
            message="Session ID must be a string",
            field="session_id",
            value=type(session_id).__name__
        )
    
    if not session_id.strip():
        raise CozeValidationError(
            message="Session ID cannot be empty",
            field="session_id",
            value=session_id
        )
    
    if not session_id.startswith('coze_session_'):
        raise CozeValidationError(
            message="Invalid session ID format",
            field="session_id",
            value=session_id
        )
    
    return True


def validate_user_id(user_id: str) -> bool:
    """
    验证用户ID格式
    
    Args:
        user_id: 用户ID
    
    Returns:
        bool: 验证是否通过
    
    Raises:
        CozeValidationError: 验证失败时抛出
    """
    if not isinstance(user_id, str):
        raise CozeValidationError(
            message="User ID must be a string",
            field="user_id",
            value=type(user_id).__name__
        )
    
    if not user_id.strip():
        raise CozeValidationError(
            message="User ID cannot be empty",
            field="user_id",
            value=user_id
        )
    
    return True


def create_response_dict(success: bool, data: Any = None, error: Optional[str] = None, 
                        error_code: Optional[str] = None, message: Optional[str] = None) -> Dict[str, Any]:
    """
    创建标准的API响应字典
    
    Args:
        success: 是否成功
        data: 响应数据
        error: 错误信息
        error_code: 错误代码
        message: 消息
    
    Returns:
        Dict[str, Any]: 响应字典
    """
    response = {
        'success': success,
        'timestamp': format_timestamp(get_current_timestamp())
    }
    
    if success:
        response['data'] = data
        if message:
            response['message'] = message
    else:
        response['error'] = error or "Unknown error"
        if error_code:
            response['error_code'] = error_code
    
    return response


def mask_sensitive_data(data: Dict[str, Any], sensitive_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    遮蔽敏感数据
    
    Args:
        data: 原始数据字典
        sensitive_keys: 敏感字段列表
    
    Returns:
        Dict[str, Any]: 遮蔽后的数据字典
    """
    if sensitive_keys is None:
        sensitive_keys = ['authorization', 'token', 'password', 'secret', 'key']
    
    masked_data = data.copy()
    
    for key, value in masked_data.items():
        if any(sensitive_key.lower() in key.lower() for sensitive_key in sensitive_keys):
            if isinstance(value, str) and len(value) > 8:
                masked_data[key] = value[:4] + "***" + value[-4:]
            else:
                masked_data[key] = "***MASKED***"
    
    return masked_data


def calculate_hash(data: str, algorithm: str = 'sha256') -> str:
    """
    计算数据哈希值
    
    Args:
        data: 要计算哈希的数据
        algorithm: 哈希算法
    
    Returns:
        str: 哈希值
    """
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(data.encode('utf-8'))
    return hash_obj.hexdigest()


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 字节数
    
    Returns:
        str: 格式化后的大小字符串
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size_float = float(size_bytes)
    while size_float >= 1024 and i < len(size_names) - 1:
        size_float /= 1024.0
        i += 1
    
    return f"{size_float:.1f} {size_names[i]}"


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断字符串
    
    Args:
        text: 原始字符串
        max_length: 最大长度
        suffix: 截断后缀
    
    Returns:
        str: 截断后的字符串
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

