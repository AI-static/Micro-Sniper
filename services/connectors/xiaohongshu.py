# -*- coding: utf-8 -*-
"""小红书连接器 - 支持登录、提取、发布、监控"""

import asyncio
from typing import Dict, Any, List, Optional
from playwright.async_api import async_playwright, Page

from .base import BaseConnector
from utils.logger import logger
from agentbay.browser.browser_agent import ActOptions
from models.connectors import PlatformType


class XiaohongshuConnector(BaseConnector):
    """小红书连接器"""

    def __init__(self):
        super().__init__(platform_name=PlatformType.XIAOHONGSHU)
    
        
    def _get_summary_config(self) -> Dict[str, Any]:
        """获取小红书摘要提取的配置"""
        return {
            "title_selectors": [
                ".title",
                "h1",
                "h2",
                "[class*='title']"
            ],
            "content_selectors": [
                ".desc",
                ".content",
                ".summary",
                "[class*='desc']"
            ]
        }

    # ==================== 私有方法 ====================

    async def _extract_note_detail(
        self,
        page,
        use_fast_mode: bool = False
    ) -> Dict[str, Any]:
        """提取笔记详情
        
        Args:
            page: 页面对象
            use_fast_mode: 是否使用快速提取模式
            
        Returns:
            笔记详情数据
        """
        # 尝试从 __INITIAL_STATE__ 提取结构化数据
        try:
            initial_state = await page.evaluate("() => window.__INITIAL_STATE__")
            if initial_state and "note" in initial_state:
                note_detail_map = initial_state.get("note", {}).get("noteDetailMap", {})
                if note_detail_map:
                    note_id = list(note_detail_map.keys())[0]
                    detail_data = note_detail_map[note_id]
                    return self._process_note_detail(detail_data)
        except Exception as e:
            logger.debug(f"[xiaohongshu] Failed to extract from __INITIAL_STATE__: {e}")

        # 使用 Agent 提取作为回退
        instruction = "提取小红书笔记：标题、内容、作者信息、互动数据（点赞、收藏、评论、分享）、图片列表"
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "笔记标题"},
                "content": {"type": "string", "description": "笔记内容"},
                "author": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "nickname": {"type": "string"},
                        "avatar": {"type": "string"}
                    }
                },
                "interact_info": {
                    "type": "object",
                    "properties": {
                        "liked_count": {"type": "integer"},
                        "collected_count": {"type": "integer"},
                        "comment_count": {"type": "integer"},
                        "shared_count": {"type": "integer"}
                    }
                },
                "images": {"type": "array", "items": {"type": "string"}}
            }
        }
        ok, data = await self._extract_page_content(page, instruction, schema)
        return data if ok else {"success": False, "error": "Failed to extract content"}

    async def _extract_user_notes(
        self,
        page
    ) -> List[Dict[str, Any]]:
        """提取用户笔记列表"""
        instruction = "提取用户的所有笔记，包括标题、互动数据、封面图、发布时间"
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "cover": {"type": "string"},
                    "liked_count": {"type": "integer"},
                    "collected_count": {"type": "integer"},
                    "comment_count": {"type": "integer"},
                    "publish_time": {"type": "string"}
                }
            }
        }
        ok, data = await self._extract_page_content(page, instruction, schema)

        if ok and data:
            return data if isinstance(data, list) else [data]
        return []

    async def _extract_general(
        self,
        page
    ) -> Dict[str, Any]:
        """提取通用内容"""
        instruction = "提取页面主要内容和数据"
        ok, data = await self._extract_page_content(page, instruction)

        return data if ok else {}

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
        context_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        """流式提取小红书帖子详情并总结分析（使用Agent进行分析），支持并发"""
        if not context_id:
            raise ValueError("未传入登陆的上下文id")
        
        # 初始化一次 session 和 browser context，所有 URL 共享
        p, browser, context = await self._get_browser_context(context_id)

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
                            agent_browser = self.session.browser.agent
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
                                analysis_agent = self.session.browser.agent
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
            # 所有 URL 处理完后关闭 browser
            await browser.close()
            await p.stop()


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
            str|None: 如果登录成功返回 context_id，用于后续恢复登录态
        """
        # 使用 source:source_id 作为上下文的唯一标识
        # 这确保了不同系统/用户之间的上下文隔离
        login_context_id = f"xiaohongshu_{source}_{source_id}"

        logger.info(f"[xiaohongshu] Using context_id: {login_context_id} for source:{source}, source_id:{source_id}")

        # 使用基类的通用方法创建持久化上下文
        return await self._create_persistent_context_by_cookies(
            context_id=login_context_id,
            cookies=cookies,
            domain=".xiaohongshu.com",
            verify_login_url="https://www.xiaohongshu.com",
            verify_login_func=self._check_login_status
        )

    async def publish_content(
            self,
            content: str,
            content_type: str = "text",
            images: Optional[List[str]] = None,
            tags: Optional[List[str]] = None,
            context_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """发布内容到小红书"""
        p, browser, context = await self._get_browser_context()

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
            agent = self.session.browser.agent
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
            await browser.close()
            await p.stop()



    # ==================== 多种查询方式的支持 ====================


    async def harvest_user_content(
            self,
            user_id: str,
            limit: Optional[int] = None,
            context_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """采收用户的所有笔记

        Args:
            user_id: 用户ID
            limit: 限制数量
            context_id: 上下文ID

        Returns:
            笔记列表
        """
        logger.info(f"[xiaohongshu] Harvesting notes from user: {user_id}, limit={limit}")

        # 先获取用户的笔记列表
        notes_info = await self.extract_by_creator_id(user_id, limit=limit, extract_details=False, context_id=context_id)

        # 使用快速提取模式获取详情
        note_urls = [note["data"]["url"] for note in notes_info if note.get("success")]

        if not note_urls:
            return []

        logger.info(f"[xiaohongshu] Extracting details for {len(note_urls)} notes")

        # 批量提取详情
        results = await self.get_note_detail(note_urls, concurrency=3, context_id=context_id)

        # 合并信息
        merged_results = []
        for note_info, detail in zip(notes_info, results):
            if detail.get("success"):
                data = detail.get("data", {})
                # 保留列表信息中的note_id
                if "data" in note_info and "note_id" in note_info["data"]:
                    data["note_id"] = note_info["data"]["note_id"]
                merged_results.append({
                    "success": True,
                    "data": data
                })
            else:
                merged_results.append({
                    "success": False,
                    "error": detail.get("error", "Failed to extract"),
                    "note_id": note_info.get("data", {}).get("note_id")
                })

        return merged_results

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
        extract_details: bool = False,
        context_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """通过创作者ID提取其笔记
        
        Args:
            creator_id: 创作者ID
            limit: 限制提取数量
            extract_details: 是否提取详情（True会访问每个笔记页面，False只提取列表信息）
            
        Returns:
            笔记列表
        """
        logger.info(f"[xiaohongshu] Extracting notes from creator: {creator_id}, limit={limit}")
        
        p, browser, context = await self._get_browser_context()
        
        try:
            page = await context.new_page()
            await page.goto(f"https://www.xiaohongshu.com/user/profile/{creator_id}", timeout=60000)
            await asyncio.sleep(3)
            
            # 提取笔记列表
            note_links = await page.evaluate("""
                () => {
                    const links = [];
                    const elements = document.querySelectorAll('a[href*="/explore/"]');
                    for (const elem of elements) {
                        const href = elem.getAttribute('href');
                        if (href && href.includes('/explore/')) {
                            const noteId = href.split('/explore/')[1].split('?')[0];
                            if (noteId && !links.find(l => l.noteId === noteId)) {
                                links.push({
                                    noteId: noteId,
                                    url: href.startsWith('http') ? href : 'https://www.xiaohongshu.com' + href,
                                    title: elem.innerText || elem.querySelector('img')?.alt || ''
                                });
                            }
                        }
                    }
                    return links;
                }
            """)
            
            if not note_links:
                logger.warning(f"[xiaohongshu] No notes found for creator: {creator_id}")
                return []
            
            # 限制数量
            if limit:
                note_links = note_links[:limit]
            
            logger.info(f"[xiaohongshu] Found {len(note_links)} notes for creator: {creator_id}")
            
            if extract_details:
                # 提取每个笔记的详情
                # 提取每个笔记的详情
                semaphore = asyncio.Semaphore(2)
                
                async def extract_detail(link):
                    async with semaphore:
                        page = None
                        try:
                            page = await context.new_page()
                            await page.goto(link["url"], timeout=30000)
                            await page.wait_for_load_state("networkidle", timeout=10000)
                            
                            content = await self._extract_note_detail(page, use_fast_mode=True)
                            
                            return {
                                "success": content.get("success", False),
                                "data": content if content.get("success") else None,
                                "error": content.get("error") if not content.get("success") else None
                            }
                        finally:
                            if page:
                                await page.close()
                
                details = await asyncio.gather(*[extract_detail(link) for link in note_links])
                
                # 合并列表信息和详情
                results = []
                for link, detail in zip(note_links, details):
                    if detail.get("success"):
                        data = detail.get("data", {})
                        data.update({
                            "list_info": {
                                "note_id": link["noteId"],
                                "url": link["url"]
                            }
                        })
                        results.append({
                            "success": True,
                            "data": data
                        })
                    else:
                        results.append({
                            "success": False,
                            "error": detail.get("error"),
                            "note_id": link["note_id"]
                        })
                
                return results
            else:
                # 只返回列表信息
                return [{
                    "success": True,
                    "data": {
                        "note_id": link["noteId"],
                        "url": link["url"],
                        "title": link["title"]
                    }
                } for link in note_links]
                
        finally:
            await browser.close()
            await p.stop()

    async def get_note_detail(
        self,
        urls: List[str],
        concurrency: int = 3,
        context_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取单个笔记的详情（使用evaluate提取结构化数据）
        
        Args:
            urls: 链接集合
            concurrency: 并发数
            context_id: 上下文ID
        Returns:
            笔记详情
        """
        p, browser, context = await self._get_browser_context(context_id)
        
        try:
            semaphore = asyncio.Semaphore(concurrency)
            
            async def extract_detail(url):
                async with semaphore:
                    page = None
                    try:
                        page = await context.new_page()
                        await page.goto(url, timeout=30000)
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        
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
            
            tasks = [extract_detail(url) for url in urls]
            results = await asyncio.gather(*tasks)
            
        finally:
            await browser.close()
            await p.stop()
        
        return results
    
    async def _get_note_detail_evaluate(self, page):
        """使用evaluate提取笔记详情（参考MCP实现）"""
        try:
            # 等待页面数据加载
            await asyncio.sleep(3)
            
            # 使用evaluate提取数据（参考MCP实现）
            note_data = await page.evaluate("""
                () => {
                    // 从页面中获取笔记数据
                    const noteDetailMap = window.__INITIAL_STATE__?.note?.noteDetailMap;
                    if (noteDetailMap) {
                        const noteIds = Object.keys(noteDetailMap);
                        if (noteIds.length > 0) {
                            const noteDetail = noteDetailMap[noteIds[0]];
                            const note = noteDetail.note;
                            
                            // 提取所需的数据结构（参考MCP的Feed结构）
                            return {
                                note_id: note.noteId,
                                xsec_token: note.xsecToken,
                                title: note.title,
                                desc: note.desc,
                                type: note.type,
                                time: note.time,
                                ip_location: note.ipLocation,
                                user: note.user ? {
                                    user_id: note.user.userId,
                                    nickname: note.user.nickname || note.user.nickName,
                                    avatar: note.user.avatar
                                } : {},
                                interact_info: note.interactInfo ? {
                                    liked: note.interactInfo.liked,
                                    liked_count: note.interactInfo.likedCount || 0,
                                    shared_count: note.interactInfo.sharedCount || 0,
                                    comment_count: note.interactInfo.commentCount || 0,
                                    collected_count: note.interactInfo.collectedCount || 0,
                                    collected: note.interactInfo.collected
                                } : {},
                                image_list: note.imageList ? note.imageList.map(img => ({
                                    width: img.width,
                                    height: img.height,
                                    url_default: img.urlDefault,
                                    url_pre: img.urlPre,
                                    live_photo: img.livePhoto
                                })) : [],
                                video: note.video,
                                tag_list: note.tagList || [],
                                location: note.location || {},
                                at_user_list: note.atUserList || []
                            };
                        }
                    }
                    
                    // 尝试其他可能的路径
                    const notes = window.__INITIAL_STATE__?.note?.notes;
                    if (notes && Object.keys(notes).length > 0) {
                        const firstKey = Object.keys(notes)[0];
                        return notes[firstKey];
                    }
                    
                    return null;
                }
            """)
            
            return note_data
            
        except Exception as e:
            logger.error(f"获取笔记详情失败: {e}")
            return None

    async def search_and_extract(
        self,
        keyword: str,
        limit: int = 20,
        extract_details: bool = True,
        context_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """搜索并提取小红书内容
        
        Args:
            keyword: 搜索关键词
            limit: 限制数量
            extract_details: 是否提取详情
            context_id: 上下文id
        Returns:
            搜索结果
        """
        logger.info(f"[xiaohongshu] Searching for: {keyword}")
        
        p, browser, context = await self._get_browser_context()
        
        try:
            page = await context.new_page()
            # 构建搜索URL
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}"
            await page.goto(search_url, timeout=60000)
            await asyncio.sleep(3)
            
            # 提取搜索结果
            search_results = await page.evaluate("""
                () => {
                    const results = [];
                    const elements = document.querySelectorAll('a[href*="/explore/"]');
                    for (const elem of elements) {
                        const href = elem.getAttribute('href');
                        if (href && href.includes('/explore/')) {
                            const noteId = href.split('/explore/')[1].split('?')[0];
                            if (noteId && !results.find(r => r.noteId === noteId)) {
                                const titleElem = elem.querySelector('.title, .note-title, h3');
                                const imgElem = elem.querySelector('img');
                                results.push({
                                    noteId: noteId,
                                    url: href.startsWith('http') ? href : 'https://www.xiaohongshu.com' + href,
                                    title: titleElem?.innerText || imgElem?.alt || '',
                                    image: imgElem?.src || ''
                                });
                            }
                        }
                    }
                    return results;
                }
            """)
            
            if not search_results:
                logger.warning(f"[xiaohongshu] No search results for: {keyword}")
                return []
            
            # 限制数量
            search_results = search_results[:limit]
            
            logger.info(f"[xiaohongshu] Found {len(search_results)} search results")
            
            if extract_details:
                # 提取每个结果的详情
                semaphore = asyncio.Semaphore(2)
                
                async def extract_detail(result):
                    async with semaphore:
                        page = None
                        try:
                            page = await context.new_page()
                            await page.goto(result["url"], timeout=30000)
                            await page.wait_for_load_state("networkidle", timeout=10000)
                            
                            content = await self._extract_note_detail(page, use_fast_mode=True)
                            
                            return {
                                "success": content.get("success", False),
                                "data": content if content.get("success") else None,
                                "error": content.get("error") if not content.get("success") else None
                            }
                        except Exception as e:
                            return {
                                "success": False,
                                "error": str(e)
                            }
                        finally:
                            if page:
                                await page.close()
                
                details = await asyncio.gather(*[extract_detail(result) for result in search_results])
                
                # 合并搜索信息和详情
                results = []
                for search_info, detail in zip(search_results, details):
                    if detail.get("success"):
                        data = detail.get("data", {})
                        data.update({
                            "search_info": {
                                "note_id": search_info["noteId"],
                                "title_snippet": search_info["title"],
                                "image": search_info["image"]
                            }
                        })
                        results.append({
                            "success": True,
                            "data": data
                        })
                    else:
                        results.append({
                            "success": False,
                            "error": detail.get("error"),
                            "note_id": search_info["note_id"]
                        })
                
                return results
            else:
                # 只返回搜索结果列表
                return [{
                    "success": True,
                    "data": {
                        "note_id": result["noteId"],
                        "url": result["url"],
                        "title": result["title"],
                        "image": result["image"]
                    }
                } for result in search_results]
                
        finally:
            await browser.close()
            await p.stop()
