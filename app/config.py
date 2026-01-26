# -*- coding: utf-8 -*-
"""
Coze模块配置管理
"""

import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# 加载 .env 文件（支持从项目根目录或当前目录加载）
# 优先从项目根目录加载（app 目录的上一级）
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path, override=False)
# 也尝试从当前目录加载（容器内可能的工作目录）
load_dotenv(override=False)


@dataclass
class CozeConfig:
    """
    Coze模块配置类
    
    所有配置项都可以通过环境变量覆盖
    """
    
    # Coze API配置
    api_url: str = "https://api.coze.cn/v3/chat"
    base_url: str = "https://api.coze.cn/v3"
    authorization: str = ""
    bot_id: str = ""
    
    # 请求配置
    timeout: int = 30  # API请求超时时间，单位：秒
    max_retries: int = 3  # API请求失败时的最大重试次数，单位：次
    poll_interval: float = 1.0  # 轮询间隔时间，单位：秒
    
    # Redis配置
    redis_url: str = "redis://localhost:6379/0"
    redis_prefix: str = "coze:"
    session_expire: int = 3600  # 会话过期时间（秒）
    result_expire: int = 1800   # 结果过期时间（秒）
    
    # 数据保留策略配置
    max_active_users: int = 1000  # 最大保留活跃用户数（超过此数量时清理最久未活动的用户）
    max_sessions_per_user: int = 10  # 每个用户允许的最大并发会话数，单位：个
    max_total_sessions: int = 5000  # 最大总会话数（超过时清理最久未活动的会话）
    user_inactive_timeout: int = 7200  # 用户不活动超时时间（秒），超过此时间未活动的用户数据可被清理
    
    # 日志配置
    log_level: str = "INFO"
    log_format: str = "json"
    
    # 业务配置
    max_message_length: int = 4000  # 单条消息的最大长度限制，单位：字符
    
    # 认证配置
    enable_auth: bool = True  # 是否启用认证
    http_scheme: str = "https://"  # HTTP协议方案
    
    # Host配置（用于认证）
    alchemy_host: str = "alchemy-studio.cn"
    moicen_host: str = "moicen.com"
    huiwings_host: str = "huiwings.cn"
    local_host: str = "localhost"
    
    def __post_init__(self):
        """初始化后处理，从环境变量读取配置"""
        # 根据运行模式设置不同的URL
        mode = os.getenv("APP_MODE", "remote")
        if mode == "local":
            # 本地测试模式，使用本地URL
            default_api_url = "http://localhost:5000/coze/v3/chat"
            default_base_url = "http://localhost:5000/coze/v3"
        else:
            # 远程部署模式，使用线上URL
            default_api_url = self.api_url
            default_base_url = self.base_url
            
        self.api_url = os.getenv("COZE_API_URL", default_api_url)
        self.base_url = os.getenv("COZE_BASE_URL", default_base_url)
        
        # 从环境变量读取 token 和 bot_id，不再使用硬编码默认值
        coze_api_token = os.getenv("COZE_API_TOKEN")
        if not coze_api_token:
            raise ValueError(
                "COZE_API_TOKEN environment variable is required. "
                "Please set it in .env file or environment variables."
            )
        
        coze_bot_id = os.getenv("COZE_BOT_ID")
        if not coze_bot_id:
            raise ValueError(
                "COZE_BOT_ID environment variable is required. "
                "Please set it in .env file or environment variables."
            )
        
        # 构建 authorization header
        # 如果 COZE_AUTHORIZATION 已设置，直接使用；否则使用 COZE_API_TOKEN 构建
        coze_authorization = os.getenv("COZE_AUTHORIZATION")
        if coze_authorization:
            # 如果已经包含 Bearer 前缀，直接使用；否则添加 Bearer 前缀
            if not coze_authorization.startswith("Bearer "):
                self.authorization = f"Bearer {coze_authorization}"
            else:
                self.authorization = coze_authorization
        else:
            # 使用 COZE_API_TOKEN 构建，确保有 Bearer 前缀
            self.authorization = f"Bearer {coze_api_token}"
        self.bot_id = coze_bot_id
        
        self.timeout = int(os.getenv("COZE_TIMEOUT", str(self.timeout)))
        self.max_retries = int(os.getenv("COZE_MAX_RETRIES", str(self.max_retries)))
        self.poll_interval = float(os.getenv("COZE_POLL_INTERVAL", str(self.poll_interval)))
        
        # Redis配置
        self.redis_url = os.getenv("REDIS_URL", self.redis_url)
        self.redis_prefix = os.getenv("COZE_REDIS_PREFIX", self.redis_prefix)
        self.session_expire = int(os.getenv("COZE_SESSION_EXPIRE", str(self.session_expire)))
        self.result_expire = int(os.getenv("COZE_RESULT_EXPIRE", str(self.result_expire)))
        
        self.log_level = os.getenv("COZE_LOG_LEVEL", self.log_level)
        self.log_format = os.getenv("COZE_LOG_FORMAT", self.log_format)
        
        self.max_message_length = int(os.getenv("COZE_MAX_MESSAGE_LENGTH", str(self.max_message_length)))
        self.max_sessions_per_user = int(os.getenv("COZE_MAX_SESSIONS_PER_USER", str(self.max_sessions_per_user)))
        
        # 数据保留策略配置
        self.max_active_users = int(os.getenv("COZE_MAX_ACTIVE_USERS", str(self.max_active_users)))
        self.max_total_sessions = int(os.getenv("COZE_MAX_TOTAL_SESSIONS", str(self.max_total_sessions)))
        self.user_inactive_timeout = int(os.getenv("COZE_USER_INACTIVE_TIMEOUT", str(self.user_inactive_timeout)))
        
        # 认证配置
        self.enable_auth = os.getenv("ENABLE_AUTH", str(self.enable_auth)).lower() in ("true", "1", "yes")
        self.http_scheme = os.getenv("HTTP_SCHEME", self.http_scheme)
        
        # Host配置
        self.alchemy_host = os.getenv("ALCHEMY_HOST", self.alchemy_host)
        self.moicen_host = os.getenv("MOICEN_HOST", self.moicen_host)
        self.huiwings_host = os.getenv("HUIWINGS_HOST", self.huiwings_host)
        self.local_host = os.getenv("LOCAL_HOST", self.local_host)
    
    def validate(self) -> bool:
        """
        验证配置是否有效
        
        Returns:
            bool: 配置是否有效
        """
        if not self.authorization:
            raise ValueError("COZE_AUTHORIZATION is required")
        
        if not self.bot_id:
            raise ValueError("COZE_BOT_ID is required")
        
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        
        if self.poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        
        if self.session_expire <= 0:
            raise ValueError("session_expire must be positive")
        
        if self.result_expire <= 0:
            raise ValueError("result_expire must be positive")
        
        if self.max_message_length <= 0:
            raise ValueError("max_message_length must be positive")
        
        if self.max_sessions_per_user <= 0:
            raise ValueError("max_sessions_per_user must be positive")
        
        if self.max_active_users <= 0:
            raise ValueError("max_active_users must be positive")
        
        if self.max_total_sessions <= 0:
            raise ValueError("max_total_sessions must be positive")
        
        if self.user_inactive_timeout <= 0:
            raise ValueError("user_inactive_timeout must be positive")
        
        return True
    
    def to_dict(self) -> dict:
        """
        转换为字典格式
        
        Returns:
            dict: 配置字典
        """
        return {
            'api_url': self.api_url,
            'bot_id': self.bot_id,
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'poll_interval': self.poll_interval,
            'redis_prefix': self.redis_prefix,
            'session_expire': self.session_expire,
            'result_expire': self.result_expire,
            'log_level': self.log_level,
            'log_format': self.log_format,
            'max_message_length': self.max_message_length,
            'max_sessions_per_user': self.max_sessions_per_user,
            'max_active_users': self.max_active_users,
            'max_total_sessions': self.max_total_sessions,
            'user_inactive_timeout': self.user_inactive_timeout,
        }


# 全局配置实例
_config: Optional[CozeConfig] = None


def get_coze_config() -> CozeConfig:
    """
    获取Coze配置实例（单例模式）
    
    Returns:
        CozeConfig: 配置实例
    """
    global _config
    if _config is None:
        _config = CozeConfig()
        _config.validate()
    return _config


def reload_config() -> CozeConfig:
    """
    重新加载配置
    
    Returns:
        CozeConfig: 新的配置实例
    """
    global _config
    _config = None
    return get_coze_config()

