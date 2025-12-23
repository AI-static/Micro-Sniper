# -*- coding: utf-8 -*-
"""Session 管理器 - 在 Sanic app.ctx 中管理 AgentBay sessions

设计原则：
- 只用 key 来管理 session，不关心业务逻辑
- key 由业务层（Connector）拼接，manager 只负责存储和获取
- 原子化操作：get_or_create_session 是线程安全的
- 全局单例：session_manager 在整个应用中共享
"""

import asyncio
from typing import Dict, Any, Optional
from agentbay import AsyncAgentBay, CreateSessionParams, BrowserContext, BrowserOption, BrowserScreen, BrowserFingerprint

from utils.logger import logger
from config.settings import global_settings


class Session:
    """管理 AgentBay sessions 的生命周期（全局单例）"""

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        api_key = global_settings.agentbay.api_key
        if not api_key:
            raise ValueError("AGENTBAY_API_KEY is required")
        
        self.agent_bay = AsyncAgentBay(api_key=api_key)
        self.sessions: Dict[str, Any] = {}
        self.locks: Dict[str, asyncio.Lock] = {}
        self._initialized = True

    async def get_or_create_session(
        self,
        key: str,
        locale: list = None
    ) -> Any:
        """获取或创建 session（原子化操作）
        
        Args:
            key: session 的唯一标识（由业务层拼接）
            locale: 浏览器语言设置
            
        Returns:
            session 对象
        """
        if key in self.sessions:
            logger.info(f"[Session] Reusing existing session for {key}")
            return self.sessions[key]
        
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()
        
        async with self.locks[key]:
            if key in self.sessions:
                return self.sessions[key]
            
            logger.info(f"[Session] Creating new session for {key}")
            
            session_result = await self.agent_bay.create(
                CreateSessionParams(
                    image_id="browser_latest",
                    browser_context=BrowserContext(key, auto_upload=True)
                )
            )
            
            if not session_result.success:
                raise RuntimeError(f"Failed to create session: {session_result.error_message}")
            
            session = session_result.session
            
            screen_option = BrowserScreen(width=1920, height=1080)
            browser_init_options = BrowserOption(
                screen=screen_option,
                solve_captchas=True,
                use_stealth=True,
                fingerprint=BrowserFingerprint(
                    devices=["desktop"],
                    operating_systems=["windows"],
                    locales=locale or ["zh-CN"],
                ),
            )
            
            ok = await session.browser.initialize(browser_init_options)
            if not ok:
                await self.agent_bay.delete(session, sync_context=False)
                raise RuntimeError("Failed to initialize browser")
            
            self.sessions[key] = session
            logger.info(f"[Session] Session created and cached for {key}")
            
            return session

    async def close_session(self, key: str):
        """关闭并清理指定的 session
        
        Args:
            key: session 的唯一标识
        """
        if key in self.sessions:
            session = self.sessions.pop(key)
            try:
                await self.agent_bay.delete(session, sync_context=False)
                logger.info(f"[Session] Session closed for {key}")
            except Exception as e:
                logger.error(f"[Session] Error closing session for {key}: {e}")
            finally:
                if key in self.locks:
                    del self.locks[key]

    async def close_all_sessions(self):
        """关闭所有缓存的 sessions（用于 Sanic 关闭时清理）"""
        logger.info("Closing all sessions...")
        
        for key, session in list(self.sessions.items()):
            try:
                await self.agent_bay.delete(session, sync_context=False)
                logger.info(f"Session closed for {key}")
            except Exception as e:
                logger.error(f"Error closing session for {key}: {e}")
        
        self.sessions.clear()
        self.locks.clear()
        logger.info("All sessions closed")

    def get_session_count(self) -> int:
        """获取当前缓存的 session 数量"""
        return len(self.sessions)

    def list_sessions(self) -> list:
        """列出所有缓存的 session keys"""
        return list(self.sessions.keys())


# 全局单例
session_manager = Session()