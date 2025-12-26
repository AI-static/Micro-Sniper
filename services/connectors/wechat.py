# -*- coding: utf-8 -*-
"""微信公众号连接器 - 支持文章提取和监控"""

import asyncio
import json
from agentbay import ActOptions, CreateSessionParams, BrowserOption, BrowserScreen, BrowserFingerprint
from typing import Dict, Any, List, Optional, AsyncGenerator
import aiohttp

from .base import BaseConnector
from utils.logger import logger
from utils.exceptions import SessionCreationException, BrowserInitializationException
from pydantic import BaseModel, Field
from models.connectors import PlatformType
from config.settings import settings

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
        self.rss_url = settings.wechat.rss_url
        self.rss_timeout = settings.wechat.rss_timeout
        self.rss_buffer_size = settings.wechat.rss_buffer_size

    def _build_context_id(self, source: str, source_id: str) -> str:
        """构建 context_id: xiaohongshu:{source}:{source_id}"""
        return f"wechat-context:{source}:{source_id}"

    async def _require_login(self, source: str, source_id: str) -> str:
        """验证并返回有效的 context_id

        Args:
            source: 系统标识
            source_id: 用户标识

        Returns:
            有效的 context_id

        Raises:
            ValueError: 用户未登录
        """
        # 不需要检查
        context_id = self._build_context_id(source, source_id)

        return context_id

    async def _get_browser_session(
            self,
            source: str = "default",
            source_id: str = "default"
    ) -> Any:
        """获取 browser session（使用持久化 context）

        Args:
            context_id: 持久化上下文ID
            source: 系统标识
            source_id: 用户标识

        Returns:
            session 对象
        """

        # 使用 context 创建 session
        session_result = await self.agent_bay.create(
            CreateSessionParams(
                image_id="browser_latest"
            )
        )

        if not session_result.success:
            raise SessionCreationException(f"Failed to create session: {session_result.error_message}")

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
            raise BrowserInitializationException("Failed to initialize browser")

        return session

    async def extract_summary_stream(
        self,
        urls: List[str],
        concurrency: int=1,
        source: str=None,
        source_id: str=None,
    ):
        """流式提取微信公众号文章摘要，支持并发"""
        # 定义提取指令
        instruction = "根据数据结构提取相关内容，并进行内容总结分析"

        session = await self._get_browser_session(source, source_id)

        try:
            # 创建信号量来限制并发数
            semaphore = asyncio.Semaphore(concurrency)

            async def extract_single_url(url: str, idx: int):
                """提取单个 URL（使用共享的 browser context）"""
                async with semaphore:
                    logger.info(f"[wechat] Processing URL {idx}/{len(urls)}: {url}")
                    try:
                        # 关闭可能出现的弹窗
                        try:
                            agent = session.browser.agent
                            nav_msg = await agent.navigate(url)
                            await agent.act_async(
                                ActOptions(action="如果有弹窗或广告，关闭它们，然后滑动到文章最下边。"),
                            )
                        except:
                            pass

                        # 提取文章内容
                        ok, data = await self._extract_page_content(page, instruction, GzhArticleSummary)
                        result = {
                            "url": url,
                            "success": ok,
                            "data": data.model_dump() if ok else {}
                        }

                        logger.info(f"[wechat] Extracted summary for URL {idx}/{len(urls)}, success={ok}")

                        return result

                    except Exception as e:
                        logger.error(f"[wechat] Error extracting {url}: {e}")
                        return {
                            "url": url,
                            "success": False,
                            "error": str(e)
                        }
                    finally:
                        # 关闭 page
                        if page:
                            await page.close()

            # 启动所有任务
            tasks = [
                asyncio.create_task(extract_single_url(url, idx))
                for idx, url in enumerate(urls, 1)
            ]

            # 使用 as_completed 来实时返回结果（谁先完成就先返回谁）
            for completed_task in asyncio.as_completed(tasks):
                result = await completed_task
                yield result

        finally:
            # 所有 URL 处理完后删除 session
            await self.agent_bay.delete(session, sync_context=False)

    async def harvest_user_content(
        self,
        user_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """采收公众号的所有文章

        Args:
            user_id: 公众号的 __biz 参数
            limit: 限制数量
        """
        return await self.extract_by_creator_id(user_id, limit=limit, extract_details=False)
    
    async def get_note_detail(
        self,
        urls: List[str],
        concurrency: int = 3,
        source: str = "default",
        source_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """快速获取微信文章详情
        
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

        # 获取或创建 session
        session = await self._get_browser_session(source, source_id)
        endpoint_url = await session.browser.get_endpoint_url()
        
        browser = await self.playwright.chromium.connect_over_cdp(endpoint_url)
        context = browser.contexts[0]
        
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
            await self.agent_bay.delete(session, sync_context=False)
    
    async def harvest_user_content(
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
            extract_details: 是否提取详情
            
        Returns:
            文章列表
        """
        logger.error(f"[wechat] extract_by_creator_id not supported: {creator_id}")
        
        # 直接返回错误，提示需要微信客户端
        raise NotImplementedError(
            "微信公众号文章列表提取需要微信客户端环境，待开发。"
        )

    
    async def _parse_json_stream(
        self,
        url: str,
        keyword: Optional[str] = None,
        limit: int = 20
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """高效流式解析 JSON 订阅源
        
        Args:
            url: 订阅源 URL
            keyword: 搜索关键字（可选）
            limit: 返回结果数量限制
            
        Yields:
            匹配的文章项
        """
        count = 0
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.rss_timeout)) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"[wechat] RSS feed returned status {response.status}")
                        return
                    
                    # 使用流式读取，避免全量加载到内存
                    buffer = ""
                    in_items = False
                    brace_count = 0
                    in_string = False
                    escape_next = False
                    
                    async for chunk in response.content.iter_chunked(self.rss_buffer_size):
                        buffer += chunk.decode('utf-8', errors='ignore')
                        
                        # 如果还没找到 items 数组，继续查找
                        if not in_items:
                            items_start = buffer.find('"items":[')
                            if items_start != -1:
                                in_items = True
                                buffer = buffer[items_start + 9:]  # 跳过 "items":[
                                brace_count = 0
                        
                        # 已找到 items，开始解析每个对象
                        while in_items and buffer:
                            for i, char in enumerate(buffer):
                                if escape_next:
                                    escape_next = False
                                    continue
                                    
                                if char == '\\':
                                    escape_next = True
                                    continue
                                    
                                if char == '"' and not escape_next:
                                    in_string = not in_string
                                    continue
                                    
                                if not in_string:
                                    if char == '{':
                                        if brace_count == 0:
                                            item_start = i
                                        brace_count += 1
                                    elif char == '}':
                                        brace_count -= 1
                                        if brace_count == 0:
                                            # 完整的 JSON 对象
                                            item_json = buffer[item_start:i+1]
                                            buffer = buffer[i+1:]
                                            
                                            try:
                                                item = json.loads(item_json)
                                                
                                                # 关键字匹配
                                                if keyword:
                                                    search_text = f"{item.get('title', '')} {item.get('description', '')} {item.get('channel_name', '')}".lower()
                                                    if keyword.lower() not in search_text:
                                                        continue
                                                
                                                yield {
                                                    "title": item.get("title", ""),
                                                    "description": item.get("description", ""),
                                                    "link": item.get("link", ""),
                                                    "updated": item.get("updated", ""),
                                                    "content": item.get("content", ""),
                                                    "channel_name": item.get("channel_name", ""),
                                                    "feed": item.get("feed", {}),
                                                    "id": item.get("id", "")
                                                }
                                                
                                                count += 1
                                                if count >= limit:
                                                    return
                                                    
                                            except json.JSONDecodeError:
                                                logger.warning(f"[wechat] Failed to parse item JSON")
                                            
                                            break
                            
                            # 如果 buffer 太小，继续读取
                            if len(buffer) < 100:
                                break
                                
        except Exception as e:
            logger.error(f"[wechat] Error parsing RSS feed: {e}")
    
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
        if not self.rss_url:
            logger.warning("[wechat] RSS URL not configured")
            return []
        
        logger.info(f"[wechat] Searching from RSS feed: {self.rss_url}")
        
        results = []
        async for item in self._parse_json_stream(self.rss_url, keyword, limit):
            results.append({
                "success": True,
                "data": item,
                "source": "rss_feed"
            })
        
        logger.info(f"[wechat] Found {len(results)} articles from RSS feed")
        return results
    
    async def search_and_extract(
        self,
        keyword: Optional[str] = None,
        limit: int = 20,
        source: str = "default",
        source_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """搜索并提取微信文章
        
        仅支持通过 RSS 订阅源获取文章
        
        Args:
            keyword: 搜索关键词（可选，如果不提供则返回所有文章）
            limit: 限制数量
        Returns:
            搜索结果
        """
        # 检查是否配置了 RSS 订阅源
        if not self.rss_url:
            raise ValueError(
                "WeChat RSS URL not configured. Please set WECHAT__RSS_URL in your environment variables."
            )
        
        # 从 RSS 订阅源搜索
        return await self._search_from_rss(keyword, limit)
