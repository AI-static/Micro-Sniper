"""异常处理中间件"""
import traceback
from sanic import Sanic
from sanic.request import Request
from sanic.response import HTTPResponse
from sanic.exceptions import NotFound
from utils.logger import logger


class ExceptionHandlerMiddleware:
    """异常处理中间件"""
    
    def __init__(self, app: Sanic):
        self.app = app
        self.setup_exception_handlers(app)

    def setup_exception_handlers(self, app: Sanic):
        """设置异常处理"""
        
        @app.exception(NotFound)
        async def not_found_handler(request: Request, exc: NotFound) -> HTTPResponse:
            """404处理"""
            from sanic.response import json
            from api.schema.base import BaseResponse, ErrorCode, ErrorMessage
            return json(
                BaseResponse(
                    code=ErrorCode.NOT_FOUND,
                    message=ErrorMessage.NOT_FOUND
                ).model_dump(),
                status=404
            )
        
        @app.exception(Exception)
        async def global_exception_handler(request: Request, exc: Exception):
            """全局异常处理"""
            from sanic.response import json
            from api.schema.base import BaseResponse, ErrorCode, ErrorMessage
            from utils.exceptions import BusinessException, RateLimitException, LockConflictException, ContextNotFoundException
            
            # 业务异常处理
            if isinstance(exc, BusinessException):
                logger.warning(f"业务异常: {exc.message} - {exc.details}")
                
                # 根据异常类型确定HTTP状态码
                status = 400
                if isinstance(exc, RateLimitException):
                    status = 429  # Too Many Requests
                elif isinstance(exc, LockConflictException):
                    status = 409  # Conflict
                elif isinstance(exc, ContextNotFoundException):
                    status = 401  # Unauthorized
                elif exc.code >= 500:
                    status = 500
                elif exc.code == 404:
                    status = 404
                    
                return json(
                    BaseResponse(
                        code=exc.code,
                        message=exc.message,
                        data=exc.details if exc.details else None
                    ).model_dump(),
                    status=status
                )
            
            # 系统异常处理
            logger.error(f"系统异常: {exc}\n{traceback.format_exc()}")
            return json(
                BaseResponse(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=ErrorMessage.INTERNAL_ERROR
                ).model_dump(),
                status=500
            )