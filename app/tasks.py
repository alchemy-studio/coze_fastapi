# -*- coding: utf-8 -*-
"""
Coze模块异步任务处理
将原来的Celery任务改为异步函数
"""

import time
import asyncio
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from .config import get_coze_config
from .logging_config import get_coze_logger
from .redis_client import get_coze_redis_client
from .models import (
    CozeSession, CozeChat, CozeMessage, CozeUser,
    SessionStatus, ChatStatus, MessageRole,
    create_coze_session, create_coze_chat
)
from .exceptions import (
    CozeAPIError, CozeNetworkError, CozeTimeoutError,
    CozeSessionError, CozeValidationError,
)
from .utils import (
    get_current_timestamp,
    safe_json_loads, safe_json_dumps,
    create_response_dict
)

# 获取配置和日志
config = get_coze_config()
logger = get_coze_logger()


# ==================== 会话管理任务 ====================

async def create_session_task(user_id: str, context: Optional[Dict[str, Any]] = None, 
                             metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    创建新的Coze会话（异步）
    
    Args:
        user_id: 用户ID
        context: 会话上下文
        metadata: 会话元数据
        
    Returns:
        包含会话信息的字典
    """
    try:
        logger.info(f"Creating new session for user: {user_id}")
        
        # 验证用户ID
        if not user_id or not isinstance(user_id, str):
            raise CozeValidationError("Invalid user ID provided")
        
        # 创建会话
        session = create_coze_session(
            user_id=user_id,
            context=context or {},
            metadata=metadata or {}
        )
        
        # 保存到Redis
        redis_client = await get_coze_redis_client()
        await redis_client.set_session(session.session_id, session.to_dict())
        
        # 更新用户信息
        user_data = await redis_client.get_value(f"user:{user_id}")
        if user_data:
            user = CozeUser.from_dict(safe_json_loads(user_data, {}))
        else:
            from .models import create_coze_user
            user = create_coze_user(user_id)
        
        user.add_session(session.session_id)
        await redis_client.set_value(f"user:{user_id}", safe_json_dumps(user.to_dict()))
        
        # 添加到活跃会话
        await redis_client.add_active_session(session.session_id)
        await redis_client.add_user_session(user_id, session.session_id)
        
        logger.info(f"Session created successfully: {session.session_id}")
        
        return create_response_dict(
            success=True,
            data=session.to_dict(),
            message="Session created successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to create session for user {user_id}: {str(e)}")
        raise


async def get_session_task(session_id: str) -> Dict[str, Any]:
    """
    获取会话信息（异步）
    
    Args:
        session_id: 会话ID
        
    Returns:
        包含会话信息的字典
    """
    try:
        logger.info(f"Retrieving session: {session_id}")
        
        # 从Redis获取会话数据
        redis_client = await get_coze_redis_client()
        session_data = await redis_client.get_session(session_id)
        if not session_data:
            raise CozeSessionError(f"Session not found: {session_id}")
        
        session = CozeSession.from_dict(session_data)
        
        # 检查会话是否过期
        if session.expires_at:
            expires_timestamp = datetime.fromisoformat(session.expires_at.replace('Z', '+00:00')).timestamp()
            if time.time() > expires_timestamp:
                session.status = SessionStatus.EXPIRED
                await redis_client.set_session(session_id, session.to_dict())
                logger.warning(f"Session {session_id} has expired")
        
        logger.info(f"Session retrieved successfully: {session_id}")
        
        return create_response_dict(
            success=True,
            data=session.to_dict(),
            message="Session retrieved successfully"
        )
        
    except CozeSessionError:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve session {session_id}: {str(e)}")
        raise


async def update_session_activity_task(session_id: str) -> Dict[str, Any]:
    """
    更新会话活动时间（异步）
    
    Args:
        session_id: 会话ID
        
    Returns:
        操作结果字典
    """
    try:
        logger.info(f"Updating session activity: {session_id}")
        
        redis_client = await get_coze_redis_client()
        session_data = await redis_client.get_session(session_id)
        if not session_data:
            raise CozeSessionError(f"Session not found: {session_id}")
        
        session = CozeSession.from_dict(session_data)
        session.update_activity()
        
        # 保存更新后的会话
        await redis_client.set_session(session_id, session.to_dict())
        
        # 延长会话过期时间
        await redis_client.extend_session(session_id, getattr(config, 'session_expire', 3600))
        
        logger.info(f"Session activity updated: {session_id}")
        
        return create_response_dict(
            success=True,
            message="Session activity updated successfully"
        )
        
    except CozeSessionError:
        raise
    except Exception as e:
        logger.error(f"Failed to update session activity {session_id}: {str(e)}")
        raise


async def terminate_session_task(session_id: str, reason: str = "User requested") -> Dict[str, Any]:
    """
    终止会话（异步）
    
    Args:
        session_id: 会话ID
        reason: 终止原因
        
    Returns:
        操作结果字典
    """
    try:
        logger.info(f"Terminating session: {session_id}, reason: {reason}")
        
        redis_client = await get_coze_redis_client()
        session_data = await redis_client.get_session(session_id)
        if not session_data:
            raise CozeSessionError(f"Session not found: {session_id}")
        
        session = CozeSession.from_dict(session_data)
        session.terminate(reason)
        
        # 保存更新后的会话
        await redis_client.set_session(session_id, session.to_dict())
        
        # 从活跃会话中移除
        await redis_client.remove_active_session(session_id)
        await redis_client.remove_user_session(session.user_id, session_id)
        
        logger.info(f"Session terminated: {session_id}")
        
        return create_response_dict(
            success=True,
            message="Session terminated successfully"
        )
        
    except CozeSessionError:
        raise
    except Exception as e:
        logger.error(f"Failed to terminate session {session_id}: {str(e)}")
        raise


# ==================== 消息处理任务 ====================

async def send_message_task(session_id: str, message_content: str, 
                           metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    发送消息到Coze API（异步）
    
    Args:
        session_id: 会话ID
        message_content: 消息内容
        metadata: 消息元数据
        
    Returns:
        包含聊天结果的字典
    """
    try:
        logger.info(f"Sending message to session: {session_id}")
        
        # 验证会话
        redis_client = await get_coze_redis_client()
        session_data = await redis_client.get_session(session_id)
        if not session_data:
            raise CozeSessionError(f"Session not found: {session_id}")
        
        session = CozeSession.from_dict(session_data)
        if not session.is_active():
            raise CozeSessionError(f"Session is not active: {session_id}")
        
        # 创建聊天记录
        chat = create_coze_chat(
            session_id=session_id,
            user_message_content=message_content,
            metadata=metadata or {}
        )
        
        if chat is None:
            raise CozeValidationError("Failed to create chat record")
        
        # 更新聊天状态为处理中
        chat.update_status(ChatStatus.PROCESSING)
        
        # 保存聊天记录
        await redis_client.set_chat_result(chat.chat_id, chat.to_dict())
        
        # 调用Coze API
        try:
            api_response = await call_coze_api(
                user_message_content=message_content,
                session_context=session.context or {},
                chat_id=chat.chat_id
            )
            
            # API响应已经通过call_coze_api中的set_api_result设置了完整数据
            # 这里只需要重新加载更新后的聊天数据
            updated_chat_data = await redis_client.get_chat_result(chat.chat_id)
            if updated_chat_data:
                chat = CozeChat.from_dict(updated_chat_data)
            
            logger.info(f"Message processed successfully for chat: {chat.chat_id}")
            
        except Exception as api_error:
            # API调用失败，更新聊天状态
            if chat is not None:
                chat.update_status(ChatStatus.FAILED)
                if hasattr(chat, 'metadata') and chat.metadata is not None:
                    chat.metadata['error'] = str(api_error)
                logger.error(f"Coze API call failed for chat {chat.chat_id}: {str(api_error)}")
                
                # 仍然保存失败的聊天记录
                await redis_client.set_chat_result(chat.chat_id, chat.to_dict())
            
            raise CozeAPIError(f"API call failed: {str(api_error)}")
        
        # 保存更新后的聊天记录
        await redis_client.set_chat_result(chat.chat_id, chat.to_dict())
        
        # 添加到会话历史
        session.add_chat(chat)
        session.update_activity()
        await redis_client.set_session(session_id, session.to_dict())
        
        # 更新用户聊天计数
        user_data = await redis_client.get_value(f"user:{session.user_id}")
        if user_data:
            user = CozeUser.from_dict(safe_json_loads(user_data, {}))
            user.add_chat()
            await redis_client.set_value(f"user:{session.user_id}", safe_json_dumps(user.to_dict()))
        
        return create_response_dict(
            success=True,
            data=chat.to_dict(),
            message="Message sent successfully"
        )
        
    except (CozeSessionError, CozeAPIError):
        raise
    except Exception as e:
        logger.error(f"Failed to send message to session {session_id}: {str(e)}")
        raise


async def get_chat_result_task(chat_id: str) -> Dict[str, Any]:
    """
    获取聊天结果（异步）
    
    Args:
        chat_id: 聊天ID
        
    Returns:
        包含聊天结果的字典
    """
    try:
        logger.info(f"Retrieving chat result: {chat_id}")
        
        redis_client = await get_coze_redis_client()
        chat_data = await redis_client.get_chat_result(chat_id)
        if not chat_data:
            raise CozeValidationError(f"Chat not found: {chat_id}")
        
        chat = CozeChat.from_dict(chat_data)
        
        logger.info(f"Chat result retrieved: {chat_id}, status: {chat.status.value}")
        
        return create_response_dict(
            success=True,
            data=chat.to_dict(),
            message="Chat result retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to retrieve chat result {chat_id}: {str(e)}")
        raise


# ==================== API调用任务 ====================

async def call_coze_api(user_message_content: str, session_context: Dict[str, Any], 
                       chat_id: str) -> Dict[str, Any]:
    """
    调用Coze API（异步）
    
    Args:
        user_message_content: 消息内容
        session_context: 会话上下文
        chat_id: 聊天ID
        
    Returns:
        API响应数据
    """
    try:
        logger.info(f"Calling Coze API for chat: {chat_id}")
        
        # 构建API请求
        api_url = config.api_url
        headers = {
            'Authorization': config.authorization,
            'Content-Type': 'application/json',
            'User-Agent': 'CozeModule/1.0.0'
        }
        
        payload = {
            'bot_id': config.bot_id,
            'user_id': session_context.get('user_id', 'anonymous'),
            'stream': False,
            'auto_save_history': True,
            'additional_messages': [
                {
                    'role': 'user',
                    'content': user_message_content,
                    'content_type': 'text',
                },
            ],
        }
        
        # 发送请求（使用httpx异步客户端）
        async with httpx.AsyncClient(timeout=config.timeout) as client:
            response = await client.post(
                api_url,
                headers=headers,
                json=payload
            )
            
            # 检查响应状态
            if response.status_code == 429:
                raise CozeAPIError("Rate limit exceeded", status_code=429)
            elif response.status_code >= 400:
                raise CozeAPIError(
                    f"API request failed with status {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
            
            # 解析响应
            api_data = response.json()
            
            if api_data.get('code') and api_data.get('code') != 0:
                raise CozeAPIError(f"API returned error: {api_data.get('msg', 'Unknown error')}")
            
            # v3 API返回chat_id和conversation_id，需要轮询获取结果
            data = api_data.get('data') or {}
            api_chat_id = data.get('id')
            conversation_id = data.get('conversation_id')
            
            if not api_chat_id or not conversation_id:
                raise CozeAPIError("No chat_id or conversation_id in API response")
            
            logger.info(f"Chat initiated successfully: {api_chat_id}, conversation: {conversation_id}")
            
            # 轮询获取结果
            result = await _poll_chat_result(api_chat_id, conversation_id)
            if not result:
                raise CozeAPIError("Failed to get chat result")
            
            # 更新聊天对象
            redis_client = await get_coze_redis_client()
            chat_data = await redis_client.get_chat_result(chat_id)
            if chat_data:
                chat = CozeChat.from_dict(chat_data)
                chat.set_api_result(
                    content=result.get('content', ''),
                    reasoning_content=result.get('reasoning_content', ''),
                    follow_up_questions=result.get('follow_up_questions', []),
                    metadata=result.get('metadata', {})
                )
                # 保存更新后的聊天数据
                await redis_client.set_chat_result(chat_id, chat.to_dict())
            
            return result
        
    except httpx.TimeoutException:
        raise CozeTimeoutError("API request timeout")
    except httpx.NetworkError:
        raise CozeNetworkError("Network connection error")
    except httpx.RequestError as e:
        raise CozeNetworkError(f"Request error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in call_coze_api: {str(e)}")
        raise CozeAPIError(f"Unexpected API error: {str(e)}")


async def _poll_chat_result(chat_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    轮询获取聊天结果（异步）
    
    Args:
        chat_id: 聊天ID
        conversation_id: 会话ID
        
    Returns:
        聊天结果或None
    """
    max_attempts = 60  # 最多轮询60次
    poll_interval = 2  # 每2秒轮询一次
    
    async with httpx.AsyncClient(timeout=config.timeout) as client:
        headers = {
            'Authorization': config.authorization,
            'Content-Type': 'application/json'
        }
        
        for attempt in range(max_attempts):
            try:
                # 获取聊天状态
                status_url = f"{config.base_url}/chat/retrieve?chat_id={chat_id}&conversation_id={conversation_id}"
                status_response = await client.get(status_url, headers=headers)
                
                if status_response.status_code != 200:
                    logger.warning(f"Status check failed: {status_response.status_code}")
                    await asyncio.sleep(poll_interval)
                    continue
                    
                status_data = status_response.json()
                status = status_data.get('data', {}).get('status')
                
                logger.info(f"Poll attempt {attempt + 1}: status = {status}")
                
                if status == 'completed':
                    # 获取消息列表 - 使用v3 API端点
                    messages_url = f"https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conversation_id}"
                    messages_response = await client.get(messages_url, headers=headers)
                    
                    logger.info(f"Messages API response status: {messages_response.status_code}")
                    
                    if messages_response.status_code == 200:
                        messages_data = messages_response.json()
                        logger.info(f"Messages response: {messages_data}")
                        
                        # v3 API响应格式: {"data": {"messages": [...]}}
                        data = messages_data.get('data', {})
                        # 处理data可能是列表的情况
                        if isinstance(data, list):
                            messages = data
                        elif isinstance(data, dict):
                            messages = data.get('messages', [])
                        else:
                            messages = []
                        
                        logger.info(f"Found {len(messages)} messages")
                        
                        # 解析消息，提取思考过程、回答和建议
                        assistant_content = ''
                        reasoning_content = ''
                        follow_up_questions = []
                        
                        for msg in messages:
                            if not msg:
                                continue
                                
                            msg_role = msg.get('role', '')
                            msg_type = msg.get('type', '')
                            msg_content = msg.get('content', '')
                            
                            logger.info(f"Processing message: role={msg_role}, type={msg_type}, content={msg_content[:50] if msg_content else 'None'}...")
                            
                            if msg_role == 'assistant':
                                if msg_type == 'answer':
                                    # 主要回答内容
                                    assistant_content = msg_content
                                    logger.info(f"Found assistant answer: {len(assistant_content)} chars")
                                elif msg_type == 'verbose':
                                    # 思考过程
                                    reasoning_content = msg_content
                                    logger.info(f"Found reasoning content: {len(reasoning_content)} chars")
                                elif msg_type == 'follow_up':
                                    # 建议问题
                                    if msg_content:
                                        follow_up_questions.append(msg_content)
                                    logger.info(f"Found follow-up question: {msg_content}")
                                else:
                                    # 如果没有明确的类型，但是assistant消息，可能是主要回答
                                    if not assistant_content and msg_content:
                                         assistant_content = msg_content
                                         logger.info(f"Found assistant content (no type): {len(assistant_content)} chars")
                        
                        if assistant_content:
                            result = {
                                'content': assistant_content,
                                'reasoning_content': reasoning_content,
                                'follow_up_questions': follow_up_questions,
                                'metadata': {
                                    'chat_id': chat_id,
                                    'conversation_id': conversation_id,
                                    'response_time': time.time(),
                                    'message_count': len(messages)
                                }
                            }
                            logger.info(f"Parsed result: content={len(assistant_content)} chars, reasoning={len(reasoning_content)} chars, questions={len(follow_up_questions)}")
                            return result
                        
                        logger.warning("No assistant answer found in completed chat")
                        return None
                    else:
                        logger.error(f"Failed to get messages: {messages_response.status_code} - {messages_response.text}")
                        
                elif status == 'failed':
                    logger.error(f"Chat failed: {chat_id}")
                    return None
                    
                # 继续轮询
                await asyncio.sleep(poll_interval)
                
            except Exception as e:
                logger.error(f"Error polling chat result: {str(e)}")
                await asyncio.sleep(poll_interval)
    
    logger.error(f"Polling timeout for chat: {chat_id}")
    return None


# ==================== 清理任务 ====================

async def cleanup_expired_sessions_task() -> Dict[str, Any]:
    """
    清理过期会话（异步）
    
    Returns:
        清理结果字典
    """
    try:
        logger.info("Starting expired sessions cleanup")
        
        redis_client = await get_coze_redis_client()
        active_sessions = await redis_client.get_active_sessions()
        expired_count = 0
        
        for session_id in active_sessions:
            try:
                session_data = await redis_client.get_session(session_id)
                if not session_data:
                    # 会话数据不存在，从活跃列表中移除
                    await redis_client.remove_active_session(session_id)
                    expired_count += 1
                    continue
                
                session = CozeSession.from_dict(session_data)
                
                # 检查是否过期
                if session and session.expires_at:
                    expires_timestamp = datetime.fromisoformat(session.expires_at.replace('Z', '+00:00')).timestamp()
                    if time.time() > expires_timestamp:
                        # 标记为过期并从活跃列表移除
                        session.status = SessionStatus.EXPIRED
                        await redis_client.set_session(session_id, session.to_dict())
                        await redis_client.remove_active_session(session_id)
                        if session.user_id:
                            await redis_client.remove_user_session(session.user_id, session_id)
                        expired_count += 1
                        logger.info(f"Expired session cleaned: {session_id}")
                        
            except Exception as e:
                logger.error(f"Error processing session {session_id} during cleanup: {str(e)}")
                continue
        
        logger.info(f"Expired sessions cleanup completed. Cleaned {expired_count} sessions")
        
        return create_response_dict(
            success=True,
            data={'expired_count': expired_count},
            message=f"Cleanup completed. {expired_count} expired sessions processed"
        )
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired sessions: {str(e)}")
        raise

