# -*- coding: utf-8 -*-
"""小红书连接器 - 支持登录、提取、发布、监控 (优化版)"""

import asyncio
import time
import json
import base64
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from playwright.async_api import Page
from datetime import datetime

from .base import BaseConnector
from utils.logger import logger
from utils.exceptions import ContextNotFoundException, SessionCreationException, BrowserInitializationException
from utils.oss import oss_client
from agentbay import ActOptions
from models.connectors import PlatformType
from agentbay import CreateSessionParams, BrowserContext, BrowserOption, BrowserScreen, BrowserFingerprint


class XiaohongshuConnector(BaseConnector):
    """小红书连接器

    所有操作都需要登录，因此必须提供 context_id
    """

    def __init__(self, playwright):
        super().__init__(platform_name=PlatformType.XIAOHONGSHU, playwright=playwright)

    @property
    def platform_name_str(self) -> str:
        return self.platform_name.value

    def _build_context_id(self, source: str, source_id: str) -> str:
        return f"{self.platform_name.value}-context:{source}-{source_id}"

    async def _get_browser_session(
            self,
            source: str = "default",
            source_id: str = "default"
    ) -> Any:
        """获取 browser session（使用持久化 context）"""
        context_key = self._build_context_id(source, source_id)
        # 获取持久化 context
        context_result = await self.agent_bay.context.get(context_key, create=False)
        if not context_result.success or not context_result.context:
            raise ContextNotFoundException(f"Context '{context_key}' not found，请先登录")

        logger.info(f"Using context {context_key} :{context_result.context.id}")

        # 使用 context 创建 session
        session_result = await self.agent_bay.create(
            CreateSessionParams(
                image_id="browser_latest",
                browser_context=BrowserContext(context_result.context.id, auto_upload=True)
            )
        )

        if not session_result.success:
            raise SessionCreationException(f"Failed to create session: {session_result.error_message}")

        session = session_result.session

        # 初始化浏览器
        ok = await session.browser.initialize(BrowserOption())
        if not ok:
            await self.agent_bay.delete(session, sync_context=False)
            raise BrowserInitializationException("Failed to initialize browser")

        return session

    # ==================== 资源管理与通用逻辑 (核心优化部分) ====================

    async def _connect_cdp(self, session):
        """连接 CDP 并获取 context"""
        endpoint_url = await session.browser.get_endpoint_url()
        browser = await self.playwright.chromium.connect_over_cdp(endpoint_url)
        # 通常 connect_over_cdp 会复用上下文，这里取第一个
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        return browser, context

    async def _cleanup_resources(self, session, browser):
        """统一清理资源"""

        try:
            if browser:
                # 尝试通过 CDP 关闭，更干净
                cdp = await browser.new_browser_cdp_session()
                await cdp.send('Browser.close')
                await asyncio.sleep(1)  # 给一点时间让 socket 关闭
                browser.close()
            if session:
                # 默认 sync_context=True 以保存 Cookie 状态
                await self.agent_bay.delete(session, sync_context=True)
        except Exception:
            pass

    async def _batch_execute(
            self,
            items: List[Any],
            processor: Callable[[Any, int, Any, Any], Any],
            concurrency: int = 2,
            source: str = "default",
            source_id: str = "default"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """通用并发批处理执行器

        Args:
            items: 待处理的数据列表 (url列表, id列表, keyword列表等)
            processor: 处理函数，签名需为 async (item, idx, context, session) -> dict
            concurrency: 并发数
        """
        session = None
        browser = None

        try:
            # 1. 初始化环境
            session = await self._get_browser_session(source, source_id)
            browser, context = await self._connect_cdp(session)

            # 2. 并发控制
            semaphore = asyncio.Semaphore(concurrency)

            async def worker(item, idx):
                async with semaphore:
                    try:
                        return await processor(item, idx, context, session)
                    except Exception as e:
                        logger.error(f"[xiaohongshu] Worker error processing {item}: {e}")
                        return {
                            "item": item,
                            "success": False,
                            "error": str(e)
                        }

            # 3. 创建任务
            tasks = [asyncio.create_task(worker(item, idx)) for idx, item in enumerate(items)]

            # 4. 实时产生结果
            for completed_task in asyncio.as_completed(tasks):
                yield await completed_task

        except Exception as e:
            logger.error(f"[xiaohongshu] Batch execution failed: {e}")
            raise
        finally:
            # 5. 统一清理
            await self._cleanup_resources(session, browser)

    # ==================== 业务逻辑：登录与发布 ====================

    async def login_with_cookies(
            self,
            cookies: Dict[str, str],
            source: str = "default",
            source_id: str = "default"
    ) -> str:
        """使用 Cookie 登录小红书"""
        context_key = self._build_context_id(source, source_id)
        logger.info(f"[xiaohongshu] Logging in with context_id: {context_key}")

        # 获取或创建 Context
        context_res = await self.agent_bay.context.get(context_key, create=True)
        if not context_res.success:
            raise ValueError(f"Failed to create context: {context_res.error_message}")

        # 创建临时 Session 进行 Cookie 注入
        session_res = await self.agent_bay.create(
            CreateSessionParams(
                image_id="browser_latest",
                browser_context=BrowserContext(context_res.context.id, auto_upload=True)
            )
        )
        if not session_res.success:
            raise ValueError(f"Failed to create session: {session_res.error_message}")

        session = session_res.session
        browser = None

        try:
            await session.browser.initialize(BrowserOption(
                screen=BrowserScreen(width=1920, height=1080),
                solve_captchas=True,
                use_stealth=True,
                fingerprint=BrowserFingerprint(
                    devices=["desktop"],
                    operating_systems=["windows"],
                    locales=self.get_locale(),
                ),
            ))
            browser, context_p = await self._connect_cdp(session)
            page = await context_p.new_page()

            # 转换并注入 Cookies
            cookies_list = [{
                "name": k, "value": v, "domain": ".xiaohongshu.com", "path": "/",
                "httpOnly": False, "secure": False, "expires": int(time.time()) + 86400
            } for k, v in cookies.items()]

            await context_p.add_cookies(cookies_list)
            await asyncio.sleep(0.5)

            # 验证登录
            await page.goto("https://www.xiaohongshu.com", timeout=60000)
            await asyncio.sleep(1)

            is_logged_in = await self._check_login_status(page)
            logger.info(f"[xiaohongshu] Login status: {is_logged_in}")

            if not is_logged_in:
                raise ValueError("Login failed: cookies invalid or expired")

            return context_res.context.id

        finally:
            await self._cleanup_resources(session, browser)

    async def login_with_qrcode(
            self,
            source: str = "default",
            source_id: str = "default",
            timeout: int = 300
    ) -> Dict[str, Any]:
        """二维码登录小红书
        
        Args:
            source: 来源标识
            source_id: 来源ID（用于区分不同用户）
            timeout: 超时时间（秒），默认300秒
            
        Returns:
            {
                "success": True,
                "context_id": str,
                "qrcode": str,  # OSS 存储的二维码图片 URL
                "timeout": int,
                "message": str
            }
        """
        context_key = self._build_context_id(source, source_id)
        logger.info(f"[xiaohongshu] QRCode login with context_id: {context_key}")

        # 先检查是否已经登录（通过创建新会话验证）
        try:
            context_res = await self.agent_bay.context.get(context_key, create=False)
            if context_res.success and context_res.context:
                # 创建临时 session 验证登录状态
                verify_session_res = await self.agent_bay.create(
                    CreateSessionParams(
                        image_id="browser_latest",
                        browser_context=BrowserContext(context_res.context.id, auto_upload=False)
                    )
                )
                if verify_session_res.success:
                    verify_session = verify_session_res.session
                    browser_v = None
                    try:
                        await verify_session.browser.initialize(BrowserOption(
                            screen=BrowserScreen(width=1920, height=1080),
                            solve_captchas=True,
                            use_stealth=True,
                            fingerprint=BrowserFingerprint(
                                devices=["desktop"],
                                operating_systems=["windows"],
                                locales=self.get_locale(),
                            ),
                        ))
                        browser_v, context_v = await self._connect_cdp(verify_session)
                        page = await context_v.new_page()
                        
                        await page.goto("https://www.xiaohongshu.com", timeout=30000)
                        await asyncio.sleep(1)
                        
                        if await self._check_login_status(page):
                            # 验证成功，已登录
                            await self._cleanup_resources(verify_session, browser_v)
                            return {
                                "success": True,
                                "context_id": context_key,
                                "qrcode": "",
                                "timeout": 0,
                                "message": "Already logged in",
                                "is_logged_in": True
                            }
                        
                        # 未登录，继续执行下面的登录流程
                        logger.info("[xiaohongshu] Context exists but not logged in, starting new login")
                    except Exception as e:
                        logger.debug(f"[xiaohongshu] Verify login status error: {e}")
                    finally:
                        # 清理验证会话
                        if browser_v:
                            try:
                                await browser_v.close()
                            except:
                                pass
                        try:
                            await self.agent_bay.delete(verify_session, sync_context=False)
                        except:
                            pass
        except Exception as e:
            logger.debug(f"[xiaohongshu] Check existing context failed: {e}")

        # 创建新的登录 Session
        session_res = await self.agent_bay.create(
            CreateSessionParams(
                image_id="browser_latest"
            )
        )
        if not session_res.success:
            raise ValueError(f"Failed to create session: {session_res.error_message}")

        session = session_res.session
        browser = None

        try:
            await session.browser.initialize(BrowserOption(
                screen=BrowserScreen(width=1920, height=1080),
                solve_captchas=True,
                use_stealth=True,
                fingerprint=BrowserFingerprint(
                    devices=["desktop"],
                    operating_systems=["windows"],
                    locales=self.get_locale(),
                ),
            ))
            browser, context_p = await self._connect_cdp(session)
            page = await context_p.new_page()

            # 导航到小红书首页触发二维码
            await page.goto("https://www.xiaohongshu.com/explore", timeout=60000)
            await asyncio.sleep(2)

            # 检查是否已经登录
            if await self._check_login_status(page):
                logger.info("[xiaohongshu] Already logged in")
                await self._cleanup_resources(session, browser)
                return {
                    "success": True,
                    "context_id": context_key,
                    "qrcode": "",
                    "timeout": 0,
                    "message": "Already logged in",
                    "is_logged_in": True
                }

            # 获取二维码图片
            qrcode_url = await self._get_qrcode_image(page, source, source_id)
            if not qrcode_url:
                await self._cleanup_resources(session, browser)
                raise ValueError("Failed to get qrcode image")

            logger.info("[xiaohongshu] QRCode generated, waiting for scan...")

            # 启动后台任务等待扫码（不阻塞响应）
            asyncio.create_task(self._wait_for_login_and_save(
                session=session,
                browser=browser,
                page=page,
                context_key=context_key,
                timeout=timeout
            ))

            # 立即返回二维码（不等待扫码完成）
            return {
                "success": True,
                "context_id": context_key,
                "qrcode": qrcode_url,
                "timeout": timeout,
                "message": "QRCode generated, waiting for scan",
                "is_logged_in": False
            }

        except Exception as e:
            logger.error(f"[xiaohongshu] QRCode login failed: {e}")
            await self._cleanup_resources(session, browser)
            raise

    async def _wait_for_login_and_save(
            self,
            session: Any,
            browser: Any,
            page: Page,
            context_key: str,
            timeout: int
    ):
        """后台任务：等待扫码登录并保存到 Context"""
        logger.info(f"[xiaohongshu] Background task: waiting for login (timeout={timeout}s)")
        
        try:
            # 每 5 秒检查一次登录状态
            for i in range(timeout // 5):
                try:
                    if await self._check_login_status(page):
                        logger.info("[xiaohongshu] Login successful! Saving cookies to context...")
                        
                        # 登录成功，保存到 Context
                        context_res = await self.agent_bay.context.get(context_key, create=True)
                        if context_res.success:
                            # 关闭浏览器时自动同步 cookies 到 context
                            await self._cleanup_resources(session, browser)
                            logger.info(f"[xiaohongshu] Cookies saved to context: {context_key}")
                        else:
                            logger.error(f"[xiaohongshu] Failed to get context: {context_res.error_message}")
                            await self._cleanup_resources(session, browser)
                        return
                except Exception as e:
                    error_msg = str(e)
                    # 如果是 Session 失效错误，直接退出
                    if "no alive session" in error_msg or "SessionHandleError" in error_msg:
                        logger.warning(f"[xiaohongshu] Session no longer alive, stopping login wait")
                        return
                    logger.warning(f"[xiaohongshu] Check login status error: {e}")
                
                await asyncio.sleep(5)
            
            # 超时
            logger.warning(f"[xiaohongshu] Login timeout after {timeout}s")
            await self._cleanup_resources(session, browser)
            
        except Exception as e:
            logger.error(f"[xiaohongshu] Background login task error: {e}")
            await self._cleanup_resources(session, browser)

    async def _get_qrcode_image(self, page: Page, source: str = "default", source_id: str = "default") -> Optional[str]:
        """获取二维码图片并上传到OSS
        
        Args:
            page: Playwright页面对象
            source: 来源标识
            source_id: 来源ID
            
        Returns:
            OSS存储的二维码图片URL
        """
        try:
            # 等待二维码元素出现
            await page.wait_for_selector(".login-container .qrcode-img", timeout=10000)
            
            screenshot_bytes = None
            
            # 方法1: 尝试从 img src 获取
            qrcode_elem = await page.query_selector(".login-container .qrcode-img")
            if qrcode_elem:
                src = await qrcode_elem.get_attribute("src")
                if src and src.startswith("data:image"):
                    logger.info("[xiaohongshu] Got QRCode from img src")
                    # 解析 base64 数据
                    if "," in src:
                        screenshot_bytes = base64.b64decode(src.split(",")[1])
            
            # 方法2: 如果 src 是 URL，则截图获取
            if qrcode_elem and not screenshot_bytes:
                # 截取二维码区域
                bbox = await qrcode_elem.bounding_box()
                if bbox:
                    # 等待二维码完全加载
                    await asyncio.sleep(0.5)
                    
                    # 截图整个二维码区域
                    screenshot_bytes = await page.screenshot(clip={
                        "x": bbox["x"],
                        "y": bbox["y"],
                        "width": bbox["width"],
                        "height": bbox["height"]
                    })
                    logger.info("[xiaohongshu] Got QRCode from screenshot")
            
            if not screenshot_bytes:
                logger.error("[xiaohongshu] Failed to get QRCode")
                return None
            
            # 生成唯一的文件名：source+sourceid+xiaohongshu-qrcode
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"qrcodes/{source}-{source_id}-xiaohongshu-qrcode-{timestamp}.png"
            
            # 上传到 OSS
            try:
                qrcode_url = await oss_client.upload_and_get_url(filename, screenshot_bytes)
                logger.info(f"[xiaohongshu] QRCode uploaded to OSS: {qrcode_url}")
                return qrcode_url
            except Exception as e:
                logger.error(f"[xiaohongshu] Failed to upload QRCode to OSS: {e}")
                # 降级：返回 base64
                b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                return f"data:image/png;base64,{b64}"
            
        except Exception as e:
            logger.error(f"[xiaohongshu] Get qrcode error: {e}")
            return None

    async def _check_login_status(self, page: Page) -> bool:
        """检查是否已登录"""
        try:
            # 等待页面加载
            await page.wait_for_selector("body", timeout=10000)
            
            # 检查登录成功的元素
            element = await page.query_selector('.main-container .user .link-wrapper .channel')
            return bool(element)
        except Exception as e:
            logger.debug(f"[xiaohongshu] Check login status error: {e}")
            return False

    async def publish_content(
            self,
            content: str,
            content_type: str = "text",
            images: Optional[List[str]] = None,
            tags: Optional[List[str]] = None,
            source: str = "default",
            source_id: str = "default"
    ) -> Dict[str, Any]:
        """发布内容"""
        session = await self._get_browser_session(source, source_id)
        browser = None
        try:
            browser, context = await self._connect_cdp(session)
            page = await context.new_page()

            await page.goto("https://creator.xiaohongshu.com/publish/publish", timeout=60000)
            await asyncio.sleep(2)

            # 构建 Agent 指令
            tag_str = ', '.join(tags or [])
            if content_type == "image" and images:
                instruction = f"发布图文笔记：内容「{content}」，上传图片：{', '.join(images)}，添加标签：{tag_str}"
            elif content_type == "video":
                instruction = f"发布视频笔记：内容「{content}」，添加标签：{tag_str}"
            else:
                instruction = f"发布文字笔记：内容「{content}」，添加标签：{tag_str}"

            success = await session.browser.agent.act_async(
                ActOptions(action=instruction),
                page=page
            )

            return {
                "success": success,
                "content": content,
                "platform": self.platform_name_str
            }
        finally:
            await self._cleanup_resources(session, browser)

    # ==================== 业务逻辑：提取与监控 (使用通用批处理) ====================

    async def extract_summary_stream(
            self,
            urls: List[str],
            concurrency: int = 1,
            source: str = "default",
            source_id: str = "default",
            extra: Optional[Dict[str, Any]] = None
    ):
        """流式提取并使用 Agent 分析"""

        async def _process(url: str, idx: int, context: Any, session: Any):
            logger.info(f"[xiaohongshu] Analyzing URL {idx + 1}: {url}")
            page = await context.new_page()
            try:
                await page.goto(url, timeout=60000)
                await asyncio.sleep(2)

                # 关闭可能的弹窗
                try:
                    await session.browser.agent.act_async(
                        ActOptions(action="如果有弹窗或登录提示，关闭它们。"), page=page
                    )
                except:
                    pass

                note_data = await self._get_note_detail_evaluate(page)

                if note_data:
                    # 构建 Prompt 让 Agent 分析
                    prompt = self._build_analysis_prompt(note_data)
                    try:
                        analysis_res = await session.browser.agent.run(prompt)
                        analysis_text = analysis_res if isinstance(analysis_res, str) else str(analysis_res)

                        return {
                            "url": url,
                            "success": True,
                            "data": {"note_data": note_data, "analysis": analysis_text},
                            "method": "agent_analysis"
                        }
                    except Exception as e:
                        return {"url": url, "success": False, "error": f"Agent analysis failed: {e}"}
                else:
                    return {"url": url, "success": False, "error": "Failed to extract note data"}
            finally:
                await page.close()

        # 调用通用批处理
        async for result in self._batch_execute(urls, _process, concurrency, source, source_id):
            yield result

    async def harvest_user_content(
            self,
            creator_ids: List[str],
            limit: Optional[int] = None,
            source: str = "default",
            source_id: str = "default",
            concurrency: int = 2
    ) -> List[Dict[str, Any]]:
        """批量抓取创作者笔记"""

        async def _process(creator_id: str, idx: int, context: Any, session: Any):
            logger.info(f"[xiaohongshu] Harvesting creator {idx + 1}: {creator_id}")
            page = await context.new_page()
            try:
                await page.goto(f"https://www.xiaohongshu.com/user/profile/{creator_id}", timeout=60000)
                await asyncio.sleep(1)

                # 提取 Initial State
                raw_data = await self._extract_initial_state(page, "user.notes")
                if not raw_data:
                    return {"creator_id": creator_id, "success": False, "error": "No notes found"}

                # 解析数据
                all_feeds = []
                for feed_group in raw_data:  # notes 是个数组的数组
                    if feed_group: all_feeds.extend(feed_group)

                parsed_notes = [self._parse_feed_item(item) for item in all_feeds]
                if limit:
                    parsed_notes = parsed_notes[:limit]

                return {"creator_id": creator_id, "success": True, "data": parsed_notes}
            finally:
                await page.close()

        results = []
        async for result in self._batch_execute(creator_ids, _process, concurrency, source, source_id):
            results.append(result)
        return results

    async def get_note_detail(
            self,
            urls: List[str],
            source: str = "default",
            source_id: str = "default",
            concurrency: int = 2
    ) -> List[Dict[str, Any]]:
        """批量获取笔记详情"""

        async def _process(url: str, idx: int, context: Any, session: Any):
            logger.info(f"[xiaohongshu] Extracting detail {idx + 1}: {url}")
            page = await context.new_page()
            try:
                await page.goto(url, timeout=60000)
                await asyncio.sleep(0.5)

                data = await self._get_note_detail_evaluate(page)
                return {
                    "url": url,
                    "success": bool(data),
                    "data": data or {},
                    "method": "evaluate_extraction"
                }
            finally:
                await page.close()

        results = []
        async for result in self._batch_execute(urls, _process, concurrency, source, source_id):
            results.append(result)
        return results

    async def search_and_extract(
            self,
            keywords: List[str],
            limit: int = 20,
            user_id: Optional[str] = None,
            source: str = "default",
            source_id: str = "default",
            concurrency: int = 2
    ) -> List[Dict[str, Any]]:
        """批量搜索"""

        async def _process(keyword: str, idx: int, context: Any, session: Any):
            logger.info(f"[xiaohongshu] Searching keyword {idx + 1}: {keyword}")
            page = await context.new_page()
            try:
                url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}"
                await page.goto(url, timeout=60000)
                await asyncio.sleep(2)

                # 注入 JS 提取搜索结果
                script = self._get_search_extract_script(user_id)
                results = await page.evaluate(script)

                return {
                    "keyword": keyword,
                    "success": bool(results),
                    "data": results or []
                }
            finally:
                await page.close()

        results = []
        async for result in self._batch_execute(keywords, _process, concurrency, source, source_id):
            results.append(result)
        return results

    # ==================== 底层数据提取与辅助方法 (私有) ====================

    async def _extract_initial_state(self, page: Page, key_path: str) -> Optional[Any]:
        """通用的 __INITIAL_STATE__ 提取器"""
        keys = key_path.split('.')
        js_check = " && ".join([f"window.__INITIAL_STATE__{'.' + '.'.join(keys[:i + 1])}" for i in range(len(keys))])

        script = f"""
        () => {{
            if (window.__INITIAL_STATE__ && {js_check}) {{
                const target = window.__INITIAL_STATE__.{key_path};
                return target.value !== undefined ? target.value : target._value;
            }}
            return null;
        }}
        """
        for _ in range(3):
            data = await page.evaluate(script)
            if data: return data
            await asyncio.sleep(0.3)
        return None

    async def _get_note_detail_evaluate(self, page: Page) -> Optional[Dict]:
        """从页面提取详情结构化数据 - 扁平化友好结构"""
        try:
            await page.wait_for_selector("body", timeout=30000)

            # 获取 noteDetailMap，包含 Note 和 Comments
            data_json = await page.evaluate("""
                () => {
                    if (window.__INITIAL_STATE__ &&
                        window.__INITIAL_STATE__.note &&
                        window.__INITIAL_STATE__.note.noteDetailMap) {
                        const noteDetailMap = window.__INITIAL_STATE__.note.noteDetailMap;
                        return JSON.stringify(noteDetailMap);
                    }
                    return "";
                }
            """)

            if not data_json:
                logger.warning(f"[xiaohongshu] No noteDetailMap found")
                return None

            note_detail_map = json.loads(data_json)
            if not note_detail_map:
                return None

            # 获取第一个笔记的详情
            first_entry = list(note_detail_map.values())[0]
            note = first_entry.get("note", {})
            comments_data = first_entry.get("comments", {})

            # 提取评论列表
            comments_list = comments_data.get("list", []) if isinstance(comments_data, dict) else []

            # 扁平化用户信息
            user = note.get("user", {})
            interact_info = note.get("interactInfo", {})

            # 扁平化图片列表，只保留核心字段
            image_list = note.get("imageList", [])
            images = [{
                "url": img.get("urlDefault", ""),
                "width": img.get("width", 0),
                "height": img.get("height", 0)
            } for img in image_list]

            # 扁平化标签列表
            tag_list = note.get("tagList", [])
            tags = [tag.get("name", "") for tag in tag_list if tag.get("name")]

            # 扁平化评论
            comments = [{
                "content": c.get("content", ""),
                "user_nickname": c.get("userInfo", {}).get("nickname", ""),
                "likes": c.get("likeCount", "0"),
                "time": c.get("createTime", "")
            } for c in comments_list[:50]]

            # 处理时间字段
            time_timestamp = note.get("time", "")
            update_time = ""
            if time_timestamp:
                try:
                    from datetime import datetime
                    dt = datetime.fromtimestamp(time_timestamp / 1000)
                    update_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    update_time = str(time_timestamp)

            result = {
                "note_id": note.get("noteId"),
                "title": note.get("title", ""),
                "desc": note.get("desc", ""),
                "type": note.get("type", ""),
                "time": time_timestamp,
                "update_time": update_time,
                # 用户信息扁平化
                "user_id": user.get("userId", ""),
                "user_nickname": user.get("nickname", ""),
                "user_avatar": user.get("avatar", ""),
                # 互动数据扁平化
                "liked_count": int(interact_info.get("likedCount", 0)),
                "collected_count": int(interact_info.get("collectedCount", 0)),
                "comment_count": int(interact_info.get("commentCount", 0)),
                "share_count": int(interact_info.get("shareCount", 0)),
                # 扁平化的图片、标签、评论
                "images": images,
                "tags": tags,
                "comments": comments
            }

            logger.info(f"[xiaohongshu] Extracted note: {result.get('title')[:30]}, {len(images)} images, {len(comments)} comments")
            return result

        except Exception as e:
            logger.error(f"[xiaohongshu] Evaluate details failed: {e}")
            return None

    def _parse_feed_item(self, feed: Dict) -> Dict:
        """解析单个 Feed 条目"""
        card = feed.get("noteCard", {})
        note_id = feed.get("id")
        xsec_token = feed.get("xsecToken", "")
        
        base_url = f"https://www.xiaohongshu.com/explore/{note_id}"
        full_url = base_url
        if xsec_token:
            full_url = f"{base_url}?xsec_token={xsec_token}&xsec_source=pc_feed"
        
        return {
            "note_id": note_id,
            "title": card.get("displayTitle", ""),
            "url": base_url,
            "full_url": full_url,
            "liked_count": card.get("interactInfo", {}).get("likedCount", "0"),
            "cover": card.get("cover", {}).get("urlDefault", ""),
            "user": {
                "id": card.get("user", {}).get("userId"),
                "name": card.get("user", {}).get("nickname")
            }
        }

    def _build_analysis_prompt(self, note_data: Dict) -> str:
        interact = note_data.get('interact_info', {})
        tags = [t.get('name', '') for t in note_data.get('tag_list', [])]
        return f"""请分析这篇小红书笔记：
        标题: {note_data.get('title')}
        内容: {note_data.get('desc')}
        互动: 点赞 {interact.get('liked_count', 0)}, 收藏 {interact.get('collected_count', 0)}
        标签: {', '.join(tags)}

        请简要分析：1.核心观点 2.受众群体 3.爆款原因。"""

    def _get_search_extract_script(self, filter_user_id: Optional[str]) -> str:
        """生成搜索提取的 JS 脚本"""
        return f"""
        () => {{
            const results = [];
            const filterId = {f"'{filter_user_id}'" if filter_user_id else 'null'};

            if (window.__INITIAL_STATE__?.search?.feeds?.value) {{
                const feeds = window.__INITIAL_STATE__.search.feeds.value;
                for (const feed of feeds) {{
                    if (!feed.noteCard) continue;
                    if (filterId && feed.noteCard.user?.userId !== filterId) continue;

                    const noteId = feed.id;
                    const xsecToken = feed.xsecToken || '';
                    const baseUrl = `https://www.xiaohongshu.com/explore/${{noteId}}`;
                    let fullUrl = baseUrl;
                    if (xsecToken) {{
                        fullUrl = `${{baseUrl}}?xsec_token=${{xsecToken}}&xsec_source=pc_feed`;
                    }}

                    results.push({{
                        note_id: noteId,
                        title: feed.noteCard.displayTitle,
                        url: baseUrl,
                        full_url: fullUrl,
                        type: feed.noteCard.type,
                        cover: feed.noteCard.cover?.urlDefault || '',
                        liked_count: feed.noteCard.interactInfo?.likedCount || 0,
                        collected_count: feed.noteCard.interactInfo?.collectedCount || 0,
                        comment_count: feed.noteCard.interactInfo?.commentCount || 0,
                        user_id: feed.noteCard.user?.userId || '',
                        user_nickname: feed.noteCard.user?.nickname || '',
                        user_avatar: feed.noteCard.user?.avatar || ''
                    }});
                }}
            }}
            return results;
        }}
        """