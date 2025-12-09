"""请求上下文中间件"""
import time
import uuid
from sanic import Sanic
from sanic.request import Request
from sanic.response import BaseHTTPResponse
from utils.logger import logger, set_request_id


class RequestContextMiddleware:
    """请求上下文中间件"""
    
    def __init__(self, app: Sanic):
        self.app = app
        self.app.register_middleware(self.add_request_context, "request")
        self.app.register_middleware(self.log_response, "response")

    async def add_request_context(self, request: Request) -> None:
        """添加请求上下文"""
        user_ip = request.headers.get("X-Real-IP", "0.0.0.0")
        
        # 生成请求ID
        request_id = str(uuid.uuid4())
        request.ctx.request_id = request_id
        request.ctx.start_time = time.time()
        request.ctx.user_ip = user_ip
        
        # 注入请求ID到上下文
        set_request_id(request_id)
        
        # 记录请求
        logger.info(f"{request.method} {request.path} - IP: {user_ip}")
    
    async def log_response(self, request: Request, response: BaseHTTPResponse) -> None:
        """记录响应日志"""
        try:
            if not hasattr(request.ctx, 'start_time'):
                return

            cost = time.time() - request.ctx.start_time

            logger.info(
                f"完成 | 耗时: {cost:.3f}s | 状态: {response.status}"
            )
        except Exception as ex:
            logger.error(f"响应日志记录异常: {ex}")