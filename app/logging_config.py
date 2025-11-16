"""Coze模块日志配置"""

import os
import sys
from pathlib import Path
from loguru import logger
from typing import Optional, Dict, Any

from .config import get_coze_config


class CozeLogger:
    """Coze模块专用日志管理器"""
    
    def __init__(self):
        self.config = get_coze_config()
        self.logger = logger
        self._configured = False
        self._log_dir: Optional[Path] = None
    
    def configure(self, log_dir: Optional[str] = None) -> None:
        """配置日志系统
        
        Args:
            log_dir: 日志目录路径，如果为None则使用默认路径
        """
        if self._configured:
            return
        
        # 设置日志目录
        if log_dir:
            self._log_dir = Path(log_dir)
        else:
            # 默认在项目根目录下创建logs目录（统一日志目录）
            project_root = Path(__file__).parent.parent
            self._log_dir = project_root / "logs"
        
        # 确保日志目录存在
        self._log_dir.mkdir(parents=True, exist_ok=True)
        
        # 不要移除默认处理器，避免影响主应用日志
        # self.logger.remove()  # 注释掉，保留主应用的日志处理器
        
        # 获取项目根目录路径
        project_root = Path(__file__).parent.parent
        
        # 添加控制台处理器
        self._add_console_handler()
        
        # 添加文件处理器
        self._add_file_handlers()
        
        self._configured = True
        
        # 记录配置完成
        unified_log_file = self._log_dir / "coze-fastapi.log"
        self.logger.info(f"Coze logger configured, unified log file: {unified_log_file}")
    
    def _add_console_handler(self) -> None:
        """添加控制台日志处理器"""
        console_format = (
            "<green>{time}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>coze</cyan> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
        
        self.logger.add(
            sys.stdout,
            format=console_format,
            level=self.config.log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
            filter=self._coze_filter
        )
    
    def _add_file_handlers(self) -> None:
        """添加文件日志处理器"""
        if self._log_dir is None:
            raise RuntimeError("Log directory not configured")
            
        file_format = (
            "{time} | "
            "{level: <8} | "
            "coze | "
            "{name}:{function}:{line} - "
            "{message}"
        )
        
        # 统一日志文件（所有日志集中在一个文件）
        unified_log_file = self._log_dir / "coze-fastapi.log"
        self.logger.add(
            unified_log_file,
            format=file_format,
            level=self.config.log_level,
            rotation="50 MB",
            retention="30 days",
            compression="zip",
            backtrace=True,
            diagnose=True,
            filter=self._coze_filter,
            encoding="utf-8"
        )
        
        # 按日期分割的日志文件（用于归档）
        self.logger.add(
            self._log_dir / "coze-fastapi_{time:YYYY-MM-DD}.log",
            format=file_format,
            level=self.config.log_level,
            rotation="00:00",
            retention="30 days",
            compression="zip",
            backtrace=True,
            diagnose=True,
            filter=self._coze_filter,
            encoding="utf-8"
        )
    
    def _coze_filter(self, record) -> bool:
        """Coze模块日志过滤器
        
        Args:
            record: 日志记录
            
        Returns:
            bool: 是否记录该日志
        """
        # 只记录coze模块相关的日志
        module_name = record.get("name", "")
        return (
            module_name.startswith("app") or
            module_name.startswith("coze") or
            "coze" in module_name.lower()
        )
    
    def get_logger(self, name: Optional[str] = None):
        """获取日志记录器
        
        Args:
            name: 日志记录器名称
            
        Returns:
            logger: 配置好的日志记录器
        """
        if not self._configured:
            self.configure()
        
        if name:
            return self.logger.bind(name=name)
        return self.logger
    
    def create_api_logger(self, endpoint: str, request_id: Optional[str] = None):
        """为API请求创建专用日志记录器
        
        Args:
            endpoint: API端点
            request_id: 请求ID
            
        Returns:
            logger: API专用日志记录器
        """
        bind_data = {
            "endpoint": endpoint,
            "component": "api"
        }
        
        if request_id:
            bind_data["request_id"] = request_id
        
        return self.get_logger().bind(**bind_data)


# 全局日志管理器实例
_coze_logger = CozeLogger()


def get_coze_logger(name: Optional[str] = None):
    """获取Coze模块日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        logger: 配置好的日志记录器
    """
    return _coze_logger.get_logger(name)


def configure_coze_logging(log_dir: Optional[str] = None) -> None:
    """配置Coze模块日志系统
    
    Args:
        log_dir: 日志目录路径
    """
    _coze_logger.configure(log_dir)


def get_api_logger(endpoint: str, request_id: Optional[str] = None):
    """获取API专用日志记录器
    
    Args:
        endpoint: API端点
        request_id: 请求ID
        
    Returns:
        logger: API专用日志记录器
    """
    return _coze_logger.create_api_logger(endpoint, request_id)

