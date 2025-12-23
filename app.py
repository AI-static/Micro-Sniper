# -*- coding: utf-8 -*-
"""
Sanic应用配置
"""
from sanic import Sanic
from sanic.config import Config
from types import SimpleNamespace
from sanic.request import Request
from sanic_cors import CORS
from sanic_ext import Extend
from playwright.async_api import async_playwright
from config.settings import settings, create_db_config
from utils.logger import logger
from tortoise import Tortoise



def create_app() -> Sanic:
    """创建Sanic应用实例"""
    app: Sanic[Config, SimpleNamespace] = Sanic("Aether")

    # 配置
    app.config.REQUEST_MAX_SIZE = 1024 * 1024 * 200
    app.ctx.settings = settings
    
    # 扩展
    Extend(app)

    # CORS
    CORS(
        app,
        resources={r"/*": {"origins": "*"}},
        supports_credentials=True,
    )

    # WebSocket
    app.enable_websocket()

    # 中间件
    from middleware.request_context import RequestContextMiddleware
    RequestContextMiddleware(app)
    
    # 身份验证中间件
    from middleware.auth import AuthMiddleware
    AuthMiddleware(app)
    
    # 异常处理
    from middleware.exception_handler import ExceptionHandlerMiddleware
    ExceptionHandlerMiddleware(app)
    
    # 注册路由
    register_routes(app)
    
    # 数据库初始化
    setup_database(app)
    
    # Playwright 初始化
    setup_playwright(app)
    
    return app


def register_routes(app: Sanic):
    """注册路由"""
    
    # 健康检查
    @app.route("/health")
    async def health_check(request: Request):
        """健康检查"""
        return {"status": "ok", "service": "aether"}
    
    # 注册业务路由
    from api.routes.image import bp as image_bp
    from api.routes.identity import identity_bp
    from api.routes.connectors import connectors_bp
    from api.routes.callback import callback_bp
    app.blueprint(image_bp)
    app.blueprint(identity_bp)
    app.blueprint(connectors_bp)
    app.blueprint(callback_bp)


def setup_database(app: Sanic):
    """设置数据库连接"""

    @app.before_server_start
    async def create_db(app: Sanic, loop):
        # 初始化ORM
        await Tortoise.init(config=create_db_config())
        await Tortoise.generate_schemas()
        logger.info(f"✅ 初始化ORM成功")


def setup_playwright(app: Sanic):
    """设置全局的 Playwright 实例"""

    @app.before_server_start
    async def init_playwright(app: Sanic, loop):
        """初始化 Playwright"""
        logger.info("🎭 初始化 Playwright...")
        app.ctx.playwright = await async_playwright().start()

    @app.before_server_stop
    async def cleanup_playwright(app: Sanic, loop):
        """清理 Playwright 资源"""
        logger.info("🎭 清理 Playwright 资源...")
        if hasattr(app.ctx, 'playwright'):
            await app.ctx.playwright.stop()
            logger.info("✅ Playwright 资源已清理")
