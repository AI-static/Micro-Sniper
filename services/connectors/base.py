# -*- coding: utf-8 -*-
"""连接器基类 - 提取公共逻辑"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from playwright.async_api import async_playwright, Page

from agentbay import AgentBay
from agentbay.browser.browser_agent import ExtractOptions
from agentbay.session_params import CreateSessionParams, BrowserContext
from agentbay.browser.browser import BrowserOption, BrowserScreen, BrowserFingerprint
from config.settings import global_settings
from utils.logger import logger
from sanic import Sanic
import re


class BaseConnector(ABC):
    """连接器基类 - 所有平台连接器的基类"""

    def __init__(self, platform_name: str):
        """初始化连接器

        Args:
            platform_name: 平台名称，用于日志和会话标识
        """
        self.platform_name = platform_name
        self.api_key = global_settings.agentbay.api_key
        if not self.api_key:
            raise ValueError("AGENTBAY_API_KEY is required")

        self.agent_bay = AgentBay(api_key=self.api_key)

    def get_locale(self) -> List[str]:
        """获取浏览器语言设置，子类可重写"""
        return ["zh-CN"]

    async def _get_browser_context(self, context_id=None) -> Tuple[Any, Any, Any, Any]:
        """获取浏览器上下文（连接到 CDP）

        Returns:
            tuple: (playwright, browser, context)
        """
        # 每次调用都创建新的 session
        p = await async_playwright().start()
        
        # 创建浏览器会话
        browser_context = None
        if context_id:
            browser_context = BrowserContext(context_id, auto_upload=True)

        session_result = self.agent_bay.create(
            CreateSessionParams(
                image_id="browser_latest",
                browser_context=browser_context
            )
        )

        if not session_result.success:
            p.stop()
            raise RuntimeError(f"Failed to create session: {session_result.error_message}")

        session = session_result.session

        # 初始化浏览器选项
        screen_option = BrowserScreen(width=1920, height=1080)
        browser_init_options = BrowserOption(
            screen=screen_option,
            solve_captchas=True,
            use_stealth=True,
            fingerprint=BrowserFingerprint(
                devices=["desktop"],
                operating_systems=["windows"],
                locales=self.get_locale(),
            ),
        )

        ok = await session.browser.initialize_async(browser_init_options)
        if not ok:
            session.delete()
            p.stop()
            raise RuntimeError("Failed to initialize browser")

        # 连接到 CDP
        endpoint_url = session.browser.get_endpoint_url()
        browser = await p.chromium.connect_over_cdp(endpoint_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()

        # 返回时包含 session，方便后续清理
        return p, browser, context, session

    async def _create_persistent_context_by_cookies(self,
                                                    context_id: str,
                                                    cookies: Dict[str, str],
                                                    domain: str,
                                                    verify_login_url: str,
                                                    verify_login_func) -> Optional[str]:
        """创建持久化上下文并设置 cookies
        
        Args:
            context_id: 上下文ID
            cookies: cookie 字典
            domain: cookie 域名
            verify_login_url: 验证登录的URL
            verify_login_func: 验证登录状态的函数，接收 page 参数，返回 bool
            
        Returns:
            str|None: 成功返回 context_id，失败返回 None
        """
        session = None
        try:
            # Step 1: Create or get persistent context
            logger.info(f"[{self.platform_name}] Creating context '{context_id}'...")
            context_result = self.agent_bay.context.get(context_id, create=True)
            
            if not context_result.success or not context_result.context:
                logger.error(f"[{self.platform_name}] Failed to create context: {context_result.error_message}")
                return None
                
            context = context_result.context
            logger.info(f"[{self.platform_name}] Context created with ID: {context.id}")
            
            # Step 2: Create session with BrowserContext
            browser_context = BrowserContext(context.id, auto_upload=True)
            
            params = CreateSessionParams(
                image_id="browser_latest",
                browser_context=browser_context
            )
            
            logger.info(f"[{self.platform_name}] Creating session with BrowserContext...")
            session_result = self.agent_bay.create(params)
            
            if not session_result.success or not session_result.session:
                logger.error(f"[{self.platform_name}] Failed to create session: {session_result.error_message}")
                return None
                
            # Store the session for later use
            session = session_result.session
            logger.info(f"[{self.platform_name}] Session created with ID: {session.session_id}")
            
            # Step 3: Initialize browser and set cookies
            logger.info(f"[{self.platform_name}] Initializing browser and setting cookies...")
            
            # Initialize browser with minimal options
            init_success = session.browser.initialize(BrowserOption())
            
            if not init_success:
                logger.error(f"[{self.platform_name}] Failed to initialize browser")
                return None
                
            logger.info(f"[{self.platform_name}] Browser initialized successfully")
            
            # Get endpoint URL
            endpoint_url = session.browser.get_endpoint_url()
            if not endpoint_url:
                logger.error(f"[{self.platform_name}] Failed to get browser endpoint URL")
                return None
                
            logger.info(f"[{self.platform_name}] Browser endpoint URL: {endpoint_url}")
            is_logged_in = False
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(endpoint_url)
                context_p = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = await context_p.new_page()

                # Convert cookies to Playwright format
                cookies_list = []
                for name, value in cookies.items():
                    cookies_list.append({
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": "/",
                        "httpOnly": False,
                        "secure": False,
                        "expires": int(time.time()) + 3600 * 24  # 24 hours from now
                    })
                await context_p.add_cookies(cookies_list)
                # 等待cookie生效
                await asyncio.sleep(0.6)

                await page.goto(verify_login_url, timeout=60000)
                await asyncio.sleep(0.6)


                logger.info(f"[{self.platform_name}] Added {len(cookies_list)} cookies")

                # Check if login is successful
                is_logged_in = await verify_login_func(page)

                await browser.close()

            # Step 4: Delete session with context synchronization
            if is_logged_in:
                logger.info(f"[{self.platform_name}] Login successful, saving session with context sync...")
                # Delete session and sync context to save cookies
                delete_result = self.agent_bay.delete(session, sync_context=True)

                if delete_result.success:
                    logger.info(f"[{self.platform_name}] Session saved successfully (RequestID: {delete_result.request_id})")
                else:
                    logger.error(f"[{self.platform_name}] Failed to save session: {delete_result.error_message}")

                # Wait for context sync to complete
                await asyncio.sleep(1.5)

                # Return the context_id for later use
                return context_id
            else:
                logger.warning(f"[{self.platform_name}] Login failed - invalid cookies")
                # Delete session without saving
                self.agent_bay.delete(session, sync_context=False)

        except Exception as e:
            logger.error(f"[{self.platform_name}] Error creating persistent context: {e}", exc_info=True)
            return None
        finally:
            # Clean up session if it exists
            if session:
                try:
                    self.agent_bay.delete(session, sync_context=False)
                except:
                    pass

    async def _extract_page_content(
        self,
        page: Page,
        instruction: str,
        schema = None
    ) -> Tuple[bool, Any]:
        """从页面提取内容

        Args:
            page: Playwright 页面对象
            instruction: 提取指令
            schema: 可选的数据结构定义

        Returns:
            tuple: (成功标志, 提取的数据)
        """
        # 需要传入 session 才能使用 agent
        # 这个方法现在需要在子类中重写，传入 session
        raise NotImplementedError("This method needs to be overridden in subclass with session parameter")

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
        pass
    
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
        pass
    
    @abstractmethod
    async def extract_by_creator_id(
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
        pass
    
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
        pass

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

    def _get_note_detail_config(self) -> Dict[str, Any]:
        """获取笔记详情的配置（子类可重写）
        
        返回配置字典，包含：
        - title_selectors: 标题选择器列表
        - author_selectors: 作者选择器列表
        - content_selectors: 内容选择器列表
        - image_selectors: 图片选择器列表（可选）
        - time_selectors: 时间选择器列表（可选）
        - stats_selectors: 统计信息选择器列表（可选）
        - custom_extractors: 自定义提取函数列表（可选）
        """
        return {}
    
    def _get_summary_config(self) -> Dict[str, Any]:
        """获取摘要提取的配置（子类可重写）
        
        返回配置字典，包含：
        - title_selectors: 标题选择器列表
        - content_selectors: 内容选择器列表
        """
        return {}
    
    async def _extract_content_parallel(
        self,
        page: Page,
        url: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """通用的并行内容提取方法
        
        Args:
            page: Playwright 页面对象
            url: 页面URL
            config: 提取配置字典
        
        Returns:
            Dict: 提取的内容
        """
        try:
            # 打印页面标题，用于调试
            title = await page.title()
            logger.info(f"[{self.platform_name} Fast] 页面标题: {title}")
            
            content = {
                "url": url,
                "title": title,
                "extract_time": asyncio.get_event_loop().time(),
                "success": True,
                "method": "fast_playwright_extraction"
            }
            
            # 准备并行任务
            extract_tasks = []
            
            # 标题提取
            if config.get("title_selectors"):
                async def extract_title():
                    for selector in config["title_selectors"]:
                        elem = await page.query_selector(selector)
                        if elem:
                            text = await elem.inner_text()
                            if text.strip() and len(text.strip()) > 5:
                                return text.strip()
                    return None
                extract_tasks.append(("title", extract_title()))
            
            # 作者提取
            if config.get("author_selectors"):
                async def extract_author():
                    for selector in config["author_selectors"]:
                        elem = await page.query_selector(selector)
                        if elem:
                            text = await elem.inner_text()
                            if text.strip():
                                return text.strip()
                    return None
                extract_tasks.append(("author", extract_author()))
            
            # 发布时间提取
            if config.get("time_selectors"):
                async def extract_time():
                    for selector in config["time_selectors"]:
                        elem = await page.query_selector(selector)
                        if elem:
                            text = await elem.inner_text()
                            if re.search(r'\d{4}-\d{2}-\d{2}|\d{2}:\d{2}|年|月|日', text):
                                return text.strip()
                    return None
                extract_tasks.append(("publish_time", extract_time()))
            
            # 内容提取（包含图片）
            if config.get("content_selectors"):
                async def extract_content_with_images():
                    for selector in config["content_selectors"]:
                        elem = await page.query_selector(selector)
                        if elem:
                            # 获取HTML内容
                            html_content = await elem.inner_html()
                            
                            if html_content:
                                logger.info(f"[{self.platform_name} Fast] 开始提取内容和图片")
                                
                                # 并行提取所有图片URL
                                img_elements = await elem.query_selector_all("img")
                                img_tasks = []
                                
                                for idx, img in enumerate(img_elements):
                                    async def get_img_info(img_elem):
                                        # 获取所有可能的图片URL属性
                                        src = await img_elem.get_attribute("data-src") or await img_elem.get_attribute("src") or await img_elem.get_attribute("data-original")
                                        if src:
                                            if src.startswith("//"):
                                                src = "https:" + src
                                            return {
                                                "src": src,
                                                "tag": await img_elem.evaluate("(elem) => elem.outerHTML")
                                            }
                                        return None
                                    img_tasks.append(get_img_info(img))
                                
                                image_results = await asyncio.gather(*img_tasks)
                                image_infos = [r for r in image_results if r]
                                
                                # 在HTML中替换图片为Markdown
                                markdown_content = html_content
                                for img_info in image_infos:
                                    img_src = img_info["src"]
                                    img_tag = img_info["tag"]
                                    img_markdown = f"\n\n![图片]({img_src})\n\n"
                                    markdown_content = markdown_content.replace(img_tag, img_markdown)
                                
                                # 清理HTML标签
                                markdown_content = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\n\1\n\n', markdown_content)
                                markdown_content = re.sub(r'<div[^>]*>(.*?)</div>', r'\n\n\1\n\n', markdown_content)
                                markdown_content = re.sub(r'<br[^>]*>', '\n', markdown_content)
                                markdown_content = re.sub(r'<[^>]+>', '', markdown_content)
                                markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content).strip()
                                
                                # 获取纯文本内容
                                text_content = await elem.inner_text()
                                
                                logger.info(f"[{self.platform_name} Fast] 提取完成: {len(image_infos)} 张图片, 内容长度: {len(markdown_content)}")
                                
                                return {
                                    "content": markdown_content,
                                    "html_content": html_content,
                                    "length": len(markdown_content),
                                    "summary": text_content[:200] + "..." if len(text_content) > 200 else text_content,
                                    "images": [info["src"] for info in image_infos]
                                }
                    return None
                extract_tasks.append(("content_data", extract_content_with_images()))
            
            # 图片提取
            if config.get("image_selectors"):
                async def extract_images():
                    img_selector = config["image_selectors"][0]  # 使用第一个选择器
                    img_elements = await page.query_selector_all(img_selector)
                    img_tasks = []
                    
                    # 并行获取图片URL
                    for img in img_elements[:20]:  # 限制最多20张图片
                        async def get_img_src(img_elem):
                            src = await img_elem.get_attribute("data-src") or await img_elem.get_attribute("src")
                            if src:
                                if src.startswith("//"):
                                    src = "https:" + src
                                if src.startswith("http"):
                                    return src
                            return None
                        img_tasks.append(get_img_src(img))
                    
                    img_urls = await asyncio.gather(*img_tasks)
                    img_urls = [u for u in img_urls if u]  # 过滤空值
                    
                    return {
                        "urls": img_urls,
                        "count": len(img_urls)
                    }
                extract_tasks.append(("images_data", extract_images()))
            
            # 统计信息提取
            if config.get("stats_selectors"):
                async def extract_stats():
                    stats = {}
                    for selector in config["stats_selectors"]:
                        elem = await page.query_selector(selector)
                        if elem:
                            text = await elem.inner_text()
                            numbers = re.findall(r'[\d,]+', text)
                            if numbers and int(numbers[0].replace(',', '')) > 10:
                                stats["read_count"] = int(numbers[0].replace(',', ''))
                                break
                    return stats
                extract_tasks.append(("stats", extract_stats()))
            
            # 自定义提取函数
            if config.get("custom_extractors"):
                for name, func in config["custom_extractors"].items():
                    extract_tasks.append((name, func(page)))
            
            # 并行执行所有任务
            results = await asyncio.gather(
                *[task for _, task in extract_tasks],
                return_exceptions=True
            )
            
            # 临时存储内容提取结果和图片提取结果
            content_result = None
            images_result = None
            stats_result = None
            
            # 处理结果
            for i, (key, _) in enumerate(extract_tasks):
                result = results[i]
                if result and not isinstance(result, Exception):
                    if key == "content_data":
                        content_result = result
                        content["content"] = result["content"]
                        content["content_length"] = result["length"]
                        content["summary"] = result["summary"]
                        logger.info(f"[{self.platform_name} Fast] 找到正文内容，长度: {result['length']}")
                    elif key == "images_data":
                        images_result = result
                        content["images"] = result["urls"]
                        content["image_count"] = result["count"]
                        logger.info(f"[{self.platform_name} Fast] 找到 {result['count']} 张图片")
                    elif key == "stats":
                        stats_result = result
                        content["stats"] = result
                    elif key == "title":
                        content["title"] = result
                        logger.info(f"[{self.platform_name} Fast] 找到标题: {result[:50] if result else 'N/A'}...")
                    elif key == "author":
                        content["author"] = result
                        logger.info(f"[{self.platform_name} Fast] 找到作者: {result}")
                    elif key == "publish_time":
                        content["publish_time"] = result
                        logger.info(f"[{self.platform_name} Fast] 找到发布时间: {result}")
                    else:
                        content[key] = result
                        if isinstance(result, dict):
                            logger.info(f"[{self.platform_name} Fast] 找到 {key}: {result}")
            
            # 内容中已经包含图片了
            if content_result:
                # 图片信息已经在content_data中处理了
                content["images"] = content_result.get("images", [])
                content["image_count"] = len(content["images"])
                content["content_with_images"] = len(content["images"]) > 0
            else:
                # 没有内容或图片
                content["images"] = images_result["urls"] if images_result else []
                content["image_count"] = len(content["images"])
                content["content_with_images"] = False
            
            # 设置默认值
            if "images" not in content:
                content["images"] = []
                content["image_count"] = 0
            if "stats" not in content:
                content["stats"] = {}
            
            return content
            
        except Exception as e:
            logger.error(f"[{self.platform_name} Fast] 提取失败: {e}")
            return {
                "url": url,
                "success": False,
                "error": str(e),
                "method": "fast_playwright_extraction"
            }

  
