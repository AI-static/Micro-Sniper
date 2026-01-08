# -*- coding: utf-8 -*-
"""抖音连接器 - 使用 session + browser + agent 方式"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from .base import BaseConnector
from utils.logger import logger
from utils.oss import oss_client
from agentbay import ActOptions, ExtractOptions, CreateSessionParams, BrowserContext, BrowserOption, BrowserScreen, BrowserFingerprint
from models.connectors import PlatformType

class CheckLoginStatus(BaseModel):
    """搜索结果模型"""
    has_login: bool = Field(description="是否已经登陆")

class SearchItems(BaseModel):
    """搜索结果模型"""
    title: str = Field(description="视频标题")
    url: str = Field(description="视频链接")
    author: str = Field(description="作者昵称")
    liked_count: str = Field(description="点赞数")

class CreatorsItems(BaseModel):
    """搜索结果模型"""
    user_id: str = Field(description="抖音号")
    author: str = Field(description="作者昵称")
    fans_count: int = Field(description="粉丝数,单位(个)")

class CreatorsResult(BaseModel):
    """搜索结果模型"""
    items: List[CreatorsItems] = Field(description="条目列表")


class SearchResult(BaseModel):
    items: List[SearchItems] = Field(description="条目列表")

class VideoDetail(BaseModel):
    """视频详情模型"""
    video_id: str = Field(description="视频ID")
    title: str = Field(description="视频标题")
    desc: str = Field(description="视频描述")
    author: str = Field(description="作者昵称")
    liked_count: str = Field(description="点赞数")
    comment_count: str = Field(description="评论数")
    share_count: str = Field(description="分享数")


class DouyinConnector(BaseConnector):
    """抖音连接器 - 使用 AgentBay session + browser + agent"""

    def __init__(self, playwright):
        super().__init__(platform_name=PlatformType.DOUYIN, playwright=playwright)
        self._login_tasks = {}

    async def search_and_extract(
        self,
        keywords: List[str],
        limit: int = 20,
        user_id: Optional[str] = None,
        source: str = "default",
        source_id: str = "default",
        concurrency: int = 2
    ) -> List[Dict[str, Any]]:
        """批量搜索抖音视频

        Args:
            keywords: 搜索关键词列表
            limit: 每个关键词限制结果数量
            user_id: 可选的用户ID过滤
            source: 来源标识
            source_id: 来源ID
            concurrency: 并发数

        Returns:
            List[Dict]: 搜索结果列表
        """

        async def _process(keyword: str, idx: int, session: Any):
            """处理单个关键词搜索"""
            logger.info(f"[douyin] Searching keyword {idx + 1}/{len(keywords)}: {keyword}")

            try:
                # 1. 导航到抖音首页
                nav_result = await session.browser.agent.navigate(
                    f"https://www.douyin.com/jingxuan/search/{creator_id}")
                await asyncio.sleep(2)

                # 2. 使用 Agent 搜索创作者
                search_act = ActOptions(
                    action=f"""
                                    1. 如果有弹窗，先关闭。
                                    2. 在标签页中点击用户。
                                    """,
                    use_vision=True
                )

                results = await session.browser.agent.act(search_act)
                logger.info(f"[douyin] Search user action: {results}")

                if not results.success:
                    return {
                        "creator_id": creator_id,
                        "success": False,
                        "data": "动作未成功"
                    }

                await asyncio.sleep(5)

                # 3. 提取用户主页
                extract_options = ExtractOptions(
                    instruction=f"""
                                    当前搜索到的用户有哪些，只输出前5个。
                                    """,
                    schema=CreatorsResult,
                    # use_text_extract=True,
                    use_vision=True
                )

                success, data = await session.browser.agent.extract(extract_options)

                if success and data and data.items:
                    results = [item.model_dump() if hasattr(item, 'model_dump') else item for item in data.items]
                    logger.info(f"[douyin] Harvested {len(results)} videos from {creator_id}")
                    return {
                        "creator_id": creator_id,
                        "success": True,
                        "data": results
                    }
                else:
                    logger.warning(f"[douyin] Failed to harvest from {creator_id}")
                    return {
                        "creator_id": creator_id,
                        "success": False,
                        "error": "Failed to extract user content",
                        "data": []
                    }

            except Exception as e:
                logger.error(f"[douyin] Error processing keyword '{keyword}': {e}")
                return {
                    "keyword": keyword,
                    "success": False,
                    "error": str(e),
                    "data": []
                }

        # 获取 session
        session = await self._get_browser_session(source, source_id)

        try:
            # 并发执行搜索
            semaphore = asyncio.Semaphore(concurrency)

            async def worker(keyword, idx):
                async with semaphore:
                    return await _process(keyword, idx, session)

            tasks = [asyncio.create_task(worker(kw, idx)) for idx, kw in enumerate(keywords)]
            results = await asyncio.gather(*tasks)

            return results

        finally:
            await self._cleanup_resources(session, None)

    async def get_note_detail(
        self,
        urls: List[str],
        source: str = "default",
        source_id: str = "default",
        concurrency: int = 2
    ) -> List[Dict[str, Any]]:
        """批量获取抖音视频详情

        Args:
            urls: 视频URL列表
            source: 来源标识
            source_id: 来源ID
            concurrency: 并发数

        Returns:
            List[Dict]: 视频详情列表
        """

        async def _process(url: str, idx: int, session: Any):
            """处理单个视频详情提取"""
            logger.info(f"[douyin] Extracting detail {idx + 1}/{len(urls)}: {url}")

            try:
                # 1. 导航到视频页面
                nav_result = await session.browser.agent.navigate(url)
                logger.info(f"[douyin] Navigated to video: {nav_result}")

                await asyncio.sleep(2)

                # 2. 使用 Agent 提取视频详情
                extract_options = ExtractOptions(
                    instruction="""
                    从当前抖音视频页面中提取以下信息：
                    1. 视频ID（如果有）
                    2. 视频标题
                    3. 视频描述/文案
                    4. 作者昵称
                    5. 点赞数
                    6. 评论数
                    7. 分享数

                    请尽可能准确地提取这些信息。
                    """,
                    schema=VideoDetail,
                    use_vision=True,
                    use_text_extract=True
                )

                success, data = await session.browser.agent.extract(extract_options)

                if success and data:
                    # 处理单条结果
                    detail = data.model_dump() if hasattr(data, 'model_dump') else data
                    logger.info(f"[douyin] Extracted detail: {detail.get('title', 'N/A')[:30]}")
                    return {
                        "url": url,
                        "success": True,
                        "data": detail
                    }
                else:
                    logger.warning(f"[douyin] Failed to extract detail for: {url}")
                    return {
                        "url": url,
                        "success": False,
                        "error": "Failed to extract video detail",
                        "data": {}
                    }

            except Exception as e:
                logger.error(f"[douyin] Error processing URL '{url}': {e}")
                return {
                    "url": url,
                    "success": False,
                    "error": str(e),
                    "data": {}
                }

        # 获取 session
        session = await self._get_browser_session(source, source_id)

        try:
            # 并发执行提取
            semaphore = asyncio.Semaphore(concurrency)

            async def worker(url, idx):
                async with semaphore:
                    return await _process(url, idx, session)

            tasks = [asyncio.create_task(worker(u, idx)) for idx, u in enumerate(urls)]
            results = await asyncio.gather(*tasks)

            return results

        finally:
            await self._cleanup_resources(session, None)

    async def harvest_user_content(
        self,
        creator_ids: List[str],
        limit: Optional[int] = None,
        source: str = "default",
        source_id: str = "default",
        concurrency: int = 2
    ) -> List[Dict[str, Any]]:
        """批量抓取创作者的视频内容

        Args:
            creator_ids: 创作者ID或昵称列表
            limit: 每个创作者限制视频数量
            source: 来源标识
            source_id: 来源ID
            concurrency: 并发数

        Returns:
            List[Dict]: 视频列表
        """

        async def _process(creator_id: str, idx: int, session: Any):
            """处理单个创作者的内容提取"""
            logger.info(f"[douyin] Harvesting content {idx + 1}/{len(creator_ids)}: {creator_id}")

            try:
                screenshot_url = []
                # 1. 导航到抖音首页
                nav_result = await session.browser.agent.navigate(f"https://www.douyin.com/jingxuan/search/{creator_id}?type=user")
                await asyncio.sleep(2)

                # 2. 使用 Agent 搜索创作者
                search_act = ActOptions(
                    action=f"""
                    1. 如果有弹窗，请关闭。
                    2. 点击第一个用户，进入其主页。
                    3. 滑动窗口到最下方。
                    """,
                    use_vision=True
                )

                results = await session.browser.agent.act(search_act)
                logger.info(f"[douyin] Search user action: {results}")

                if not results.success:
                    return {
                        "creator_id": creator_id,
                        "success": False,
                        "data": "动作未成功"
                    }

                await asyncio.sleep(5)

                screenshot_b64 = await session.browser.agent.screenshot()
                object_name = f"抖音获取用户视频截图留证-{int(time.time())}"
                await oss_client.upload_file(object_name=object_name, file_data=screenshot_b64)
                screenshot_url.append(oss_client.get_public_url(object_name))

                # 3. 提取用户主页
                extract_options = ExtractOptions(
                    instruction=f"""
                    当前用户的视频信息有哪些，只输出前{limit}个。
                    """,
                    schema=SearchResult,
                    use_text_extract=True,
                    use_vision=True
                )

                success, data = await session.browser.agent.extract(extract_options)

                if success and data and data.items:
                    results = [item.model_dump() if hasattr(item, 'model_dump') else item for item in data.items]
                    logger.info(f"[douyin] Harvested {len(results)} videos from {creator_id}")
                    return {
                        "screenshot_url": screenshot_url,
                        "creator_id": creator_id,
                        "success": True,
                        "data": results
                    }
                else:
                    logger.warning(f"[douyin] Failed to harvest from {creator_id}")
                    return {
                        "screenshot_url": screenshot_url,
                        "creator_id": creator_id,
                        "success": False,
                        "error": "Failed to extract user content",
                        "data": []
                    }

            except Exception as e:
                logger.error(f"[douyin] Error harvesting from '{creator_id}': {e}")
                return {
                    "creator_id": creator_id,
                    "success": False,
                    "error": str(e),
                    "data": []
                }

        # 获取 session
        session = await self._get_browser_session(source, source_id)

        try:
            # 并发执行采收
            semaphore = asyncio.Semaphore(concurrency)

            async def worker(creator_id, idx):
                async with semaphore:
                    return await _process(creator_id, idx, session)

            tasks = [asyncio.create_task(worker(cid, idx)) for idx, cid in enumerate(creator_ids)]
            results = await asyncio.gather(*tasks)

            return results

        finally:
            await self._cleanup_resources(session, None)

    async def login_with_cookies(
        self,
        cookies: Dict[str, str],
        source: str = "default",
        source_id: str = "default"
    ) -> str:
        """使用 Cookie 登录抖音"""
        context_key = self._build_context_id(source, source_id)
        logger.info(f"[douyin] Logging in with context_id: {context_key}")

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
                "name": k, "value": v, "domain": ".douyin.com", "path": "/",
                "httpOnly": False, "secure": False, "expires": int(time.time()) + 86400
            } for k, v in cookies.items()]

            await context_p.add_cookies(cookies_list)
            await asyncio.sleep(0.5)

            # 验证登录
            await page.goto("https://www.douyin.com", timeout=60000)
            await asyncio.sleep(1)

            # 检查登录状态
            is_logged_in = await self._check_login_status_douyin(page)
            logger.info(f"[douyin] Login status: {is_logged_in}")

            if not is_logged_in:
                raise ValueError("Login failed: cookies invalid or expired")

            return context_res.context.id

        finally:
            await self._cleanup_resources(session, browser)

    async def _check_login_status_douyin(self, page) -> bool:
        """检查抖音登录状态"""
        try:
            # 检查是否有用户头像等登录标识
            await page.wait_for_selector(".login-btn", timeout=3000)
            # 如果找到登录按钮，说明未登录
            return False
        except:
            # 如果没找到登录按钮，说明已登录
            return True

    async def login_with_qrcode(
        self,
        source: str = "default",
        source_id: str = "default",
        timeout: int = 120
    ) -> Dict[str, Any]:
        """二维码登录抖音

        Args:
            source: 来源标识
            source_id: 来源ID
            timeout: 超时时间（秒）

        Returns:
            Dict: 包含二维码图片 URL 的字典
        """
        context_key = self._build_context_id(source, source_id)
        logger.info(f"[douyin] QRCode login with context_id: {context_key}")

        # 创建持久化 context
        context_result = await self.agent_bay.context.get(context_key, create=True)
        if not context_result.success:
            raise ValueError(f"Failed to create context: {context_result.error_message}")

        # 创建 session
        session_result = await self.agent_bay.create(
            CreateSessionParams(
                image_id="browser_latest",
                browser_context=BrowserContext(context_result.context.id, auto_upload=False)
            )
        )

        if not session_result.success:
            raise ValueError(f"Failed to create session: {session_result.error_message}")

        session = session_result.session

        try:
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

            # 导航到抖音登录页
            await session.browser.agent.navigate("https://www.douyin.com")
            await asyncio.sleep(1.5)
            extract_options = ExtractOptions(
                instruction="""查看此页面，看是否有用户头像等信息，判断其状态是否为登陆。""",
                use_vision=True,
                schema=CheckLoginStatus
            )

            success, data = await session.browser.agent.extract(extract_options)
            if success and data.has_login:
                return {
                    "success": True,
                    "context_id": context_key,
                    "message": "Has Logining"
                    }

            # 使用 Agent 找到并点击登录方式，显示二维码
            login_act = ActOptions(
                action="""
                1. 查找页面上的"登录"按钮并点击
                2. 在弹出的登录框中，选择"扫码登录"或"二维码登录"方式
                3. 确保二维码已显示在页面上
                """,
                use_vision=True
            )

            await session.browser.agent.act(login_act)
            await asyncio.sleep(2)

            # 获取二维码图片 URL
            qrcode_url = session.resource_url

            if not qrcode_url:
                raise ValueError("Failed to get QR code URL")

            logger.info(f"[douyin] QRCode generated, waiting for scan...")

            # 启动后台任务：等待扫码后优雅关闭
            task = asyncio.create_task(self._wait_and_cleanup_after_scan(
                session=session,
                browser=None,
                context_key=context_key,
                timeout=timeout
            ))

            # 存储登录任务信息（包含 session 和 browser）
            self._login_tasks[context_key] = {
                "session": session,
                "browser": None,
                "task": task,
                "context_key": context_key,
                "timeout": timeout
            }

            return {
                "success": True,
                "context_id": context_key,
                "qrcode": qrcode_url,
                "timeout": timeout,
                "message": "Cloud browser created, waiting for login",
                "is_logged_in": False
            }

        except Exception as e:
            logger.debug(f"[douyin] Check existing context failed: {e}")
            await self._cleanup_resources(verify_session, browser_v)
            await self.agent_bay.delete(verify_session, sync_context=False)

    async def _wait_and_cleanup_after_scan(
            self,
            session: Any,
            browser: Any,
            context_key: str,
            timeout: int = 120,
    ):
        """后台任务：等待指定秒数后优雅关闭并落盘上下文"""
        logger.info(f"[douyin] Background task: waiting {timeout}s before cleanup")

        try:
            # 直接等待指定秒数，让用户扫码并让页面完全稳定
            await asyncio.sleep(timeout)

            logger.info(f"[douyin] Saving context and cleaning up: {context_key}")

            # 优雅关闭浏览器，自动同步 cookies 到 context
            await self._cleanup_resources(session, browser)
            logger.info(f"[douyin] Context saved successfully")

        except Exception as e:
            logger.error(f"[douyin] Background task error: {e}")
            await self._cleanup_resources(session, browser)
        finally:
            # 清理 _login_tasks 中的记录
            if context_key in self._login_tasks:
                logger.info(f"[douyin] Cleaning up _login_tasks entry: {context_key}")
                del self._login_tasks[context_key]

