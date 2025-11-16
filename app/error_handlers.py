"""Coze模块专用错误处理机制（FastAPI版本）"""

import traceback
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from .logging_config import get_coze_logger, get_api_logger
from .exceptions import (
    CozeValidationError, CozeAPIError, CozeRedisError,
    CozeConfigError, CozeSessionError
)

logger = get_coze_logger()


def create_error_response(error_message: str, status_code: int = 400, 
                         error_code: Optional[str] = None,
                         task_id: Optional[str] = None,
                         details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """创建统一的错误响应格式"""
    response_data = {
        "success": False,
        "error": {
            "message": error_message,
            "code": error_code or f"COZE_ERROR_{status_code}",
        },
        "data": None,
        "task_id": task_id,
        "task_status": "failed" if task_id else None
    }
    
    if details:
        response_data["error"]["details"] = details
    
    return response_data


def create_success_response(data: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    """创建统一的成功响应格式"""
    return {
        'success': True,
        'data': data,
        'error': None
    }


async def handle_coze_validation_error(request: Request, exc: CozeValidationError):
    """处理Coze验证错误"""
    api_logger = get_api_logger(str(request.url))
    api_logger.error(f"Validation error: {exc}")
    
    response_data = create_error_response(
        error_message=str(exc),
        status_code=400,
        error_code="COZE_VALIDATION_ERROR",
        details=getattr(exc, 'details', None)
    )
    return JSONResponse(status_code=400, content=response_data)


async def handle_coze_api_error(request: Request, exc: CozeAPIError):
    """处理Coze API错误"""
    api_logger = get_api_logger(str(request.url))
    api_logger.error(f"API error: {exc}")
    
    status_code = getattr(exc, 'status_code', 500)
    response_data = create_error_response(
        error_message=str(exc),
        status_code=status_code,
        error_code="COZE_API_ERROR",
        details={
            "api_status_code": status_code,
            "api_response": getattr(exc, 'response_data', None)
        }
    )
    return JSONResponse(status_code=status_code, content=response_data)


async def handle_coze_redis_error(request: Request, exc: CozeRedisError):
    """处理Coze Redis错误"""
    api_logger = get_api_logger(str(request.url))
    api_logger.error(f"Redis error: {exc}")
    
    response_data = create_error_response(
        error_message="数据存储服务暂时不可用",
        status_code=503,
        error_code="COZE_REDIS_ERROR",
        details={
            "original_error": str(exc),
            "service": "redis"
        }
    )
    return JSONResponse(status_code=503, content=response_data)


async def handle_coze_config_error(request: Request, exc: CozeConfigError):
    """处理Coze配置错误"""
    api_logger = get_api_logger(str(request.url))
    api_logger.error(f"Config error: {exc}")
    
    response_data = create_error_response(
        error_message="服务配置错误",
        status_code=500,
        error_code="COZE_CONFIG_ERROR",
        details={
            "config_issue": str(exc)
        }
    )
    return JSONResponse(status_code=500, content=response_data)


async def handle_coze_session_error(request: Request, exc: CozeSessionError):
    """处理Coze会话错误"""
    api_logger = get_api_logger(str(request.url))
    api_logger.error(f"Session error: {exc}")
    
    response_data = create_error_response(
        error_message=str(exc),
        status_code=400,
        error_code="COZE_SESSION_ERROR",
        details={
            "session_id": getattr(exc, 'session_id', None)
        }
    )
    return JSONResponse(status_code=400, content=response_data)


async def handle_http_exception(request: Request, exc: HTTPException):
    """处理HTTP异常"""
    response_data = create_error_response(
        error_message=exc.detail or "HTTP错误",
        status_code=exc.status_code,
        error_code=f"HTTP_{exc.status_code}"
    )
    return JSONResponse(status_code=exc.status_code, content=response_data)


async def handle_generic_exception(request: Request, exc: Exception):
    """处理通用异常"""
    # 记录完整的错误堆栈
    api_logger = get_api_logger(str(request.url))
    api_logger.error(
        f"Unhandled exception in Coze module: {str(exc)}",
        extra={
            "exception_type": type(exc).__name__,
            "traceback": traceback.format_exc(),
            "request_path": str(request.url),
            "request_method": request.method
        }
    )
    
    # 在生产环境中隐藏详细错误信息
    import os
    debug_mode = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    
    if debug_mode:
        error_message = str(exc)
        details = {
            "exception_type": type(exc).__name__,
            "traceback": traceback.format_exc()
        }
    else:
        error_message = "服务器内部错误"
        details = None
    
    response_data = create_error_response(
        error_message=error_message,
        status_code=500,
        error_code="INTERNAL_SERVER_ERROR",
        details=details
    )
    return JSONResponse(status_code=500, content=response_data)


def register_error_handlers(app):
    """注册错误处理器到FastAPI应用"""
    app.add_exception_handler(CozeValidationError, handle_coze_validation_error)
    app.add_exception_handler(CozeAPIError, handle_coze_api_error)
    app.add_exception_handler(CozeRedisError, handle_coze_redis_error)
    app.add_exception_handler(CozeConfigError, handle_coze_config_error)
    app.add_exception_handler(CozeSessionError, handle_coze_session_error)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_generic_exception)
    
    logger.info("Coze error handlers registered successfully")

