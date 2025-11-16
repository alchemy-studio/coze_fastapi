# -*- coding: utf-8 -*-
"""
Coze模块专用异常类
定义所有Coze相关的异常类型
"""

from typing import Optional, Dict, Any


class CozeBaseException(Exception):
    """
    Coze模块基础异常类
    所有Coze相关异常的基类
    """
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        初始化异常
        
        Args:
            message: 错误消息
            error_code: 错误代码
            details: 错误详情
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            Dict[str, Any]: 异常信息字典
        """
        return {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'details': self.details
        }


class CozeConfigError(CozeBaseException):
    """
    Coze配置错误
    当配置验证失败或配置缺失时抛出
    """
    pass


class CozeAPIError(CozeBaseException):
    """
    Coze API错误
    当API调用失败时抛出
    """
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict[str, Any]] = None, **kwargs):
        """
        初始化API错误
        
        Args:
            message: 错误消息
            status_code: HTTP状态码
            response_data: API响应数据
            **kwargs: 其他参数
        """
        super().__init__(message, **kwargs)
        self.status_code = status_code
        self.response_data = response_data or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            Dict[str, Any]: 异常信息字典
        """
        result = super().to_dict()
        result.update({
            'status_code': self.status_code,
            'response_data': self.response_data
        })
        return result


class CozeNetworkError(CozeBaseException):
    """
    Coze网络错误
    当网络连接失败或超时时抛出
    """
    pass


class CozeTimeoutError(CozeNetworkError):
    """
    Coze超时错误
    当请求超时时抛出
    """
    pass


class CozeSessionError(CozeBaseException):
    """
    Coze会话错误
    当会话操作失败时抛出
    """
    
    def __init__(self, message: str, session_id: Optional[str] = None, **kwargs):
        """
        初始化会话错误
        
        Args:
            message: 错误消息
            session_id: 会话ID
            **kwargs: 其他参数
        """
        super().__init__(message, **kwargs)
        self.session_id = session_id
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            Dict[str, Any]: 异常信息字典
        """
        result = super().to_dict()
        result['session_id'] = self.session_id
        return result


class CozeSessionNotFoundError(CozeSessionError):
    """
    Coze会话未找到错误
    当指定的会话不存在时抛出
    """
    pass


class CozeSessionExpiredError(CozeSessionError):
    """
    Coze会话过期错误
    当会话已过期时抛出
    """
    pass


class CozeRedisError(CozeBaseException):
    """
    Coze Redis错误
    当Redis操作失败时抛出
    """
    pass


class CozeValidationError(CozeBaseException):
    """
    Coze验证错误
    当数据验证失败时抛出
    """
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None, **kwargs):
        """
        初始化验证错误
        
        Args:
            message: 错误消息
            field: 验证失败的字段
            value: 验证失败的值
            **kwargs: 其他参数
        """
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            Dict[str, Any]: 异常信息字典
        """
        result = super().to_dict()
        result.update({
            'field': self.field,
            'value': str(self.value) if self.value is not None else None
        })
        return result


class CozeRateLimitError(CozeAPIError):
    """
    Coze速率限制错误
    当API调用超过速率限制时抛出
    """
    
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        """
        初始化速率限制错误
        
        Args:
            message: 错误消息
            retry_after: 重试等待时间（秒）
            **kwargs: 其他参数
        """
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            Dict[str, Any]: 异常信息字典
        """
        result = super().to_dict()
        result['retry_after'] = self.retry_after
        return result

