# -*- coding: utf-8 -*-
from app import create_app
from config.settings import settings

# 创建应用
app = create_app()

if __name__ == '__main__':
    # 启动 Sanic 应用
    app.run(
        host="0.0.0.0",
        port=settings.app.port,
        debug=settings.app.debug,
        auto_reload=settings.app.env == "dev"
    )

