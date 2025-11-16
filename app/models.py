# -*- coding: utf-8 -*-
"""
Coze模块数据模型
定义会话、聊天和用户相关的数据结构
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from enum import Enum

from .utils import (
    generate_session_id, generate_chat_id, get_current_timestamp, 
    format_timestamp, validate_message, validate_session_id, validate_user_id
)
from .exceptions import CozeValidationError


class SessionStatus(Enum):
    """会话状态枚举"""
    ACTIVE = "active"          # 活跃状态
    INACTIVE = "inactive"      # 非活跃状态
    EXPIRED = "expired"        # 已过期
    TERMINATED = "terminated"  # 已终止


class ChatStatus(Enum):
    """聊天状态枚举"""
    PENDING = "pending"        # 等待中
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 已取消


class MessageRole(Enum):
    """消息角色枚举"""
    USER = "user"              # 用户消息
    ASSISTANT = "assistant"    # 助手消息
    SYSTEM = "system"          # 系统消息


@dataclass
class CozeMessage:
    """Coze消息模型"""
    role: MessageRole
    content: str
    timestamp: Optional[str] = None
    message_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """初始化后处理"""
        if self.timestamp is None:
            self.timestamp = format_timestamp(get_current_timestamp())
        
        if self.message_id is None:
            self.message_id = generate_chat_id()
        
        if self.metadata is None:
            self.metadata = {}
        
        # 验证消息内容
        if not validate_message(self.content):
            raise CozeValidationError(f"Invalid message content: {self.content}")
        
        # 确保role是MessageRole枚举
        if isinstance(self.role, str):
            try:
                self.role = MessageRole(self.role)
            except ValueError:
                raise CozeValidationError(f"Invalid message role: {self.role}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'role': self.role.value,
            'content': self.content,
            'timestamp': self.timestamp,
            'message_id': self.message_id,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CozeMessage':
        """从字典创建实例"""
        return cls(
            role=MessageRole(data['role']),
            content=data['content'],
            timestamp=data.get('timestamp'),
            message_id=data.get('message_id'),
            metadata=data.get('metadata', {})
        )
    
    def get_content_length(self) -> int:
        """获取消息内容长度"""
        return len(self.content)
    
    def is_user_message(self) -> bool:
        """是否为用户消息"""
        return self.role == MessageRole.USER
    
    def is_assistant_message(self) -> bool:
        """是否为助手消息"""
        return self.role == MessageRole.ASSISTANT


@dataclass
class CozeChat:
    """Coze聊天模型"""
    chat_id: str
    session_id: str
    user_message: CozeMessage
    status: ChatStatus = ChatStatus.PENDING
    assistant_message: Optional[CozeMessage] = None
    content: Optional[str] = None  # AI回答内容
    reasoning_content: Optional[str] = None  # 思考过程
    follow_up_questions: Optional[List[str]] = None  # 建议问题
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """初始化后处理"""
        current_time = format_timestamp(get_current_timestamp())
        
        if self.created_at is None:
            self.created_at = current_time
        
        if self.updated_at is None:
            self.updated_at = current_time
        
        if self.metadata is None:
            self.metadata = {}
        
        if self.follow_up_questions is None:
            self.follow_up_questions = []
        
        # 验证会话ID
        if not validate_session_id(self.session_id):
            raise CozeValidationError(f"Invalid session ID: {self.session_id}")
        
        # 确保status是ChatStatus枚举
        if isinstance(self.status, str):
            try:
                self.status = ChatStatus(self.status)
            except ValueError:
                raise CozeValidationError(f"Invalid chat status: {self.status}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'chat_id': self.chat_id,
            'session_id': self.session_id,
            'user_message': self.user_message.to_dict(),
            'status': self.status.value,
            'assistant_message': self.assistant_message.to_dict() if self.assistant_message else None,
            'content': self.content,
            'reasoning_content': self.reasoning_content,
            'follow_up_questions': self.follow_up_questions or [],
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'completed_at': self.completed_at,
            'error_message': self.error_message,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CozeChat':
        """从字典创建实例"""
        user_message = CozeMessage.from_dict(data['user_message'])
        assistant_message = None
        if data.get('assistant_message'):
            assistant_message = CozeMessage.from_dict(data['assistant_message'])
        
        return cls(
            chat_id=data['chat_id'],
            session_id=data['session_id'],
            user_message=user_message,
            status=ChatStatus(data['status']),
            assistant_message=assistant_message,
            content=data.get('content'),
            reasoning_content=data.get('reasoning_content'),
            follow_up_questions=data.get('follow_up_questions', []),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            completed_at=data.get('completed_at'),
            error_message=data.get('error_message'),
            metadata=data.get('metadata', {})
        )
    
    def update_status(self, status: ChatStatus, error_message: Optional[str] = None):
        """更新聊天状态"""
        self.status = status
        self.updated_at = format_timestamp(get_current_timestamp())
        
        if error_message:
            self.error_message = error_message
        
        if status == ChatStatus.COMPLETED:
            self.completed_at = self.updated_at
    
    def set_assistant_message(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        """设置助手回复消息"""
        self.assistant_message = CozeMessage(
            role=MessageRole.ASSISTANT,
            content=content,
            metadata=metadata or {}
        )
        self.update_status(ChatStatus.COMPLETED)
    
    def set_api_result(self, content: str, reasoning_content: Optional[str] = None, 
                      follow_up_questions: Optional[List[str]] = None, 
                      metadata: Optional[Dict[str, Any]] = None):
        """设置API解析的结果"""
        self.content = content
        self.reasoning_content = reasoning_content
        self.follow_up_questions = follow_up_questions or []
        
        # 同时设置assistant_message以保持兼容性
        self.assistant_message = CozeMessage(
            role=MessageRole.ASSISTANT,
            content=content,
            metadata=metadata or {}
        )
        
        # 更新元数据
        if metadata:
            if self.metadata is None:
                self.metadata = {}
            self.metadata.update(metadata)
        
        self.update_status(ChatStatus.COMPLETED)
    
    def is_completed(self) -> bool:
        """是否已完成"""
        return self.status == ChatStatus.COMPLETED
    
    def is_failed(self) -> bool:
        """是否失败"""
        return self.status == ChatStatus.FAILED
    
    def get_duration(self) -> Optional[float]:
        """获取聊天持续时间（秒）"""
        if not self.completed_at or not self.created_at:
            return None
        
        try:
            created = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
            completed = datetime.fromisoformat(self.completed_at.replace('Z', '+00:00'))
            return (completed - created).total_seconds()
        except Exception:
            return None


@dataclass
class CozeSession:
    """Coze会话模型"""
    session_id: str
    user_id: str
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_activity_at: Optional[str] = None
    expires_at: Optional[str] = None
    chat_history: List[CozeChat] = field(default_factory=list)
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """初始化后处理"""
        current_time = format_timestamp(get_current_timestamp())
        
        if self.created_at is None:
            self.created_at = current_time
        
        if self.updated_at is None:
            self.updated_at = current_time
        
        if self.last_activity_at is None:
            self.last_activity_at = current_time
        
        if self.context is None:
            self.context = {}
        
        if self.metadata is None:
            self.metadata = {}
        
        # 验证用户ID
        if not validate_user_id(self.user_id):
            raise CozeValidationError(f"Invalid user ID: {self.user_id}")
        
        # 验证会话ID
        if not validate_session_id(self.session_id):
            raise CozeValidationError(f"Invalid session ID: {self.session_id}")
        
        # 确保status是SessionStatus枚举
        if isinstance(self.status, str):
            try:
                self.status = SessionStatus(self.status)
            except ValueError:
                raise CozeValidationError(f"Invalid session status: {self.status}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'status': self.status.value,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_activity_at': self.last_activity_at,
            'expires_at': self.expires_at,
            'chat_history': [chat.to_dict() for chat in self.chat_history],
            'context': self.context,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CozeSession':
        """从字典创建实例"""
        chat_history = []
        if data.get('chat_history'):
            chat_history = [CozeChat.from_dict(chat_data) for chat_data in data['chat_history']]
        
        return cls(
            session_id=data['session_id'],
            user_id=data['user_id'],
            status=SessionStatus(data['status']),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            last_activity_at=data.get('last_activity_at'),
            expires_at=data.get('expires_at'),
            chat_history=chat_history,
            context=data.get('context', {}),
            metadata=data.get('metadata', {})
        )
    
    def update_activity(self):
        """更新活动时间"""
        current_time = format_timestamp(get_current_timestamp())
        self.last_activity_at = current_time
        self.updated_at = current_time
    
    def add_chat(self, chat: CozeChat):
        """添加聊天记录"""
        if chat.session_id != self.session_id:
            raise CozeValidationError(f"Chat session ID {chat.session_id} does not match session {self.session_id}")
        
        self.chat_history.append(chat)
        self.update_activity()
    
    def get_latest_chat(self) -> Optional[CozeChat]:
        """获取最新的聊天记录"""
        return self.chat_history[-1] if self.chat_history else None
    
    def get_chat_count(self) -> int:
        """获取聊天数量"""
        return len(self.chat_history)
    
    def get_completed_chat_count(self) -> int:
        """获取已完成的聊天数量"""
        return sum(1 for chat in self.chat_history if chat.is_completed())
    
    def get_failed_chat_count(self) -> int:
        """获取失败的聊天数量"""
        return sum(1 for chat in self.chat_history if chat.is_failed())
    
    def is_active(self) -> bool:
        """是否为活跃状态"""
        return self.status == SessionStatus.ACTIVE
    
    def is_expired(self) -> bool:
        """是否已过期"""
        if self.status == SessionStatus.EXPIRED:
            return True
        
        if self.expires_at:
            try:
                expires = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
                return datetime.now(expires.tzinfo) > expires
            except Exception:
                return False
        
        return False
    
    def terminate(self, reason: Optional[str] = None):
        """终止会话"""
        self.status = SessionStatus.TERMINATED
        self.updated_at = format_timestamp(get_current_timestamp())
        
        if reason:
            self.metadata['termination_reason'] = reason
    
    def set_expires_at(self, expires_at: str):
        """设置过期时间"""
        self.expires_at = expires_at
        self.updated_at = format_timestamp(get_current_timestamp())
    
    def get_context_value(self, key: str, default: Any = None) -> Any:
        """获取上下文值"""
        if self.context is None:
            return default
        return self.context.get(key, default)
    
    def set_context_value(self, key: str, value: Any):
        """设置上下文值"""
        if self.context is None:
            self.context = {}
        self.context[key] = value
        self.updated_at = format_timestamp(get_current_timestamp())
    
    def clear_context(self):
        """清空上下文"""
        self.context = {}
        self.updated_at = format_timestamp(get_current_timestamp())
    
    def get_session_duration(self) -> Optional[float]:
        """获取会话持续时间（秒）"""
        if not self.created_at or not self.last_activity_at:
            return None
        
        try:
            created = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
            last_activity = datetime.fromisoformat(self.last_activity_at.replace('Z', '+00:00'))
            return (last_activity - created).total_seconds()
        except Exception:
            return None


@dataclass
class CozeUser:
    """Coze用户模型"""
    user_id: str
    active_sessions: List[str] = field(default_factory=list)
    total_sessions: int = 0
    total_chats: int = 0
    created_at: Optional[str] = None
    last_activity_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """初始化后处理"""
        current_time = format_timestamp(get_current_timestamp())
        
        if self.created_at is None:
            self.created_at = current_time
        
        if self.last_activity_at is None:
            self.last_activity_at = current_time
        
        if self.metadata is None:
            self.metadata = {}
        
        # 验证用户ID
        if not validate_user_id(self.user_id):
            raise CozeValidationError(f"Invalid user ID: {self.user_id}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'user_id': self.user_id,
            'active_sessions': self.active_sessions,
            'total_sessions': self.total_sessions,
            'total_chats': self.total_chats,
            'created_at': self.created_at,
            'last_activity_at': self.last_activity_at,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CozeUser':
        """从字典创建实例"""
        return cls(
            user_id=data['user_id'],
            active_sessions=data.get('active_sessions', []),
            total_sessions=data.get('total_sessions', 0),
            total_chats=data.get('total_chats', 0),
            created_at=data.get('created_at'),
            last_activity_at=data.get('last_activity_at'),
            metadata=data.get('metadata', {})
        )
    
    def add_session(self, session_id: str):
        """添加会话"""
        if session_id not in self.active_sessions:
            self.active_sessions.append(session_id)
        self.total_sessions += 1
        self.last_activity_at = format_timestamp(get_current_timestamp())
    
    def remove_session(self, session_id: str):
        """移除会话"""
        if session_id in self.active_sessions:
            self.active_sessions.remove(session_id)
        self.last_activity_at = format_timestamp(get_current_timestamp())
    
    def add_chat(self):
        """增加聊天计数"""
        self.total_chats += 1
        self.last_activity_at = format_timestamp(get_current_timestamp())
    
    def get_active_session_count(self) -> int:
        """获取活跃会话数量"""
        return len(self.active_sessions)
    
    def has_active_sessions(self) -> bool:
        """是否有活跃会话"""
        return len(self.active_sessions) > 0


# 工厂函数

def create_coze_session(user_id: str, session_id: Optional[str] = None, 
                       context: Optional[Dict[str, Any]] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> CozeSession:
    """创建Coze会话"""
    if session_id is None:
        session_id = generate_session_id()
    
    return CozeSession(
        session_id=session_id,
        user_id=user_id,
        context=context or {},
        metadata=metadata or {}
    )


def create_coze_chat(session_id: str, user_message_content: str,
                     chat_id: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> CozeChat:
    """创建Coze聊天"""
    if chat_id is None:
        chat_id = generate_chat_id()
    
    user_message = CozeMessage(
        role=MessageRole.USER,
        content=user_message_content,
        metadata=metadata or {}
    )
    
    return CozeChat(
        chat_id=chat_id,
        session_id=session_id,
        user_message=user_message,
        metadata=metadata or {}
    )


def create_coze_user(user_id: str, metadata: Optional[Dict[str, Any]] = None) -> CozeUser:
    """创建Coze用户"""
    return CozeUser(
        user_id=user_id,
        metadata=metadata or {}
    )

