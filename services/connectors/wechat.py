# -*- coding: utf-8 -*-
"""微信公众号连接器 - 支持文章提取和监控"""

import asyncio
from enum import Enum
from agentbay.browser.browser_agent import ActOptions
from typing import Dict, Any, List, Optional
from typing import Optional, List
from playwright.async_api import Page

from .base import BaseConnector
from utils.logger import logger
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

    def __init__(self):
        super().__init__(platform_name=PlatformType.WECHAT)

    async def login_with_cookies(self,
                                 cookies: Dict[str, str],
                                 source: str = "default",
                                 source_id: str = "default") -> str:
        # TODO：公众号不需要实现
        return ""

    async def extract_summary_stream(
        self,
        urls: List[str],
        concurrency: int=1,
        context_id: str=None
    ):
        """流式提取微信公众号文章摘要，支持并发"""
        # 定义提取指令
        instruction = "根据数据结构提取相关内容，并进行内容总结分析"

        # 初始化一次 session 和 browser context，所有 URL 共享
        p, browser, context = await self._get_browser_context(context_id)

        try:
            # 创建信号量来限制并发数
            semaphore = asyncio.Semaphore(concurrency)

            async def extract_single_url(url: str, idx: int):
                """提取单个 URL（使用共享的 browser context）"""
                async with semaphore:
                    logger.info(f"[wechat] Processing URL {idx}/{len(urls)}: {url}")

                    page = None
                    try:
                        # 在共享的 context 中创建新 page
                        page = await context.new_page()
                        await page.goto(url, timeout=60000)
                        await asyncio.sleep(2)

                        # 关闭可能出现的弹窗
                        try:
                            agent = self.session.browser.agent
                            await agent.act_async(
                                ActOptions(action="如果有弹窗或广告，关闭它们，然后滑动到文章最下边。"),
                                page=page
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
            # 所有 URL 处理完后关闭 browser
            await browser.close()
            await p.stop()

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
        context_id=None
    ) -> List[Dict[str, Any]]:
        """快速获取微信文章详情
        
        Args:
            urls: 文章URL列表
            concurrency: 并发数
            context_id
        Returns:
            提取结果列表
        """
        p, browser, context = await self._get_browser_context()
        
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
            
        finally:
            await browser.close()
            await p.stop()
        
        return results
    
    async def extract_by_creator_id(
        self,
        creator_id: str,
        limit: Optional[int] = None,
        extract_details: bool = False
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

    
    async def search_and_extract(
        self,
        keyword: str,
        limit: int = 20,
        extract_details: bool = False,
        context_id = None
    ) -> List[Dict[str, Any]]:
        """搜索并提取微信文章
        
        Args:
            keyword: 搜索关键词
            limit: 限制数量
            extract_details: 是否提取详情
            context_id
        Returns:
            搜索结果
        """
        logger.info(f"[wechat] Searching for: {keyword}")
        
        # 微信文章搜索接口
        search_url = f"https://weixin.sogou.com/weixin?type=2&query={keyword}"
        
        p, browser, context = await self._get_browser_context(context_id)
        
        try:
            page = await context.new_page()
            await page.goto(search_url, timeout=60000)
            await asyncio.sleep(3)
            
            # 使用evaluate直接提取搜索结果
            articles = await page.evaluate("""
                (limit) => {
                    const articles = [];
                    
                    // 查找搜索结果列表容器
                    const newsList = document.querySelector('.news-list');
                    if (!newsList) return articles;
                    
                    // 获取所有li元素
                    const listItems = newsList.querySelectorAll('li');
                    
                    Array.from(listItems).forEach((item, index) => {
                        if (limit && index >= limit) return;
                        
                        // 提取标题和链接
                        const titleEl = item.querySelector('h3 a');
                        const title = titleEl ? titleEl.innerText.trim() : '';
                        const href = titleEl ? titleEl.getAttribute('href') : '';
                        
                        if (href) {
                            // 提取作者/公众号名
                            const authorEl = item.querySelector('.s-p .all-time-y2');
                            const author = authorEl ? authorEl.innerText.trim() : '';
                            
                            // 提取时间 - 在.s-p .s2中的script标签
                            const timeEl = item.querySelector('.s-p .s2 script');
                            let time = '';
                            if (timeEl) {
                                // 从script内容中提取时间戳
                                const scriptText = timeEl.innerText;
                                const match = scriptText.match(/timeConvert\('(\d+)'\)/);
                                if (match) {
                                    // 转换时间戳为可读格式
                                    const timestamp = parseInt(match[1]);
                                    const date = new Date(timestamp * 1000);
                                    time = date.toLocaleString('zh-CN');
                                }
                            }
                            
                            // 提取摘要
                            const descEl = item.querySelector('.txt-info');
                            const desc = descEl ? descEl.innerText.trim() : '';
                            
                            // 提取图片
                            const imgEl = item.querySelector('.img-box img');
                            const image = imgEl ? imgEl.getAttribute('src') : '';
                            
                            articles.push({
                                title: title,
                                author: author,
                                url: href,  // 这里是搜狗的跳转链接，需要后续处理
                                publish_time: time,
                                summary: desc,
                                image: image,
                                index: index
                            });
                        }
                    });
                    
                    return articles;
                }
            """, limit or 20)
            
            logger.info(f"[wechat] Found {len(articles)} articles")
            
            # 转换为完整的URL
            for article in articles:
                if article.get("url") and article["url"].startswith("/"):
                    article["url"] = f"https://weixin.sogou.com{article['url']}"
                    logger.debug(f"[wechat] Converted relative URL to absolute: {article['url']}")
            
            logger.info(f"[wechat] Found {len(articles)} articles")
            
            if extract_details and articles:
                # 提取每篇文章的详情
                urls = [article.get("url") for article in articles if article.get("url")]
                details = await self.get_note_detail(urls, concurrency=2, context_id=context_id)
                
                # 合并信息
                results = []
                for article, detail in zip(articles, details):
                    if detail.get("success"):
                        results.append({
                            "success": True,
                            "data": {
                                **article,
                                "detail": detail.get("data")
                            }
                        })
                    else:
                        results.append({
                            "success": False,
                            "error": detail.get("error"),
                            "article_info": article
                        })
                
                return results
            else:
                return [{
                    "success": True,
                    "data": article
                } for article in articles]
            
        finally:
            await browser.close()
            await p.stop()
