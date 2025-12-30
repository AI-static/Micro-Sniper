# -*- coding: utf-8 -*-
"""连接器基类 - 提取公共逻辑"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from playwright.async_api import async_playwright, Page

from agentbay import AsyncAgentBay
from agentbay import ExtractOptions, CreateSessionParams, BrowserContext, BrowserOption, BrowserScreen, BrowserFingerprint
from config.settings import global_settings
from utils.logger import logger
import re
from sanic import Sanic


class BaseConnector(ABC):
    """连接器基类 - 所有平台连接器的基类
    
    设计原则：
    - 子类负责实现 _build_session_key() 方法来拼接自己的 session key
    - 不再透传 source/source_id
    - playwright 实例由外部传入，支持独立脚本运行
    """

    def __init__(self, platform_name: str, playwright=None):
        """初始化连接器

        Args:
            platform_name: 平台名称，用于日志和会话标识
            playwright: Playwright 实例，如果不提供则从 Sanic app 获取
        """
        self.platform_name = platform_name
        api_key = global_settings.agentbay.api_key
        if not api_key:
            raise ValueError("AGENTBAY_API_KEY is required")
        self.agent_bay = AsyncAgentBay(api_key=api_key)
        
        # Playwright 实例管理
        self._playwright_instance = playwright

    @property
    def playwright(self):
        """获取 Playwright 实例"""
        if self._playwright_instance:
            return self._playwright_instance
        # 如果没有传入实例，则从 Sanic app 获取（兼容 API 模式）
        return Sanic.get_app(global_settings.app.name).ctx.playwright

    @staticmethod
    async def cleanup_pages(context):
        pages = context.pages
        logger.info(f"清理开始，当前共有 {len(pages)} 个页面待关闭")

        # 使用 gather 同时关闭所有页面，效率最高
        await asyncio.gather(*[p.close() for p in pages])
        logger.info("所有并发页面已清理完毕")

    def get_locale(self) -> List[str]:
        """获取浏览器语言设置，子类可重写"""
        return ["zh-CN"]

    def _build_session_key(self, source: str = "default", source_id: str = "default") -> str:
        """构建 session key（子类可重写）
        
        Args:
            source: 系统标识
            source_id: 用户标识
            
        Returns:
            session key 字符串
        """
        return f"{self.platform_name}:{source}:{source_id}"

    async def _get_session(self, source: str = "default", source_id: str = "default") -> Any:
        """创建新的 session普通 session，不使用 context_id

        Args:
            source: 系统标识
            source_id: 用户标识

        Returns:
            session 对象
        """
        from agentbay import CreateSessionParams, BrowserContext, BrowserOption, BrowserScreen, BrowserFingerprint
        
        key = self._build_session_key(source, source_id)
        
        # 创建 session
        session_result = await self.agent_bay.create(
            CreateSessionParams(
                image_id="browser_latest",
                browser_context=BrowserContext(key, auto_upload=True)
            )
        )
        
        if not session_result.success:
            raise RuntimeError(f"Failed to create session: {session_result.error_message}")
        
        session = session_result.session
        
        # 初始化浏览器
        ok = await session.browser.initialize(BrowserOption(
            screen=BrowserScreen(width=1920, height=1080),
            solve_captchas=True,
            use_stealth=True,
            fingerprint=BrowserFingerprint(
                devices=["desktop"],
                operating_systems=["windows"],
                locales=self.get_locale(),
            ),
        ))
        
        if not ok:
            await self.agent_bay.delete(session, sync_context=False)
            raise RuntimeError("Failed to initialize browser")
        
        return session

    # ==================== 需要子类实现的抽象方法 ====================

    @abstractmethod
    async def extract_summary_stream(
        self,
        urls: List[str]
    ) -> List[Dict[str, Any]]:
        """提取内容摘要（子类必须实现）

        Args:
            urls: 要提取的URL列表

        Returns:
            List[Dict]: 提取结果列表
        """
        raise NotImplementedError(f"{self.platform_name} does not support extract_summary_stream")

    @abstractmethod
    async def get_note_detail(
        self,
        urls: List[str]
    ) -> List[Dict[str, Any]]:
        """获取笔记/文章详情（子类必须实现）

        Args:
            urls: 要提取的URL列表

        Returns:
            List[Dict]: 提取结果列表
        """
        raise NotImplementedError(f"{self.platform_name} does not support get_note_detail")

    @abstractmethod
    async def harvest_user_content(
        self,
        creator_id: str,
        limit: Optional[int] = None,
        extract_details: bool = False
    ) -> List[Dict[str, Any]]:
        """通过创作者ID提取内容（子类必须实现）

        Args:
            creator_id: 创作者ID
            limit: 限制数量
            extract_details: 是否提取详情

        Returns:
            List[Dict]: 提取结果列表
        """
        raise NotImplementedError(f"{self.platform_name} does not support extract_by_creator_id")

    @abstractmethod
    async def search_and_extract(
        self,
        keyword: str,
        limit: int = 20,
        extract_details: bool = False
    ) -> List[Dict[str, Any]]:
        """搜索并提取内容（子类必须实现）

        Args:
            keyword: 搜索关键词
            limit: 限制数量
            extract_details: 是否提取详情

        Returns:
            List[Dict]: 搜索结果列表
        """
        raise NotImplementedError(f"{self.platform_name} does not support harvest_user_content")

    async def harvest_user_content(
        self,
        user_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """采收用户内容（可选实现）

        Args:
            user_id: 用户ID
            limit: 限制数量

        Returns:
            List[Dict]: 内容列表
        """
        raise NotImplementedError(f"{self.platform_name} does not support harvest_user_content")

    async def login_with_cookies(
            self,
            cookies: Dict[str, str],
            source: str = "default",
            source_id: str = "default"
    ) -> str:
        """根据cookie登陆（可选实现）

        Returns:
            str: context_id 用于恢复登录态
        """
        raise NotImplementedError(f"{self.platform_name} does not support login_with_cookies")

    async def publish_content(
        self,
        content: str,
        content_type: str = "text",
        images: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """发布内容（可选实现）

        Args:
            content: 内容文本
            content_type: 内容类型
            images: 图片列表
            tags: 标签列表

        Returns:
            Dict: 发布结果
        """
        raise NotImplementedError(f"{self.platform_name} does not support publish_content")