"""自定义异常类"""
from typing import Optional
from api.schema.base import ErrorCode


class BusinessException(Exception):
    """业务异常基类"""
    def __init__(self, message: str, code: int = ErrorCode.INTERNAL_ERROR, details: Optional[dict] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class RateLimitException(BusinessException):
    """频率限制异常"""
    def __init__(self, message: str = "操作过于频繁，请稍后再试"):
        super().__init__(
            message=message,
            code=ErrorCode.BAD_REQUEST,
            details={"error_type": "rate_limit_exceeded"}
        )


class LockConflictException(BusinessException):
    """锁冲突异常 - 正在运行相同任务"""
    def __init__(self, message: str = "当前正在运行相同任务，请等待完成后再试"):
        super().__init__(
            message=message,
            code=ErrorCode.BAD_REQUEST,
            details={"error_type": "operation_in_progress"}
        )


class ContextNotFoundException(BusinessException):
    """Context 不存在异常 - 用户未登录"""
    def __init__(self, message: str = "登录态不存在，请先登录"):
        super().__init__(
            message=message,
            code=ErrorCode.BAD_REQUEST,
            details={"error_type": "context_not_found"}
        )


class SessionCreationException(BusinessException):
    """Session 创建失败异常"""
    def __init__(self, message: str = "创建浏览器会话失败"):
        super().__init__(
            message=message,
            code=ErrorCode.INTERNAL_ERROR,
            details={"error_type": "session_creation_failed"}
        )


class BrowserInitializationException(BusinessException):
    """浏览器初始化失败异常"""
    def __init__(self, message: str = "浏览器初始化失败"):
        super().__init__(
            message=message,
            code=ErrorCode.INTERNAL_ERROR,
            details={"error_type": "browser_init_failed"}
        )