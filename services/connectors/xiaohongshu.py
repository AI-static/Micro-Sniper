# -*- coding: utf-8 -*-
"""小红书连接器 - 支持登录、提取、发布、监控"""

import asyncio
from typing import Dict, Any, List, Optional
from playwright.async_api import async_playwright, Page

from .base import BaseConnector
from utils.logger import logger
from utils.exceptions import ContextNotFoundException, SessionCreationException, BrowserInitializationException
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
        """获取平台名称字符串"""
        return self.platform_name.value

    def _build_context_id(self, source: str, source_id: str) -> str:
        """构建 context_id: xiaohongshu:{source}:{source_id}"""
        return f"{self.platform_name.value}-context:{source}-{source_id}"


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

        context_key = self._build_context_id(source, source_id)
        # 获取持久化 context
        context_result = await self.agent_bay.context.get(context_key, create=False)
        if not context_result.success or not context_result.context:
            raise ContextNotFoundException(f"Context '{context_key}' not found，请先登录")
        logger.info(f"context_result 存在 {context_key} :{context_result.context.id} {context_result.context.__dict__}")
        # 使用 context 创建 session
        session_result = await self.agent_bay.create(
            CreateSessionParams(
                image_id="browser_latest",
                # 这里的cntext要传真实的id
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
    

    # ==================== 私有方法 ====================

    async def _check_login_status(self, page) -> bool:
        """检查是否已登录"""
        try:
            # 等待页面加载
            await asyncio.sleep(1)
            
            # 使用和小红书MCP相同的选择器
            # 这个选择器更可靠，因为它检查的是用户频道的存在
            element = await page.query_selector('.main-container .user .link-wrapper .channel')
            
            if element:
                logger.info("[xiaohongshu] Login status: Logged in (found channel element)")
                return True
            else:
                logger.warning("[xiaohongshu] Login status: Not logged in (channel element not found)")
                return False
                
        except Exception as e:
            logger.error(f"[xiaohongshu] Error checking login status: {e}")
            return False

    def _process_note_detail(self, detail: dict) -> dict:
        """处理笔记详情的原始数据"""
        note = detail.get("note", {})
        user = note.get("user", {})
        interact_info = note.get("interactInfo", {})
        image_list = note.get("imageList", [])

        return {
            "note_id": note.get("noteId"),
            "title": note.get("title"),
            "desc": note.get("desc"),
            "type": note.get("type"),
            "time": note.get("time"),
            "user": {
                "user_id": user.get("userId"),
                "nickname": user.get("nickname") or user.get("nickName"),
                "avatar": user.get("avatar")
            },
            "interact_info": {
                "liked_count": interact_info.get("likedCount"),
                "comment_count": interact_info.get("commentCount"),
                "shared_count": interact_info.get("sharedCount"),
                "collected_count": interact_info.get("collectedCount")
            },
            "images": [
                {
                    "url": img.get("urlDefault"),
                    "width": img.get("width"),
                    "height": img.get("height")
                }
                for img in image_list
            ]
        }

    # ==================== 登陆和发布 ====================

    async def extract_summary_stream(
        self,
        urls: List[str],
        concurrency: int = 1,
        source: str = "default",
        source_id: str = "default",
        extra: Optional[Dict[str, Any]] = None
    ):
        """流式提取小红书帖子详情并总结分析（使用Agent进行分析），支持并发"""
        # 初始化一次 session 和 browser context，所有 URL 共享
        session = await self._get_browser_session(source, source_id)
        endpoint_url = await session.browser.get_endpoint_url()
        
        browser = await self.playwright.chromium.connect_over_cdp(endpoint_url)
        context = browser.contexts[0]

        try:
            # 创建信号量来限制并发数
            semaphore = asyncio.Semaphore(concurrency)

            async def extract_single_url(url: str, idx: int):
                """提取单个 URL（使用共享的 browser context）"""
                async with semaphore:
                    logger.info(f"[xiaohongshu] Processing URL {idx}/{len(urls)}: {url}")

                    page = None
                    try:
                        # 在共享的 context 中创建新 page
                        page = await context.new_page()
                        await page.goto(url, timeout=60000)
                        await asyncio.sleep(2)

                        # 关闭可能出现的弹窗
                        try:
                            agent_browser = session.browser.agent
                            await agent_browser.act_async(
                                ActOptions(action="如果有弹窗或登录提示，关闭它们，然后滚动到笔记底部查看完整内容。"),
                                page=page
                            )
                        except:
                            pass

                        # 使用get_note_detail方法获取结构化数据
                        note_data = await self._get_note_detail_evaluate(page)
                        
                        # 如果获取到了结构化数据，使用Agent进行总结分析
                        if note_data:
                            # 准备用于分析的内容
                            title = note_data.get("title", "")
                            desc = note_data.get("desc", "")
                            user_info = note_data.get("user", {})
                            interaction = note_data.get("interact_info", {})
                            tags = note_data.get("tag_list", [])
                            
                            # 构建分析提示
                            prompt = f"""请分析这篇小红书笔记：

                            标题: {title}
                            
                            内容: {desc}
                            
                            作者: {user_info.get('nickname', '未知')}
                            互动数据: 
                            - 点赞: {interaction.get('liked_count', 0)}
                            - 收藏: {interaction.get('collected_count', 0)}
                            - 评论: {interaction.get('comment_count', 0)}
                            - 分享: {interaction.get('shared_count', 0)}
                            
                            标签: {', '.join([tag.get('name', '') for tag in tags])}
                            
                            请从以下几个方面进行分析：
                            1. 内容主题和核心观点
                            2. 作者的写作风格和特点
                            3. 用户互动情况分析
                            4. 内容的热度和传播价值
                            5. 目标受众群体
                            6. 总结和建议
                            
                            请详细分析并提供有价值的见解。"""
                            
                            # 使用Agent进行内容分析和总结
                            analysis_result = ""
                            try:
                                # 使用session中的browser的agent
                                analysis_agent = session.browser.agent
                                # 生成分析结果
                                response = await analysis_agent.run(prompt)
                                analysis_result = response if isinstance(response, str) else str(response)
                            except Exception as e:
                                logger.error(f"[xiaohongshu] Agent分析失败: {e}")
                                analysis_result = f"分析失败：{str(e)}\n\n原始内容：\n标题：{title}\n内容：{desc}"
                            
                            result = {
                                "url": url,
                                "success": True,
                                "data": {
                                    "note_data": note_data,
                                    "analysis": analysis_result
                                },
                                "method": "agent_analysis"
                            }
                        else:
                            result = {
                                "url": url,
                                "success": False,
                                "error": "无法获取笔记内容"
                            }

                        logger.info(f"[xiaohongshu] Extracted summary for URL {idx}/{len(urls)}, success={result['success']}")

                        return result

                    except Exception as e:
                        logger.error(f"[xiaohongshu] Error extracting {url}: {e}")
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
            await self.agent_bay.delete(session, sync_context=False)


    async def login_with_cookies(self,
                                 cookies: Dict[str, str],
                                 source: str = "default",
                                 source_id: str = "default") -> str:
        """使用 Cookie 登录小红书

        Args:
            cookies: 登录的 cookies
            source: 系统标识，用于区分不同的系统
            source_id: 用户标识，用于区分不同用户

        Returns:
            str: 登录成功返回 context_id
        """
        import time

        context_key = self._build_context_id(source, source_id)
        logger.info(f"[xiaohongshu] Logging in with context_id: {context_key}")

        session = None

        try:
            # Step 1: 创建持久化 context
            logger.info(f"[xiaohongshu] Creating context '{context_key}'...")
            context_result = await self.agent_bay.context.get(context_key, create=True)

            if not context_result.success or not context_result.context:
                logger.error(f"[xiaohongshu] Failed to create context: {context_result.error_message}")
                raise ValueError("Failed to create context")

            context = context_result.context
            logger.info(f"[xiaohongshu] Context created with ID: {context.id}")

            # Step 2: 使用 context 创建 session
            session_result = await self.agent_bay.create(
                CreateSessionParams(
                    image_id="browser_latest",
                    browser_context=BrowserContext(context.id, auto_upload=True)
                )
            )

            if not session_result.success or not session_result.session:
                logger.error(f"[xiaohongshu] Failed to create session: {session_result.error_message}")
                raise ValueError("Failed to create session")

            session = session_result.session
            logger.info(f"[xiaohongshu] Session created with ID: {session.session_id}")

            # Step 3: 初始化浏览器并设置 cookies
            logger.info(f"[xiaohongshu] Initializing browser and setting cookies...")

            init_success = await session.browser.initialize(BrowserOption())
            if not init_success:
                logger.error(f"[xiaohongshu] Failed to initialize browser")
                raise ValueError("Failed to initialize browser")

            logger.info(f"[xiaohongshu] Browser initialized successfully")

            # 获取 endpoint URL
            endpoint_url = await session.browser.get_endpoint_url()
            if not endpoint_url:
                logger.error(f"[xiaohongshu] Failed to get browser endpoint URL")
                raise ValueError("Failed to get browser endpoint URL")

            logger.info(f"[xiaohongshu] Browser endpoint URL: {endpoint_url}")

            browser = None
            page = None
            try:
                browser = await self.playwright.chromium.connect_over_cdp(endpoint_url)
                cdp_session = await browser.new_browser_cdp_session()
                context_p = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = await context_p.new_page()

                # 转换 cookies 为 Playwright 格式
                cookies_list = []
                for name, value in cookies.items():
                    cookies_list.append({
                        "name": name,
                        "value": value,
                        "domain": ".xiaohongshu.com",
                        "path": "/",
                        "httpOnly": False,
                        "secure": False,
                        "expires": int(time.time()) + 3600 * 24
                    })
                await context_p.add_cookies(cookies_list)
                await asyncio.sleep(0.6)

                await page.goto("https://www.xiaohongshu.com", timeout=60000)
                await asyncio.sleep(0.6)

                logger.info(f"[xiaohongshu] Added {len(cookies_list)} cookies")

                cookies = await context_p.cookies()
                logger.info(f"[xiaohongshu] Added cookies---> {cookies} cookies")

                # 检查登录是否成功
                is_logged_in = await self._check_login_status(page)
                logger.info(f"[xiaohongshu] check_login_status {is_logged_in}")
                await cdp_session.send('Browser.close')
                await asyncio.sleep(2)

            except Exception as e:
                raise
            finally:
                if browser:
                    await browser.close()
                if page:
                    await page.close()

            # Step 4: 删除 session 并同步 context 以保存 cookies
            if not is_logged_in:
                raise ValueError("Login failed: invalid cookies")
            logger.info(f"[xiaohongshu] Login successful, saving session with context sync...")
            return context.id

        except Exception as e:
            logger.error(f"[xiaohongshu] Error during login: {e}")
            raise
        finally:
            delete_result = await self.agent_bay.delete(session, sync_context=True)

    async def publish_content(
            self,
            content: str,
            content_type: str = "text",
            images: Optional[List[str]] = None,
            tags: Optional[List[str]] = None,
            source: str = "default",
            source_id: str = "default"
    ) -> Dict[str, Any]:
        """发布内容到小红书"""
        session = await self._get_browser_session(source, source_id)
        endpoint_url = await session.browser.get_endpoint_url()
        
        browser = await self.playwright.chromium.connect_over_cdp(endpoint_url)
        context = browser.contexts[0]

        try:
            page = await context.new_page()
            await page.goto("https://creator.xiaohongshu.com/publish/publish", timeout=60000)
            await asyncio.sleep(2)

            # 构建发布指令
            if content_type == "image" and images:
                instruction = f"发布图文笔记：内容「{content}」，上传图片：{', '.join(images)}，添加标签：{', '.join(tags or [])}"
            elif content_type == "video":
                instruction = f"发布视频笔记：内容「{content}」，添加标签：{', '.join(tags or [])}"
            else:
                instruction = f"发布文字笔记：内容「{content}」，添加标签：{', '.join(tags or [])}"

            # 执行发布操作
            agent = session.browser.agent
            success = await agent.act_async(
                ActOptions(action=instruction),
                page=page
            )

            return {
                "success": success,
                "content": content,
                "content_type": content_type,
                "platform": str(PlatformType.XIAOHONGSHU)
            }

        finally:
            await self.agent_bay.delete(session, sync_context=True)



    # ==================== 多种查询方式的支持 ====================


    async def harvest_user_content(
            self,
            user_id: str,
            limit: Optional[int] = None,
            source: str = "default",
            source_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """采收用户的所有笔记

        Args:
            user_id: 用户ID
            limit: 限制数量

        Returns:
            笔记列表
        """
        logger.info(f"[xiaohongshu] Harvesting notes from user: {user_id}, limit={limit}")

        # 直接获取用户的笔记列表（已包含完整数据）
        return await self.extract_by_creator_id(user_id, limit=limit, source=source, source_id=source_id)

    async def extract_by_note_ids(
        self,
        note_ids: List[str],
        concurrency: int = 3
    ) -> List[Dict[str, Any]]:
        """通过笔记ID批量提取内容

        Args:
            note_ids: 笔记ID列表
            concurrency: 并发数

        Returns:
            提取结果列表
        """
        # 构建URL
        urls = [f"https://www.xiaohongshu.com/explore/{note_id}" for note_id in note_ids]

        logger.info(f"[xiaohongshu] Extracting {len(note_ids)} notes by IDs")
        return await self.get_note_detail(urls, concurrency)

    async def extract_by_creator_id(
        self,
        creator_id: str,
        limit: Optional[int] = None,
        source: str = "default",
        source_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """通过创作者ID提取其笔记

        Args:
            creator_id: 创作者ID
            limit: 限制提取数量

        Returns:
            笔记列表
        """
        logger.info(f"[xiaohongshu] Extracting notes from creator: {creator_id}, limit={limit}")

        session = await self._get_browser_session(source, source_id)
        endpoint_url = await session.browser.get_endpoint_url()

        browser = await self.playwright.chromium.connect_over_cdp(endpoint_url)
        cdp_session = await browser.new_browser_cdp_session()
        context = browser.contexts[0]

        try:
            page = await context.new_page()
            profile_url = f"https://www.xiaohongshu.com/user/profile/{creator_id}"
            await page.goto(profile_url, timeout=60000)

            for attempt in range(3):
                notes_json = await page.evaluate("""
                    () => {
                        if (window.__INITIAL_STATE__ &&
                            window.__INITIAL_STATE__.user &&
                            window.__INITIAL_STATE__.user.notes) {
                            const notes = window.__INITIAL_STATE__.user.notes;
                            const data = notes.value !== undefined ? notes.value : notes._value;
                            if (data) {
                                return JSON.stringify(data);
                            }
                        }
                        return "";
                    }
                """)
                if notes_json:
                    break
                await asyncio.sleep(0.3)

            if not notes_json:
                logger.warning(f"[xiaohongshu] No notes found for creator: {creator_id}")
                return []

            import json
            notes_feeds = json.loads(notes_json)

            all_feeds = []
            for feeds in notes_feeds:
                if feeds:
                    all_feeds.extend(feeds)

            if not all_feeds:
                logger.warning(f"[xiaohongshu] No feeds found for creator: {creator_id}")
                return []

            if limit:
                all_feeds = all_feeds[:limit]

            logger.info(f"[xiaohongshu] Found {len(all_feeds)} notes for creator: {creator_id}")

            results = []
            for feed in all_feeds:
                note_card = feed.get("noteCard", {})
                model_type = feed.get("modelType", "")

                note_id = feed.get("id")
                xsec_token = feed.get("xsecToken", "")
                xsec_source = feed.get("xsecSource", "pc_feed")

                data = {
                    "note_id": note_id,
                    "xsec_token": xsec_token,
                    "xsec_source": xsec_source,
                    "url": f"https://www.xiaohongshu.com/explore/{note_id}",
                    "full_url": f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source={xsec_source}",
                    "model_type": model_type,
                    "title": note_card.get("displayTitle", ""),
                }

                cover = note_card.get("cover", {})
                if cover:
                    image_url = cover.get("urlDefault") or cover.get("url")
                    if not image_url:
                        info_list = cover.get("infoList", [])
                        if info_list and len(info_list) > 0:
                            image_url = info_list[0].get("url", "")
                    data["image"] = image_url
                    data["cover"] = {
                        "width": cover.get("width"),
                        "height": cover.get("height"),
                        "url_default": cover.get("urlDefault"),
                        "url": cover.get("url"),
                        "url_pre": cover.get("urlPre"),
                    }

                interact_info = note_card.get("interactInfo", {})
                data["liked_count"] = interact_info.get("likedCount", "0")
                data["liked"] = interact_info.get("liked", False)

                user_info = note_card.get("user", {})
                if user_info:
                    data["user_id"] = user_info.get("userId")
                    data["nickname"] = user_info.get("nickname") or user_info.get("nickName")
                    data["avatar"] = user_info.get("avatar")

                video = note_card.get("video")
                if video and video.get("capa"):
                    data["video_duration"] = video["capa"].get("duration")

                results.append({
                    "success": True,
                    "data": data
                })

            return results

        finally:
            await cdp_session.send('Browser.close')
            await asyncio.sleep(2)
            await self.agent_bay.delete(session, sync_context=True)

    async def get_note_detail(
        self,
        urls: List[str],
        concurrency: int = 3,
        source: str = "default",
        source_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """获取单个笔记的详情（使用evaluate提取结构化数据）
        
        Args:
            urls: 链接集合
            concurrency: 并发数
        Returns:
            笔记详情
        """
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
                        await page.wait_for_load_state("networkidle", timeout=30000)
                        
                        # 使用_get_note_detail_evaluate方法提取笔记信息
                        note_data = await self._get_note_detail_evaluate(page)
                        
                        return {
                            "url": url,
                            "success": True if note_data else False,
                            "data": note_data or {},
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
            
            results = await asyncio.gather(*[extract_detail(url) for url in urls], return_exceptions=True)
            
        finally:
            await self.agent_bay.delete(session, sync_context=True)
        
        return results
    
    async def _get_note_detail_evaluate(self, page):
        """使用evaluate提取笔记详情，包含评论信息"""
        try:
            await page.wait_for_selector("body", timeout=30000)

            for attempt in range(3):
                result = await page.evaluate("""
                    () => {
                        const data = {};

                        if (window.__INITIAL_STATE__) {
                            if (window.__INITIAL_STATE__.note &&
                                window.__INITIAL_STATE__.note.noteDetailMap) {
                                data.noteDetailMap = window.__INITIAL_STATE__.note.noteDetailMap;
                            }
                            if (window.__INITIAL_STATE__.comments) {
                                data.comments = window.__INITIAL_STATE__.comments;
                            }
                        }

                        return Object.keys(data).length > 0 ? JSON.stringify(data) : "";
                    }
                """)

                if result:
                    import json
                    data = json.loads(result)
                    note_detail_map = data.get("noteDetailMap", {})
                    comments_data = data.get("comments", {})

                    if note_detail_map:
                        note_ids = list(note_detail_map.keys())
                        if note_ids:
                            note_id = note_ids[0]
                            note_detail = note_detail_map[note_id]
                            note = note_detail.get("note", {})

                            result_data = {
                                "note_id": note.get("noteId"),
                                "xsec_token": note.get("xsecToken"),
                                "title": note.get("title"),
                                "desc": note.get("desc"),
                                "type": note.get("type"),
                                "time": note.get("time"),
                                "ip_location": note.get("ipLocation"),
                                "user": note.get("user") or {},
                                "interact_info": note.get("interactInfo") or {},
                                "image_list": note.get("imageList") or [],
                                "video": note.get("video"),
                                "tag_list": note.get("tagList") or [],
                                "location": note.get("location") or {},
                                "at_user_list": note.get("atUserList") or []
                            }

                            # 添加评论信息
                            if comments_data:
                                comment_list = comments_data.get("list", [])
                                # 处理评论数据，添加更多结构化信息
                                processed_comments = []
                                for comment in comment_list[:100]:  # 最多取100条评论
                                    processed_comment = {
                                        "id": comment.get("id"),
                                        "note_id": comment.get("noteId"),
                                        "content": comment.get("content"),
                                        "like_count": comment.get("likeCount"),
                                        "create_time": comment.get("createTime"),
                                        "ip_location": comment.get("ipLocation"),
                                        "liked": comment.get("liked", False),
                                        "user_info": comment.get("userInfo") or {},
                                        "sub_comment_count": comment.get("subCommentCount"),
                                        "sub_comments": comment.get("subComments") or [],
                                        "show_tags": comment.get("showTags") or []
                                    }
                                    processed_comments.append(processed_comment)
                                
                                result_data["comments"] = processed_comments
                                result_data["comment_count"] = len(processed_comments)
                                result_data["comment_has_more"] = comments_data.get("hasMore", False)
                                result_data["comment_cursor"] = comments_data.get("cursor", "")

                            return result_data

                await asyncio.sleep(0.2)

            logger.warning("[xiaohongshu] Failed to extract note after 3 attempts")
            return None

        except Exception as e:
            logger.error(f"获取笔记详情失败: {e}")
            return None

    async def search_and_extract(
        self,
        keyword: str,
        limit: int = 20,
        user_id: Optional[str] = None,
        source: str = "default",
        source_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """搜索并提取小红书内容

        Args:
            keyword: 搜索关键词
            limit: 限制数量
            user_id: 可选，只搜索特定用户的笔记
        Returns:
            搜索结果（包含完整详情）
        """
        # 验证登录状态并获取 context_id
        logger.info(f"[xiaohongshu] Searching for: {keyword}, user_id: {user_id}")

        session = await self._get_browser_session(source, source_id)
        endpoint_url = await session.browser.get_endpoint_url()

        browser = await self.playwright.chromium.connect_over_cdp(endpoint_url)
        cdp_session = await browser.new_browser_cdp_session()

        context = browser.contexts[0]

        logger.info(f"[xiaohongshu] Context cookies count: {len(await context.cookies())}")

        try:
            page = await context.new_page()
            # 构建搜索URL
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}"
            await page.goto(search_url, timeout=30000)
            await asyncio.sleep(3)

            # 提取搜索结果（从小红书 MCP 的 __INITIAL_STATE__ 中提取）
            search_results = await page.evaluate(f"""
                () => {{
                    const results = [];
                    const filterUserId = {f'"{user_id}"' if user_id else 'null'};

                    // 从 __INITIAL_STATE__ 中获取搜索结果（参考小红书 MCP 实现）
                    if (window.__INITIAL_STATE__ &&
                        window.__INITIAL_STATE__.search &&
                        window.__INITIAL_STATE__.search.feeds) {{
                        const feeds = window.__INITIAL_STATE__.search.feeds;
                        const feedsData = feeds.value !== undefined ? feeds.value : feeds._value;

                        if (feedsData && Array.isArray(feedsData)) {{
                            for (const feed of feedsData) {{
                                const noteCard = feed.noteCard;
                                if (!noteCard) continue;

                                const user = noteCard.user || {{}};

                                // 如果指定了 user_id，只返回该用户的笔记
                                if (filterUserId && user.userId !== filterUserId) {{
                                    continue;
                                }}

                                const noteId = feed.id;
                                const xsecToken = feed.xsecToken;
                                const xsecSource = feed.xsecSource || 'pc_feed';
                                const fullUrl = `https://www.xiaohongshu.com/explore/${{noteId}}?xsec_token=${{xsecToken}}&xsec_source=${{xsecSource}}`;

                                // 提取互动数据（参考小红书 MCP 的 InteractInfo 结构）
                                const interactInfo = noteCard.interactInfo || {{}};
                                const likedCount = interactInfo.likedCount || '0';
                                const collectedCount = interactInfo.collectedCount || '0';
                                const commentCount = interactInfo.commentCount || '0';
                                const sharedCount = interactInfo.sharedCount || '0';

                                const userId = user.userId || '';
                                const nickname = user.nickname || user.nickName || '';
                                const avatar = user.avatar || '';

                                results.push({{
                                    note_id: noteId,
                                    xsecToken: xsecToken,
                                    xsecSource: xsecSource,
                                    url: `https://www.xiaohongshu.com/explore/${{noteId}}`,
                                    full_url: fullUrl,
                                    title: noteCard.displayTitle || '',
                                    image: noteCard.cover?.urlDefault || '',
                                    liked_count: likedCount,
                                    collected_count: collectedCount,
                                    comment_count: commentCount,
                                    shared_count: sharedCount,
                                    user_id: userId,
                                    nickname: nickname,
                                    avatar: avatar
                                }});
                            }}
                        }}
                    }}

                    return results;
                }}
            """)

            if not search_results:
                logger.warning(f"[xiaohongshu] No search results for: {keyword}")
                return []

            # 限制数量
            search_results = search_results[:limit]

            logger.info(f"[xiaohongshu] Found {len(search_results)} search results")

            return search_results

        finally:
            await cdp_session.send('Browser.close')
            await asyncio.sleep(2)
            await self.agent_bay.delete(session, sync_context=True)
