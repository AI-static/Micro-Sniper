# -*- coding: utf-8 -*-
"""
Sanic应用配置
"""
from sanic import Sanic
from sanic.config import Config
from sanic.request import Request
from sanic_cors import CORS
from sanic_ext import Extend
from playwright.async_api import async_playwright
from config.settings import settings, create_db_config
from utils.logger import logger
from tortoise import Tortoise
from types import SimpleNamespace


def create_app() -> Sanic:
    """创建Sanic应用实例"""
    app: Sanic[Config, SimpleNamespace] = Sanic(settings.app.name)

    # 配置
    app.config.REQUEST_MAX_SIZE = 1024 * 1024 * 200

    # 超时配置（适配二维码登录等长时间操作）
    app.config.REQUEST_TIMEOUT = 300  # 请求超时：5分钟
    app.config.RESPONSE_TIMEOUT = 300  # 响应超时：5分钟

    app.ctx.settings = settings

    # 静态文件服务（启用 index 参数处理目录访问）
    app.static('/static', './static', name='static_files', index='index.html')

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
    from api.routes.sniper import sniper_bp
    app.blueprint(image_bp)
    app.blueprint(identity_bp)
    app.blueprint(connectors_bp)
    app.blueprint(callback_bp)
    app.blueprint(sniper_bp)


def setup_database(app: Sanic):
    """设置数据库连接"""

    @app.before_server_start
    async def create_db(app: Sanic):
        # 初始化ORM
        await Tortoise.init(config=create_db_config())
        await Tortoise.generate_schemas()
        logger.info(f"✅ 初始化ORM成功")

    @app.after_server_stop
    async def close_db(app: Sanic):
        await Tortoise.close_connections()
        logger.info("✅ 数据库连接已关闭")


def setup_playwright(app: Sanic):
    """设置全局的 Playwright 实例"""

    @app.before_server_start
    async def init_playwright(app: Sanic):
        """初始化 Playwright"""
        logger.info("🎭 初始化 Playwright...")
        app.ctx.playwright = await async_playwright().start()

    @app.before_server_stop
    async def cleanup_playwright(app: Sanic):
        """清理 Playwright 资源和分布式锁"""
        logger.info("🎭 清理 Playwright 资源...")
        if hasattr(app.ctx, 'playwright'):
            await app.ctx.playwright.stop()
            logger.info("✅ Playwright 资源已清理")

        # 清理所有活跃任务的分布式锁
        from services.sniper.connectors import ConnectorService
        await ConnectorService.cleanup_all_locks()
        logger.info("✅ 分布式锁已清理")
