# -*- coding: utf-8 -*-
"""
Coze模块专用Redis客户端（异步版本）
确保与ai-api原有数据完全隔离
"""

import redis.asyncio as redis
import json
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta

from .config import get_coze_config
from .exceptions import CozeRedisError
from .logging_config import get_coze_logger
from .utils import safe_json_dumps, safe_json_loads, get_current_timestamp, format_timestamp


class CozeRedisClient:
    """
    Coze专用Redis客户端（异步版本）
    使用独立的命名空间，确保数据隔离
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        初始化Redis客户端
        
        Args:
            redis_url: Redis连接URL
        """
        self.config = get_coze_config()
        self.logger = get_coze_logger()
        self.prefix = self.config.redis_prefix
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
    
    async def connect(self):
        """连接Redis"""
        try:
            self.redis_client = await redis.from_url(self.redis_url, decode_responses=True)
            # 测试连接
            await self.redis_client.ping()
            self.logger.info(f"Connected to Redis successfully with prefix: {self.prefix}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise CozeRedisError(f"Redis connection failed: {e}") from e
    
    async def disconnect(self):
        """断开Redis连接"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
    
    def _get_key(self, key: str) -> str:
        """
        获取带前缀的Redis键
        
        Args:
            key: 原始键名
        
        Returns:
            str: 带前缀的键名
        """
        return f"{self.prefix}{key}"
    
    def _log_operation(self, operation: str, key: str, success: bool = True, error: Optional[str] = None):
        """
        记录Redis操作日志
        
        Args:
            operation: 操作类型
            key: 键名
            success: 是否成功
            error: 错误信息
        """
        if success:
            self.logger.debug(f"Redis {operation}: {key}")
        else:
            self.logger.error(f"Redis {operation} failed for {key}: {error}")
    
    # 会话相关操作
    
    async def set_session(self, session_id: str, session_data: Dict[str, Any], expire: Optional[int] = None) -> bool:
        """
        设置会话数据
        
        Args:
            session_id: 会话ID
            session_data: 会话数据
            expire: 过期时间（秒），默认使用配置值
        
        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key(f"session:{session_id}")
            expire_time = expire or self.config.session_expire
            
            # 添加时间戳
            session_data['updated_at'] = format_timestamp(get_current_timestamp())
            
            # 序列化数据
            serialized_data = safe_json_dumps(session_data)
            
            # 设置数据和过期时间
            result = await self.redis_client.setex(key, expire_time, serialized_data)
            
            self._log_operation("SET_SESSION", session_id, True)
            return bool(result)
            
        except Exception as e:
            self._log_operation("SET_SESSION", session_id, False, str(e))
            raise CozeRedisError(f"Failed to set session {session_id}: {e}") from e
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话数据
        
        Args:
            session_id: 会话ID
        
        Returns:
            Optional[Dict[str, Any]]: 会话数据，不存在时返回None
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key(f"session:{session_id}")
            data = await self.redis_client.get(key)
            
            if data is None:
                self._log_operation("GET_SESSION", session_id, True)
                return None
            
            session_data = safe_json_loads(str(data), {})
            self._log_operation("GET_SESSION", session_id, True)
            return session_data
            
        except Exception as e:
            self._log_operation("GET_SESSION", session_id, False, str(e))
            raise CozeRedisError(f"Failed to get session {session_id}: {e}") from e
    
    async def delete_session(self, session_id: str) -> bool:
        """
        删除会话数据
        
        Args:
            session_id: 会话ID
        
        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key(f"session:{session_id}")
            result = await self.redis_client.delete(key)
            
            self._log_operation("DELETE_SESSION", session_id, True)
            return bool(result)
            
        except Exception as e:
            self._log_operation("DELETE_SESSION", session_id, False, str(e))
            raise CozeRedisError(f"Failed to delete session {session_id}: {e}") from e
    
    async def session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在
        
        Args:
            session_id: 会话ID
        
        Returns:
            bool: 会话是否存在
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key(f"session:{session_id}")
            result = await self.redis_client.exists(key)
            
            self._log_operation("EXISTS_SESSION", session_id, True)
            return bool(result)
            
        except Exception as e:
            self._log_operation("EXISTS_SESSION", session_id, False, str(e))
            raise CozeRedisError(f"Failed to check session existence {session_id}: {e}") from e
    
    async def extend_session(self, session_id: str, expire: Optional[int] = None) -> bool:
        """
        延长会话过期时间
        
        Args:
            session_id: 会话ID
            expire: 新的过期时间（秒），默认使用配置值
        
        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key(f"session:{session_id}")
            expire_time = expire or self.config.session_expire
            
            result = await self.redis_client.expire(key, expire_time)
            
            self._log_operation("EXTEND_SESSION", session_id, True)
            return bool(result)
            
        except Exception as e:
            self._log_operation("EXTEND_SESSION", session_id, False, str(e))
            raise CozeRedisError(f"Failed to extend session {session_id}: {e}") from e
    
    # 聊天结果相关操作
    
    async def set_chat_result(self, chat_id: str, result_data: Dict[str, Any], expire: Optional[int] = None) -> bool:
        """
        设置聊天结果数据
        
        Args:
            chat_id: 聊天ID
            result_data: 结果数据
            expire: 过期时间（秒），默认使用配置值
        
        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key(f"chat:{chat_id}")
            expire_time = expire or self.config.result_expire
            
            # 添加时间戳
            result_data['updated_at'] = format_timestamp(get_current_timestamp())
            
            # 序列化数据
            serialized_data = safe_json_dumps(result_data)
            
            # 设置数据和过期时间
            result = await self.redis_client.setex(key, expire_time, serialized_data)
            
            self._log_operation("SET_CHAT_RESULT", chat_id, True)
            return bool(result)
            
        except Exception as e:
            self._log_operation("SET_CHAT_RESULT", chat_id, False, str(e))
            raise CozeRedisError(f"Failed to set chat result {chat_id}: {e}") from e
    
    async def get_chat_result(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        获取聊天结果数据
        
        Args:
            chat_id: 聊天ID
        
        Returns:
            Optional[Dict[str, Any]]: 结果数据，不存在时返回None
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key(f"chat:{chat_id}")
            data = await self.redis_client.get(key)
            
            if data is None:
                self._log_operation("GET_CHAT_RESULT", chat_id, True)
                return None
            
            result_data = safe_json_loads(str(data), {})
            self._log_operation("GET_CHAT_RESULT", chat_id, True)
            return result_data
            
        except Exception as e:
            self._log_operation("GET_CHAT_RESULT", chat_id, False, str(e))
            raise CozeRedisError(f"Failed to get chat result {chat_id}: {e}") from e
    
    async def delete_chat_result(self, chat_id: str) -> bool:
        """
        删除聊天结果数据
        
        Args:
            chat_id: 聊天ID
        
        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key(f"chat:{chat_id}")
            result = await self.redis_client.delete(key)
            
            self._log_operation("DELETE_CHAT_RESULT", chat_id, True)
            return bool(result)
            
        except Exception as e:
            self._log_operation("DELETE_CHAT_RESULT", chat_id, False, str(e))
            raise CozeRedisError(f"Failed to delete chat result {chat_id}: {e}") from e
    
    # 用户会话管理
    
    async def add_user_session(self, user_id: str, session_id: str) -> bool:
        """
        添加用户会话关联
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
        
        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key(f"user_sessions:{user_id}")
            result = await self.redis_client.sadd(key, session_id)
            
            # 设置过期时间
            await self.redis_client.expire(key, self.config.session_expire)
            
            self._log_operation("ADD_USER_SESSION", f"{user_id}:{session_id}", True)
            return bool(result)
            
        except Exception as e:
            self._log_operation("ADD_USER_SESSION", f"{user_id}:{session_id}", False, str(e))
            raise CozeRedisError(f"Failed to add user session {user_id}:{session_id}: {e}") from e
    
    async def get_user_sessions(self, user_id: str) -> List[str]:
        """
        获取用户的所有会话
        
        Args:
            user_id: 用户ID
        
        Returns:
            List[str]: 会话ID列表
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key(f"user_sessions:{user_id}")
            sessions_set = await self.redis_client.smembers(key)
            
            self._log_operation("GET_USER_SESSIONS", user_id, True)
            if isinstance(sessions_set, set):
                return list(sessions_set)
            return []
            
        except Exception as e:
            self._log_operation("GET_USER_SESSIONS", user_id, False, str(e))
            raise CozeRedisError(f"Failed to get user sessions {user_id}: {e}") from e
    
    async def remove_user_session(self, user_id: str, session_id: str) -> bool:
        """
        移除用户会话关联
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
        
        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key(f"user_sessions:{user_id}")
            result = await self.redis_client.srem(key, session_id)
            
            self._log_operation("REMOVE_USER_SESSION", f"{user_id}:{session_id}", True)
            return bool(result)
            
        except Exception as e:
            self._log_operation("REMOVE_USER_SESSION", f"{user_id}:{session_id}", False, str(e))
            raise CozeRedisError(f"Failed to remove user session {user_id}:{session_id}: {e}") from e
    
    # 活跃会话管理
    
    async def add_active_session(self, session_id: str) -> bool:
        """
        添加活跃会话
        
        Args:
            session_id: 会话ID
        
        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key("active_sessions")
            result = await self.redis_client.sadd(key, session_id)
            
            # 设置过期时间
            await self.redis_client.expire(key, self.config.session_expire)
            
            self._log_operation("ADD_ACTIVE_SESSION", session_id, True)
            return bool(result)
            
        except Exception as e:
            self._log_operation("ADD_ACTIVE_SESSION", session_id, False, str(e))
            raise CozeRedisError(f"Failed to add active session {session_id}: {e}") from e
    
    async def remove_active_session(self, session_id: str) -> bool:
        """
        移除活跃会话
        
        Args:
            session_id: 会话ID
        
        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key("active_sessions")
            result = await self.redis_client.srem(key, session_id)
            
            self._log_operation("REMOVE_ACTIVE_SESSION", session_id, True)
            return bool(result)
            
        except Exception as e:
            self._log_operation("REMOVE_ACTIVE_SESSION", session_id, False, str(e))
            raise CozeRedisError(f"Failed to remove active session {session_id}: {e}") from e
    
    async def get_active_sessions(self) -> List[str]:
        """
        获取所有活跃会话
        
        Returns:
            List[str]: 活跃会话ID列表
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            key = self._get_key("active_sessions")
            sessions_set = await self.redis_client.smembers(key)
            
            self._log_operation("GET_ACTIVE_SESSIONS", "all", True)
            if isinstance(sessions_set, set):
                return list(sessions_set)
            return []
            
        except Exception as e:
            self._log_operation("GET_ACTIVE_SESSIONS", "all", False, str(e))
            raise CozeRedisError(f"Failed to get active sessions: {e}") from e
    
    # 通用操作
    
    async def set_value(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """
        设置键值对
        
        Args:
            key: 键名
            value: 值
            expire: 过期时间（秒）
        
        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            redis_key = self._get_key(key)
            serialized_value = safe_json_dumps(value)
            
            if expire:
                result = await self.redis_client.setex(redis_key, expire, serialized_value)
            else:
                result = await self.redis_client.set(redis_key, serialized_value)
            
            self._log_operation("SET_VALUE", key, True)
            return bool(result)
            
        except Exception as e:
            self._log_operation("SET_VALUE", key, False, str(e))
            raise CozeRedisError(f"Failed to set value {key}: {e}") from e
    
    async def get_value(self, key: str, default: Any = None) -> Any:
        """
        获取键值
        
        Args:
            key: 键名
            default: 默认值
        
        Returns:
            Any: 键值
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            redis_key = self._get_key(key)
            data = await self.redis_client.get(redis_key)
            
            if data is None:
                self._log_operation("GET_VALUE", key, True)
                return default
            
            value = safe_json_loads(str(data), default)
            self._log_operation("GET_VALUE", key, True)
            return value
            
        except Exception as e:
            self._log_operation("GET_VALUE", key, False, str(e))
            raise CozeRedisError(f"Failed to get value {key}: {e}") from e
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        获取Coze Redis使用统计
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            pattern = self._get_key("*")
            keys_result = await self.redis_client.keys(pattern)
            
            if isinstance(keys_result, list):
                all_keys_list = keys_result
            else:
                all_keys_list = []
            stats = {
                'total_keys': len(all_keys_list),
                'session_keys': len([k for k in all_keys_list if ':session:' in k]),
                'chat_keys': len([k for k in all_keys_list if ':chat:' in k]),
                'user_session_keys': len([k for k in all_keys_list if ':user_sessions:' in k]),
                'active_session_keys': len([k for k in all_keys_list if ':active_sessions' in k]),
                'other_keys': len([k for k in all_keys_list if not any(x in k for x in [':session:', ':chat:', ':user_sessions:', ':active_sessions'])]),
                'prefix': self.prefix
            }
            
            self.logger.info(f"Coze Redis stats: {stats}")
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get Coze Redis stats: {e}")
            raise CozeRedisError(f"Failed to get stats: {e}") from e


# 全局Redis客户端实例
_redis_client: Optional[CozeRedisClient] = None


async def get_coze_redis_client(redis_url: str = "redis://localhost:6379/0") -> CozeRedisClient:
    """
    获取Coze Redis客户端实例（单例模式）
    
    Args:
        redis_url: Redis连接URL
    
    Returns:
        CozeRedisClient: Redis客户端实例
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = CozeRedisClient(redis_url)
        await _redis_client.connect()
    return _redis_client


async def reset_redis_client() -> None:
    """
    重置Redis客户端实例
    """
    global _redis_client
    if _redis_client:
        await _redis_client.disconnect()
    _redis_client = None

