# -*- coding: utf-8 -*-
"""微信公众号连接器 - 支持文章提取和监控"""

import asyncio
from agentbay import ActOptions, CreateSessionParams, BrowserOption, BrowserScreen, BrowserFingerprint
from typing import Dict, Any, List, Optional

from .base import BaseConnector
from utils.logger import logger
from utils.exceptions import SessionCreationException, BrowserInitializationException
from pydantic import BaseModel, Field
from models.connectors import PlatformType

class GzhArticleSummary(BaseModel):
    """公众号文章摘要（用于URL列表详情提取）"""
    title: str = Field(..., description="文章标题")
    author: str = Field(..., description="公众号名称")
    publish_time: str = Field("", description="发布时间")
    key_points: List[str] = Field(default_factory=list, description="文章关键要点列表")
    struct: str = Field("", description="详细的文章结构（带证据链）")

class WechatConnector(BaseConnector):
    """微信公众号连接器"""

    def __init__(self, playwright):
        super().__init__(platform_name=PlatformType.WECHAT, playwright=playwright)

    async def harvest_user_content(
        self,
        creator_ids: List[str],
        limit: Optional[int] = None,
        source: str = "default",
        source_id: str = "default",
        concurrency: int = 2
    ) -> List[Dict[str, Any]]:
        """采收公众号的所有文章

        Args:
            creator_ids: 公众号的 __biz 参数列表
            limit: 限制数量
            source: 系统标识
            source_id: 用户标识
            concurrency: 并发数
        """
        pass
    
    async def get_note_detail(
        self,
        urls: List[str],
        source: str = "default",
        source_id: str = "default",
        concurrency: int = 2
    ) -> List[Dict[str, Any]]:
        """快速获取微信文章详情（不需要登录）

        Args:
            urls: 文章URL列表
            concurrency: 并发数
            source: 系统标识
            source_id: 用户标识
        Returns:
            提取结果列表
        """
        if not urls:
            raise ValueError("未输入urls")

        # 微信公众号文章是公开的，不需要登录，直接创建临时浏览器会话
        from agentbay import CreateSessionParams, BrowserOption, BrowserScreen, BrowserFingerprint

        logger.info(f"[WechatConnector] 创建临时浏览器会话采集 {len(urls)} 篇文章")

        # 创建临时 session（不使用持久化 context）
        session_result = await self.agent_bay.create(
            CreateSessionParams(
                image_id="browser_latest",
                browser_context=None  # 不使用持久化 context，每次都是新的
            )
        )

        if not session_result.success:
            raise SessionCreationException(f"Failed to create session: {session_result.error_message}")

        session = session_result.session

        # 初始化浏览器
        ok = await session.browser.initialize(
            BrowserOption(
                screen=BrowserScreen(width=1920, height=1080),
                solve_captchas=True,
                use_stealth=True,
                fingerprint=BrowserFingerprint(
                    devices=["desktop"],
                    operating_systems=["windows"],
                    locales=["zh-CN"],
                ),
            )
        )
        if not ok:
            await self.agent_bay.delete(session, sync_context=False)
            raise BrowserInitializationException("Failed to initialize browser")

        # 连接 CDP 以使用 Playwright API
        endpoint_url = await session.browser.get_endpoint_url()
        browser = await self.playwright.chromium.connect_over_cdp(endpoint_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()

        try:
            semaphore = asyncio.Semaphore(concurrency)

            async def extract_detail(url):
                async with semaphore:
                    page = None
                    try:
                        page = await context.new_page()
                        await page.goto(url, timeout=30000)
                        await page.wait_for_load_state("networkidle", timeout=10000)

                        # 使用evaluate快速提取文章信息
                        article_data = await page.evaluate("""
                            () => {
                                // 提取标题
                                const titleEl = document.querySelector('#activity-name, .rich_media_title, h1');
                                const title = titleEl ? titleEl.innerText.trim() : '';

                                // 提取作者
                                const authorEl = document.querySelector('#profileBt, .rich_media_meta_text, [id*="author"]');
                                const author = authorEl ? authorEl.innerText.trim() : '';

                                // 提取发布时间
                                const timeEl = document.querySelector('#publish_time, .rich_media_meta_text, [id*="time"]');
                                let publishTime = '';
                                if (timeEl) {
                                    const text = timeEl.innerText.trim();
                                    // 匹配各种时间格式
                                    const timeMatch = text.match(/(\\d{4}-\\d{2}-\\d{2}|\\d{2}:\\d{2}|\\d{4}年\\d{1,2}月\\d{1,2}日)/);
                                    publishTime = timeMatch ? timeMatch[1] : text;
                                }

                                // 提取阅读量
                                const readNumEl = document.querySelector('#sg_read_num3, .read_num, [id*="read"]');
                                let readCount = 0;
                                if (readNumEl) {
                                    const text = readNumEl.innerText;
                                    const numMatch = text.match(/(\\d+,?\\d*)/);
                                    readCount = numMatch ? parseInt(numMatch[1].replace(/,/g, '')) : 0;
                                }

                                // 提取内容
                                const contentEl = document.querySelector('#js_content, .rich_media_content, [id*="content"]');
                                let content = '';
                                let images = [];

                                if (contentEl) {
                                    // 获取纯文本内容
                                    content = contentEl.innerText.trim();

                                    // 提取所有图片
                                    const imgEls = contentEl.querySelectorAll('img');
                                    images = Array.from(imgEls).map(img => {
                                        const src = img.getAttribute('data-src') ||
                                                   img.getAttribute('src') ||
                                                   img.getAttribute('data-original');
                                        if (src && !src.startsWith('data:')) {
                                            return src.startsWith('//') ? 'https:' + src : src;
                                        }
                                        return null;
                                    }).filter(Boolean);
                                }

                                // 提取摘要
                                const summary = content.length > 200 ?
                                    content.substring(0, 200) + '...' : content;

                                return {
                                    title: title,
                                    author: author,
                                    publish_time: publishTime,
                                    read_count: readCount,
                                    content: content,
                                    summary: summary,
                                    images: images,
                                    image_count: images.length,
                                    content_length: content.length
                                };
                            }
                        """)

                        return {
                            "url": url,
                            "success": True,
                            "data": article_data,
                            "method": "evaluate_extraction"
                        }
                    except Exception as e:
                        return {
                            "url": url,
                            "success": False,
                            "error": str(e),
                            "method": "evaluate_extraction"
                        }
                    finally:
                        if page:
                            await page.close()

            tasks = [extract_detail(url) for url in urls]
            results = await asyncio.gather(*tasks)
            return results

        finally:
            # 清理资源
            try:
                if browser:
                    cdp = await browser.new_browser_cdp_session()
                    await cdp.send('Browser.close')
                    await asyncio.sleep(0.5)
                await browser.close()
            except Exception as e:
                logger.warning(f"[WechatConnector] Error closing browser: {e}")

            if session:
                await self.agent_bay.delete(session, sync_context=False)  # 不需要保存 context
                logger.info(f"[WechatConnector] Temporary session deleted")

    async def harvest_user_content_by_creator(
        self,
        creator_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """通过公众号ID提取文章

        注意：此功能需要在微信客户端中打开链接，当前Web环境无法直接访问。
        需要对接agentbay的云桌面才能实现。

        Args:
            creator_id: 公众号的 __biz 参数
            limit: 限制数量

        Returns:
            文章列表
        """
        pass


    async def _parse_json_stream(
        self,
        url: str,
        keyword: Optional[str] = None,
        limit: int = 20
    ):
        """高效流式解析 JSON 订阅源

        Args:
            url: 订阅源 URL
            keyword: 搜索关键字（可选）
            limit: 返回结果数量限制

        Yields:
            匹配的文章项
        """
        pass

    async def _search_from_rss(
        self,
        keyword: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """从 RSS 订阅源搜索文章

        Args:
            keyword: 搜索关键字（可选）
            limit: 返回结果数量限制

        Returns:
            搜索结果列表
        """
        pass

    async def search_and_extract(
        self,
        keywords: List[str],
        limit: int = 20,
        user_id: Optional[str] = None,
        source: str = "default",
        source_id: str = "default",
        concurrency: int = 2
    ) -> List[Dict[str, Any]]:
        """搜索并提取微信文章

        仅支持通过 RSS 订阅源获取文章

        Args:
            keywords: 搜索关键词列表
            limit: 每个关键词限制结果数量
            user_id: 可选的用户ID过滤
            source: 系统标识
            source_id: 用户标识
            concurrency: 并发数
        Returns:
            搜索结果列表
        """
        pass

