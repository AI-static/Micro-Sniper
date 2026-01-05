"""身份验证中间件"""
from typing import Optional
from sanic import Request, Sanic
from sanic.response import JSONResponse
from services.identity_service import identity_service
from utils.logger import logger


class AuthMiddleware:
    """简化的身份验证中间件"""
    
    def __init__(self, app: Sanic):
        self.app = app
        self.app.register_middleware(self.authenticate, "request")

    async def authenticate(
        self,
        request: Request,
        response: Optional[JSONResponse] = None
    ) -> Optional[JSONResponse]:
        """处理请求的身份验证"""
        # 跳过认证的路由
        if self._should_skip_auth(request):
            return None
        
        # 验证身份
        try:
            # 从 Authorization header 中提取 Bearer token
            auth_header = request.headers.get('authorization')
            apikey = None
            
            if auth_header and auth_header.startswith('Bearer '):
                apikey = auth_header[7:]  # 去掉 'Bearer ' 前缀
            
            if not apikey:
                raise ValueError("缺少认证令牌")
            
            # 验证API密钥并获取用户信息
            auth_info = await identity_service.validate_auth(
                api_key=apikey,
            )
            
            # 将认证信息存储到请求上下文中
            request.ctx.auth_info = auth_info
            # 为了方便访问，单独设置api_key_id
            request.ctx.api_key_id = auth_info.id
            
            logger.info(f"身份验证成功: {auth_info.source}:{auth_info.source_id} - {request.method} {request.path}")
            return None
            
        except ValueError as e:
            logger.warning(f"身份验证失败: {request.method} {request.path} - {str(e)}")
            return JSONResponse(
            {
                "success": False,
                "error": "UNAUTHORIZED",
                "message": str(e)
            },
            status=401
        )
    
    @staticmethod
    def _should_skip_auth(request: Request) -> bool:
        """检查是否应该跳过认证"""
        exempt_routes = [
            "/health",
            "/callback/wechat_verify/",
            "/static"
        ]

        for route in exempt_routes:
            if request.path.startswith(route):
                return True

        if request.method == "OPTIONS":
            return True

        return False