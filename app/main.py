"""
FastAPI应用入口
"""

import os
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_coze_config
from .logging_config import get_coze_logger, configure_coze_logging as configure_logging, get_api_logger
from .error_handlers import register_error_handlers
from .routes import router
from .redis_client import get_coze_redis_client, reset_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger = get_coze_logger()
    logger.info("Starting Coze FastAPI application...")
    
    # 配置日志
    configure_logging()
    
    # 初始化配置
    get_coze_config()
    
    # 验证配置
    config = get_coze_config()
    logger.info(f"Coze module initialized with config: {config.api_url}")
    
    # 测试Redis连接
    try:
        redis_client = await get_coze_redis_client()
        await redis_client.redis_client.ping()
        logger.info("Coze Redis connection verified")
    except Exception as e:
        logger.warning(f"Coze Redis connection test failed: {e}")
    
    logger.info("Coze FastAPI application started successfully")
    
    yield
    
    # 关闭时
    logger.info("Shutting down Coze FastAPI application...")
    await reset_redis_client()
    logger.info("Coze FastAPI application shut down")


# 创建FastAPI应用
app = FastAPI(
    title="Coze API Service",
    description="Coze API service using FastAPI",
    version="1.0.0",
    lifespan=lifespan
)

# 注册CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def before_request(request: Request, call_next):
    """请求前处理"""
    # 生成请求ID
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # 创建请求专用日志记录器
    request.state.logger = get_api_logger(request.url.path, request_id)
    
    # 记录请求开始
    request.state.logger.info(
        f"Request started: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "remote_addr": request.client.host if request.client else None,
            "user_agent": request.headers.get('User-Agent', ''),
            "content_type": request.headers.get('Content-Type', '')
        }
    )
    
    response = await call_next(request)
    
    # 记录请求完成
    if hasattr(request.state, 'logger'):
        request.state.logger.info(
            f"Request completed: {response.status_code}",
            extra={
                "status_code": response.status_code,
            }
        )
    
    return response


# 注册路由
app.include_router(router)

# 注册错误处理器
register_error_handlers(app)


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "coze-fastapi",
        "version": "1.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    
    # 从环境变量获取端口，默认6000
    port = int(os.getenv("PORT", "6000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )

