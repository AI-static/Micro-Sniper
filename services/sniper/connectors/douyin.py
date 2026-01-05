# -*- coding: utf-8 -*-
"""抖音连接器 - 使用 session + browser + agent 方式"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from .base import BaseConnector
from utils.logger import logger
from agentbay import ActOptions, ExtractOptions, CreateSessionParams, BrowserContext, BrowserOption, BrowserScreen, BrowserFingerprint
from models.connectors import PlatformType


class SearchResult(BaseModel):
    """搜索结果模型"""
    title: str = Field(description="视频标题")
    url: str = Field(description="视频链接")
    author: str = Field(description="作者昵称")
    liked_count: str = Field(description="点赞数")


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
                nav_result = await session.browser.agent.navigate("https://www.douyin.com")
                logger.info(f"[douyin] Navigated to douyin: {nav_result}")

                await asyncio.sleep(2)

                # 2. 使用 Agent 查找搜索框并输入关键词
                search_act = ActOptions(
                    action=f"""
                    1. 如果页面有登录弹窗或广告弹窗，先关闭它们
                    2. 找到页面顶部的搜索框（通常有放大镜图标或"搜索"文字）
                    3. 点击搜索框
                    4. 输入关键词：{keyword}
                    5. 按回车键执行搜索
                    """,
                    use_vision=True
                )

                act_result = await session.browser.agent.act(search_act)
                logger.info(f"[douyin] Search action completed: {act_result}")

                # 3. 等待搜索结果加载
                await asyncio.sleep(3)

                # 4. 使用 Agent 提取搜索结果
                extract_options = ExtractOptions(
                    instruction=f"""
                    从当前抖音搜索结果页面中提取前 {limit} 个视频信息：
                    1. 视频标题
                    2. 视频链接（以 /video/ 开头的相对路径或完整 URL）
                    3. 作者昵称
                    4. 点赞数（如果有）

                    只返回列表中的视频信息，不要返回广告或其他无关内容。
                    """,
                    schema=SearchResult,
                    use_text_extract=True
                )

                success, data = await session.browser.agent.extract(extract_options)

                if success and data:
                    # 将 Pydantic 模型转换为字典
                    results = [item.model_dump() if hasattr(item, 'model_dump') else item for item in data]
                    logger.info(f"[douyin] Extracted {len(results)} results for keyword: {keyword}")
                    return {
                        "keyword": keyword,
                        "success": True,
                        "data": results
                    }
                else:
                    logger.warning(f"[douyin] Failed to extract results for keyword: {keyword}")
                    return {
                        "keyword": keyword,
                        "success": False,
                        "error": "Failed to extract search results",
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
        session = await self._get_session(source, source_id)

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
            # 清理 session
            try:
                await self.agent_bay.delete(session, sync_context=True)
            except Exception as e:
                logger.error(f"[douyin] Error cleaning up session: {e}")

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
        session = await self._get_session(source, source_id)

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
            # 清理 session
            try:
                await self.agent_bay.delete(session, sync_context=True)
            except Exception as e:
                logger.error(f"[douyin] Error cleaning up session: {e}")

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
                # 1. 导航到抖音首页
                nav_result = await session.browser.agent.navigate("https://www.douyin.com")
                await asyncio.sleep(2)

                # 2. 使用 Agent 搜索创作者
                search_act = ActOptions(
                    action=f"""
                    1. 如果有弹窗，先关闭
                    2. 找到并点击搜索框
                    3. 输入创作者名称或ID：{creator_id}
                    4. 按回车搜索
                    5. 在搜索结果中找到"用户"或"创作者"标签
                    6. 点击该标签查看用户列表
                    7. 点击第一个匹配的用户进入主页
                    """,
                    use_vision=True
                )

                act_result = await session.browser.agent.act(search_act)
                logger.info(f"[douyin] Search user action: {act_result}")

                await asyncio.sleep(3)

                # 3. 提取用户主页的视频列表
                max_videos = limit or 20
                extract_options = ExtractOptions(
                    instruction=f"""
                    从当前抖音用户主页中提取视频列表：
                    1. 提取前 {max_videos} 个视频
                    2. 每个视频包括：标题、链接、点赞数

                    只返回视频列表，不要返回其他内容。
                    """,
                    schema=SearchResult,
                    use_text_extract=True
                )

                success, data = await session.browser.agent.extract(extract_options)

                if success and data:
                    results = [item.model_dump() if hasattr(item, 'model_dump') else item for item in data]
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
                logger.error(f"[douyin] Error harvesting from '{creator_id}': {e}")
                return {
                    "creator_id": creator_id,
                    "success": False,
                    "error": str(e),
                    "data": []
                }

        # 获取 session
        session = await self._get_session(source, source_id)

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
            # 清理 session
            try:
                await self.agent_bay.delete(session, sync_context=True)
            except Exception as e:
                logger.error(f"[douyin] Error cleaning up session: {e}")

    async def login_with_cookies(
        self,
        cookies: Dict[str, str],
        source: str = "default",
        source_id: str = "default"
    ) -> str:
        """使用 Cookie 登录抖音

        Args:
            cookies: Cookie 字典
            source: 来源标识
            source_id: 来源ID

        Returns:
            str: context_id
        """
        context_key = self._build_context_id(source, source_id)
        logger.info(f"[douyin] Logging in with context_id: {context_key}")

        # 创建持久化 context
        context_result = await self.agent_bay.context.get(context_key, create=True)
        if not context_result.success:
            raise ValueError(f"Failed to create context: {context_result.error_message}")

        # 使用 context 创建 session
        session_result = await self.agent_bay.create(
            CreateSessionParams(
                image_id="browser_latest",
                browser_context=BrowserContext(context_result.context.id, auto_upload=True)
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

            # 使用 Agent 注入 Cookie
            cookies_list = [
                {"name": k, "value": v, "domain": ".douyin.com", "path": "/"}
                for k, v in cookies.items()
            ]

            # 通过 Agent 注入 cookies（使用 JavaScript）
            inject_act = ActOptions(
                action=f"""
                为当前页面注入以下 cookies：
                {json.dumps(cookies_list, ensure_ascii=False)}

                使用 document.cookie 注入每个 cookie，然后刷新页面。
                """,
                use_vision=False
            )

            await session.browser.agent.act(inject_act)
            await asyncio.sleep(2)

            # 导航到抖音首页验证登录
            await session.browser.agent.navigate("https://www.douyin.com")
            await asyncio.sleep(3)

            logger.info(f"[douyin] Login completed with context_id: {context_key}")
            return context_key

        except Exception as e:
            logger.error(f"[douyin] Login failed: {e}")
            await self.agent_bay.delete(session, sync_context=False)
            raise

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
                browser_context=BrowserContext(context_result.context.id, auto_upload=True)
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
            await asyncio.sleep(2)

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

            # 启动后台任务：等待扫码后保存 context
            async def wait_and_cleanup():
                try:
                    await asyncio.sleep(timeout)
                    logger.info(f"[douyin] Saving context after {timeout}s")
                    await self.agent_bay.delete(session, sync_context=True)
                    logger.info(f"[douyin] Context saved successfully")
                except Exception as e:
                    logger.error(f"[douyin] Background task error: {e}")

            asyncio.create_task(wait_and_cleanup())

            return {
                "success": True,
                "context_id": context_key,
                "qrcode": qrcode_url,
                "timeout": timeout,
                "message": "QRCode generated, waiting for scan"
            }

        except Exception as e:
            logger.error(f"[douyin] QRCode login failed: {e}")
            await self.agent_bay.delete(session, sync_context=False)
            raise