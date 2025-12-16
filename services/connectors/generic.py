# -*- coding: utf-8 -*-
"""通用网站连接器 - 支持任何网站的内容提取"""

import asyncio
from typing import Dict, Any, List, Optional
from playwright.async_api import Page

from .base import BaseConnector
from utils.logger import logger
from models.connectors import PlatformType


class GenericConnector(BaseConnector):
    """通用网站连接器 - 适用于任何网站"""

    def __init__(self):
        super().__init__(platform_name=PlatformType.GENERIC)

    async def extract_summary(
        self,
        urls: List[str]
    ) -> List[Dict[str, Any]]:
        """提取网站摘要"""
        results = []
        async for result in self.extract_summary_stream(urls):
            results.append(result)
        return results

    async def extract_summary_stream(
        self,
        urls: List[str],
        concurrency: int = 1,
        context_id: Optional[str] = None
    ):
        """流式提取网站摘要，支持并发
        
        Args:
            urls: URL列表
            concurrency: 并发数
            context_id: 上下文ID
        """
        # 初始化一次 session 和 browser context，所有 URL 共享
        p, browser, context = await self._get_browser_context(context_id)

        try:
            # 创建信号量来限制并发数
            semaphore = asyncio.Semaphore(concurrency)

            async def extract_single_url(url: str, idx: int):
                """提取单个 URL（使用共享的 browser context）"""
                async with semaphore:
                    logger.info(f"[generic] Processing URL {idx}/{len(urls)}: {url}")

                    page = None
                    try:
                        # 在共享的 context 中创建新 page
                        page = await context.new_page()
                        await page.goto(url, timeout=60000)
                        await asyncio.sleep(2)

                        # 使用evaluate提取页面信息
                        page_data = await page.evaluate("""
                            () => {
                                // 提取标题
                                const title = document.title || 
                                           (document.querySelector('h1')?.innerText) || 
                                           (document.querySelector('title')?.innerText) || '';
                                
                                // 提取meta信息
                                const metaDesc = document.querySelector('meta[name="description"]')?.getAttribute('content') || '';
                                const metaKeywords = document.querySelector('meta[name="keywords"]')?.getAttribute('content') || '';
                                
                                // 提取主要内容
                                let content = '';
                                const contentSelectors = [
                                    'main',
                                    'article',
                                    '[role="main"]',
                                    '.content',
                                    '.main-content',
                                    '#content',
                                    '.post-content',
                                    '.article-content'
                                ];
                                
                                for (const selector of contentSelectors) {
                                    const el = document.querySelector(selector);
                                    if (el) {
                                        content = el.innerText.trim();
                                        if (content.length > 100) break;
                                    }
                                }
                                
                                // 如果没找到内容，尝试提取body文本
                                if (!content || content.length < 100) {
                                    const bodyText = document.body?.innerText || '';
                                    content = bodyText.trim();
                                }
                                
                                // 提取所有链接
                                const links = [];
                                document.querySelectorAll('a[href]').forEach(a => {
                                    const href = a.getAttribute('href');
                                    const text = a.innerText.trim();
                                    if (href && text && !href.startsWith('#') && !href.startsWith('javascript:')) {
                                        links.push({
                                            url: href,
                                            text: text.substring(0, 100)
                                        });
                                    }
                                });
                                
                                // 提取所有图片
                                const images = [];
                                document.querySelectorAll('img[src]').forEach(img => {
                                    const src = img.getAttribute('src');
                                    const alt = img.getAttribute('alt') || '';
                                    if (src && !src.startsWith('data:')) {
                                        images.push({
                                            url: src.startsWith('//') ? 'https:' + src : src,
                                            alt: alt
                                        });
                                    }
                                });
                                
                                // 生成摘要
                                const summary = content.length > 300 ? 
                                    content.substring(0, 300) + '...' : content;
                                
                                return {
                                    title: title,
                                    description: metaDesc,
                                    keywords: metaKeywords,
                                    content: content,
                                    summary: summary,
                                    content_length: content.length,
                                    links: links.slice(0, 20), // 限制链接数量
                                    link_count: links.length,
                                    images: images.slice(0, 20), // 限制图片数量
                                    image_count: images.length,
                                    url: window.location.href
                                };
                            }
                        """)
                        
                        return {
                            "url": url,
                            "success": True,
                            "data": page_data,
                            "method": "evaluate_extraction"
                        }

                    except Exception as e:
                        logger.error(f"[generic] Error extracting {url}: {e}")
                        return {
                            "url": url,
                            "success": False,
                            "error": str(e),
                            "method": "evaluate_extraction"
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

    async def get_note_detail(
        self,
        urls: List[str],
        concurrency: int = 3,
        context_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取网页详情
        
        Args:
            urls: URL列表
            concurrency: 并发数
            context_id: 上下文ID
            
        Returns:
            提取结果列表
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
                        
                        # 使用evaluate获取详细信息
                        detail_data = await page.evaluate("""
                            () => {
                                // 获取页面基本信息
                                const title = document.title || '';
                                const url = window.location.href;
                                
                                // 获取所有标题
                                const headings = [];
                                document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(h => {
                                    headings.push({
                                        level: parseInt(h.tagName.substring(1)),
                                        text: h.innerText.trim()
                                    });
                                });
                                
                                // 获取所有段落
                                const paragraphs = [];
                                document.querySelectorAll('p').forEach(p => {
                                    const text = p.innerText.trim();
                                    if (text.length > 20) {
                                        paragraphs.push(text);
                                    }
                                });
                                
                                // 获取列表
                                const lists = [];
                                document.querySelectorAll('ul, ol').forEach(list => {
                                    const items = [];
                                    list.querySelectorAll('li').forEach(li => {
                                        const text = li.innerText.trim();
                                        if (text) items.push(text);
                                    });
                                    if (items.length > 0) {
                                        lists.push({
                                            type: list.tagName.toLowerCase(),
                                            items: items
                                        });
                                    }
                                });
                                
                                // 获取表格
                                const tables = [];
                                document.querySelectorAll('table').forEach(table => {
                                    const rows = [];
                                    table.querySelectorAll('tr').forEach(tr => {
                                        const cells = [];
                                        tr.querySelectorAll('td, th').forEach(td => {
                                            cells.push(td.innerText.trim());
                                        });
                                        if (cells.length > 0) rows.push(cells);
                                    });
                                    if (rows.length > 0) tables.push(rows);
                                });
                                
                                // 获取所有表单
                                const forms = [];
                                document.querySelectorAll('form').forEach(form => {
                                    const inputs = [];
                                    form.querySelectorAll('input, textarea, select').forEach(input => {
                                        inputs.push({
                                            type: input.type || input.tagName.toLowerCase(),
                                            name: input.name || '',
                                            placeholder: input.placeholder || ''
                                        });
                                    });
                                    if (inputs.length > 0) {
                                        forms.push({
                                            action: form.action || '',
                                            method: form.method || 'GET',
                                            inputs: inputs
                                        });
                                    }
                                });
                                
                                return {
                                    title: title,
                                    url: url,
                                    headings: headings,
                                    paragraphs: paragraphs,
                                    lists: lists,
                                    tables: tables,
                                    forms: forms,
                                    content_stats: {
                                        heading_count: headings.length,
                                        paragraph_count: paragraphs.length,
                                        list_count: lists.length,
                                        table_count: tables.length,
                                        form_count: forms.length
                                    }
                                };
                            }
                        """)
                        
                        return {
                            "url": url,
                            "success": True,
                            "data": detail_data,
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
        """通用连接器不支持通过创作者ID提取"""
        raise NotImplementedError("GenericConnector does not support extract_by_creator_id")
    
    async def search_and_extract(
        self,
        keyword: str,
        limit: int = 20,
        extract_details: bool = False
    ) -> List[Dict[str, Any]]:
        """通用连接器不支持搜索功能"""
        raise NotImplementedError("GenericConnector does not support search_and_extract")
