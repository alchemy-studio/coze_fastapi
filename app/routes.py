"""Coze模块的FastAPI路由定义"""

from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from .logging_config import get_coze_logger
from .error_handlers import create_success_response, create_error_response
from .exceptions import CozeValidationError, CozeRedisError
from .models import CozeSession
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
        response_data = create_error_response(f"Service unhealthy: {str(e)}", 503)
        return JSONResponse(status_code=503, content=response_data)


@router.post('/sessions')
async def create_session(request: Request):
    """创建新的Coze会话"""
    # 验证认证
    await verify_request_header_host_token(request)
    try:
        try:
            data = await request.json()
        except Exception:
            response_data = create_error_response("Request body is required", 400)
            return JSONResponse(status_code=400, content=response_data)
        
        if not data:
            response_data = create_error_response("Request body is required", 400)
            return JSONResponse(status_code=400, content=response_data)
        
        user_id = data.get('user_id')
        bot_id = data.get('bot_id') or '7486362828392284194'  # 默认bot_id
        
        if not user_id:
            response_data = create_error_response("user_id is required", 400)
            return JSONResponse(status_code=400, content=response_data)
        
        # 可选参数
        additional_messages = data.get('additional_messages') or []
        auto_save_history = data.get('auto_save_history', True)
        meta_data = data.get('meta_data') or {}
        
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
            'task_result': result
        })
        
    except CozeValidationError as e:
        logger.error(f"Validation error in create_session: {e}")
        response_data = create_error_response(str(e), 400, error_code="COZE_VALIDATION_ERROR")
        return JSONResponse(status_code=400, content=response_data)
    except Exception as e:
        logger.error(f"Unexpected error in create_session: {e}")
        response_data = create_error_response(f"Internal server error: {str(e)}", 500)
        return JSONResponse(status_code=500, content=response_data)


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
            response_data = create_error_response(f"Session {session_id} not found", 404)
            return JSONResponse(status_code=404, content=response_data)
        
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
        response_data = create_error_response(f"Database error: {str(e)}", 500, error_code="COZE_REDIS_ERROR")
        return JSONResponse(status_code=500, content=response_data)
    except Exception as e:
        logger.error(f"Unexpected error in get_session: {e}")
        response_data = create_error_response(f"Internal server error: {str(e)}", 500)
        return JSONResponse(status_code=500, content=response_data)


@router.post('/sessions/{session_id}/messages')
async def send_message(
    request: Request,
    session_id: str
):
    """向会话发送消息"""
    # 验证认证
    await verify_request_header_host_token(request)
    try:
        try:
            data = await request.json()
        except Exception:
            response_data = create_error_response("Request body is required", 400)
            return JSONResponse(status_code=400, content=response_data)
        
        if not data:
            response_data = create_error_response("Request body is required", 400)
            return JSONResponse(status_code=400, content=response_data)
        
        message = data.get('message')
        if not message:
            response_data = create_error_response("message is required", 400)
            return JSONResponse(status_code=400, content=response_data)
        
        # 可选参数
        stream = data.get('stream', False)
        
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
            'task_result': result
        })
        
    except CozeValidationError as e:
        logger.error(f"Validation error in send_message: {e}")
        response_data = create_error_response(str(e), 400, error_code="COZE_VALIDATION_ERROR")
        return JSONResponse(status_code=400, content=response_data)
    except Exception as e:
        logger.error(f"Unexpected error in send_message: {e}")
        response_data = create_error_response(f"Internal server error: {str(e)}", 500)
        return JSONResponse(status_code=500, content=response_data)


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
            'task_result': result
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in get_chat_result: {e}")
        response_data = create_error_response(f"Internal server error: {str(e)}", 500)
        return JSONResponse(status_code=500, content=response_data)


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
        response_data = create_error_response(f"Internal server error: {str(e)}", 500)
        return JSONResponse(status_code=500, content=response_data)


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
            response_data = create_error_response(f"Session {session_id} not found", 404)
            return JSONResponse(status_code=404, content=response_data)
        
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
        response_data = create_error_response(f"Database error: {str(e)}", 500, error_code="COZE_REDIS_ERROR")
        return JSONResponse(status_code=500, content=response_data)
    except Exception as e:
        logger.error(f"Unexpected error in get_session_chats: {e}")
        response_data = create_error_response(f"Internal server error: {str(e)}", 500)
        return JSONResponse(status_code=500, content=response_data)


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
        response_data = create_error_response(f"Database error: {str(e)}", 500, error_code="COZE_REDIS_ERROR")
        return JSONResponse(status_code=500, content=response_data)
    except Exception as e:
        logger.error(f"Unexpected error in get_user_sessions: {e}")
        response_data = create_error_response(f"Internal server error: {str(e)}", 500)
        return JSONResponse(status_code=500, content=response_data)


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
        response_data = create_error_response(f"Internal server error: {str(e)}", 500)
        return JSONResponse(status_code=500, content=response_data)


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
        response_data = create_error_response(f"Database error: {str(e)}", 500, error_code="COZE_REDIS_ERROR")
        return JSONResponse(status_code=500, content=response_data)
    except Exception as e:
        logger.error(f"Unexpected error in get_stats: {e}")
        response_data = create_error_response(f"Internal server error: {str(e)}", 500)
        return JSONResponse(status_code=500, content=response_data)

