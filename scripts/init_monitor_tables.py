#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
初始化监控相关的数据库表
"""

import asyncio
from tortoise import Tortoise
from config.settings import settings, create_db_config
from models.config import MonitorConfig, UserSession
from utils.logger import logger


async def init_tables():
    """初始化监控相关的数据库表"""
    
    # 初始化数据库连接
    await Tortoise.init(config=create_db_config())
    
    # 生成表结构
    await Tortoise.generate_schemas(safe=True)
    
    logger.info("监控相关表初始化完成")
    
    # 关闭连接
    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(init_tables())