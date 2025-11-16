"""Coze模块的FastAPI路由定义"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from .logging_config import get_coze_logger
from .error_handlers import create_success_response, create_error_response
from .exceptions import (
    CozeValidationError, CozeAPIError, CozeRedisError,
    CozeConfigError
)
from .models import (
    CozeSession, CozeChat, CozeMessage, MessageRole,
    SessionStatus, ChatStatus
)
from .redis_client import get_coze_redis_client
from .tasks import (
    create_session_task, send_message_task,
    get_chat_result_task, update_session_activity_task,
    terminate_session_task, cleanup_expired_sessions_task
)
from .auth import verify_request_header_host_token

# 创建路由器
router = APIRouter(prefix="/coze", tags=["coze"])

# 全局日志记录器
logger = get_coze_logger()


# 请求模型
class CreateSessionRequest(BaseModel):
    user_id: str
    bot_id: Optional[str] = None
    additional_messages: Optional[list] = []
    auto_save_history: Optional[bool] = True
    meta_data: Optional[Dict[str, Any]] = {}


class SendMessageRequest(BaseModel):
    message: str
    stream: Optional[bool] = False


@router.get('/health')
async def health_check(request: Request):
    """健康检查接口"""
    # 验证认证（如果启用）
    try:
        await verify_request_header_host_token(request)
    except HTTPException:
        # 如果认证失败，仍然允许健康检查
        pass
    try:
        redis_client = await get_coze_redis_client()
        # 简单的Redis连接测试
        await redis_client.redis_client.ping()
        
        return create_success_response({
            'status': 'healthy',
            'service': 'coze-api',
            'redis': 'connected'
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@router.post('/sessions')
async def create_session(
    request: Request,
    request_data: CreateSessionRequest
):
    """创建新的Coze会话"""
    # 验证认证
    await verify_request_header_host_token(request)
    try:
        user_id = request_data.user_id
        bot_id = request_data.bot_id or '7486362828392284194'  # 使用默认bot_id
        
        # 可选参数
        additional_messages = request_data.additional_messages or []
        auto_save_history = request_data.auto_save_history
        meta_data = request_data.meta_data or {}
        
        # 直接调用任务函数
        result = await create_session_task(
            user_id=user_id,
            context={'bot_id': bot_id, 'additional_messages': additional_messages, 'auto_save_history': auto_save_history},
            metadata=meta_data
        )
        
        logger.info(f"Created session for user: {user_id}, bot: {bot_id}")
        
        return create_success_response({
            'task_id': None,
            'task_status': 'completed',
            'task_result': result.get('data', {})
        })
        
    except CozeValidationError as e:
        logger.error(f"Validation error in create_session: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in create_session: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get('/sessions/{session_id}')
async def get_session(
    request: Request,
    session_id: str
):
    """获取会话信息"""
    # 验证认证
    await verify_request_header_host_token(request)
    try:
        redis_client = await get_coze_redis_client()
        session_data = await redis_client.get_session(session_id)
        
        if not session_data:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # 更新会话活动时间
        await update_session_activity_task(session_id)
        
        return create_success_response({
            'session': session_data,
            'task_id': None,
            'task_status': 'completed',
            'task_result': session_data
        })
        
    except CozeRedisError as e:
        logger.error(f"Redis error in get_session: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_session: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post('/sessions/{session_id}/messages')
async def send_message(
    request: Request,
    session_id: str,
    request_data: SendMessageRequest
):
    """向会话发送消息"""
    # 验证认证
    await verify_request_header_host_token(request)
    try:
        message = request_data.message
        if not message:
            raise HTTPException(status_code=400, detail="message is required")
        
        # 可选参数
        stream = request_data.stream or False
        
        # 直接调用任务函数
        result = await send_message_task(
            session_id=session_id,
            message_content=message,
            metadata={'stream': stream}
        )
        
        logger.info(f"Sent message for session: {session_id}")
        
        return create_success_response({
            'task_id': None,
            'task_status': 'completed',
            'task_result': result.get('data', {})
        })
        
    except CozeValidationError as e:
        logger.error(f"Validation error in send_message: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in send_message: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get('/chats/{chat_id}/result')
async def get_chat_result(
    request: Request,
    chat_id: str
):
    """获取聊天结果"""
    # 验证认证
    await verify_request_header_host_token(request)
    try:
        # 直接调用任务函数
        result = await get_chat_result_task(chat_id)
        
        logger.info(f"Get chat result for chat: {chat_id}")
        
        return create_success_response({
            'task_id': None,
            'task_status': 'completed',
            'task_result': result.get('data', {})
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in get_chat_result: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete('/sessions/{session_id}')
async def terminate_session(
    request: Request,
    session_id: str
):
    """终止会话"""
    # 验证认证
    await verify_request_header_host_token(request)
    try:
        # 直接调用任务函数
        result = await terminate_session_task(session_id)
        
        logger.info(f"Terminate session: {session_id}")
        
        return create_success_response({
            'task_id': None,
            'task_status': 'completed',
            'task_result': result
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in terminate_session: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get('/sessions/{session_id}/chats')
async def get_session_chats(
    request: Request,
    session_id: str
):
    """获取会话的所有聊天记录"""
    # 验证认证
    await verify_request_header_host_token(request)
    try:
        redis_client = await get_coze_redis_client()
        
        # 检查会话是否存在
        if not await redis_client.session_exists(session_id):
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # 获取会话数据以获取聊天历史
        session_data = await redis_client.get_session(session_id)
        if session_data:
            session = CozeSession.from_dict(session_data)
            chats_list = [chat.to_dict() for chat in session.chat_history]
        else:
            chats_list = []
        
        # 更新会话活动时间
        await update_session_activity_task(session_id)
        
        return create_success_response({
            'session_id': session_id,
            'chats': chats_list,
            'count': len(chats_list),
            'task_id': None,
            'task_status': 'completed',
            'task_result': chats_list
        })
        
    except CozeRedisError as e:
        logger.error(f"Redis error in get_session_chats: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_session_chats: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get('/users/{user_id}/sessions')
async def get_user_sessions(
    request: Request,
    user_id: str
):
    """获取用户的所有会话"""
    # 验证认证
    await verify_request_header_host_token(request)
    try:
        redis_client = await get_coze_redis_client()
        
        # 获取用户会话
        sessions = await redis_client.get_user_sessions(user_id)
        
        return create_success_response({
            'user_id': user_id,
            'sessions': sessions,
            'count': len(sessions),
            'task_id': None,
            'task_status': 'completed',
            'task_result': sessions
        })
        
    except CozeRedisError as e:
        logger.error(f"Redis error in get_user_sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in get_user_sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post('/admin/cleanup')
async def cleanup_expired_sessions(
    request: Request
):
    """清理过期会话（管理员接口）"""
    # 验证认证
    await verify_request_header_host_token(request)
    try:
        # 直接调用任务函数
        result = await cleanup_expired_sessions_task()
        
        logger.info(f"Cleanup expired sessions completed")
        
        return create_success_response({
            'task_id': None,
            'task_status': 'completed',
            'task_result': result
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in cleanup_expired_sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get('/admin/stats')
async def get_stats(
    request: Request
):
    """获取Coze模块统计信息（管理员接口）"""
    # 验证认证
    await verify_request_header_host_token(request)
    try:
        redis_client = await get_coze_redis_client()
        stats = await redis_client.get_stats()
        
        return create_success_response({
            'stats': stats,
            'task_id': None,
            'task_status': 'completed',
            'task_result': stats
        })
        
    except CozeRedisError as e:
        logger.error(f"Redis error in get_stats: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in get_stats: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

