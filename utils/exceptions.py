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


class NotLoggedInException(BusinessException):
    """平台未登录异常 - 需要登录平台账号才能继续操作

    注意：这是业务逻辑层面的"未登录"，不是系统身份验证的 401
    """
    def __init__(
        self,
        message: str = "需要登录平台账号",
        platform: str = None,
        context_id: str = None,
        resource_url: str = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.NOT_LOGGED_IN,  # 使用业务错误码 604，不是 HTTP 401
            details={
                "error_type": "not_logged_in",
                "platform": platform,
                "context_id": context_id,
                "resource_url": resource_url,
                "requires_login": True
            }
        )
        self.platform = platform
        self.context_id = context_id
        self.resource_url = resource_url