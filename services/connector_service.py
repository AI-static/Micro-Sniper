"""
连接器服务层 - 统一的连接器管理和调度

提供四大核心功能：
- 监控 (monitor): 持续追踪URL变化，实时推送更新
- 提取 (extract): 一次性获取指定URL的内容
- 采收 (harvest): 批量获取用户/账号的所有内容
- 发布 (publish): 发布内容到指定平台
"""

from typing import Dict, Any, List, Optional, AsyncGenerator

from services.connectors.xiaohongshu import XiaohongshuConnector
from services.connectors.wechat import WechatConnector
from services.connectors.generic import GenericConnector
from utils.logger import logger
from models.connectors import PlatformType, LoginMethod
from agentbay import CreateSessionParams, BrowserContext, BrowserOption, BrowserScreen, BrowserFingerprint


class ConnectorService:
    """连接器服务 - 统一的连接器管理和调度中心
    
    设计原则：
    - connector 实例按平台缓存，不再按 source:source_id
    - source/source_id 由各 connector 在调用时自行处理
    """

    # 平台标识映射
    PLATFORM_IDENTIFIERS = {
        PlatformType.XIAOHONGSHU: ["xiaohongshu.com", "xhslink.com"],
        PlatformType.WECHAT: ["mp.weixin.qq.com"],
    }

    def __init__(self):
        """初始化连接器服务"""
        self._connectors = {}

    def _get_connector(self, platform: PlatformType):
        """获取或创建平台连接器

        Args:
            platform: 平台名称 (xiaohongshu/wechat/generic)

        Returns:
            对应的连接器实例

        Raises:
            ValueError: 不支持的平台
        """
        # 转换为枚举类型
        if isinstance(platform, str):
            platform = PlatformType(platform)
        
        if platform not in self._connectors:
            if platform == PlatformType.XIAOHONGSHU:
                self._connectors[platform] = XiaohongshuConnector()
            elif platform == PlatformType.WECHAT:
                self._connectors[platform] = WechatConnector()
            elif platform == PlatformType.GENERIC:
                self._connectors[platform] = GenericConnector()
            else:
                raise ValueError(f"不支持的平台: {platform}")

        return self._connectors[platform]

    def _detect_platform(self, url: str) -> PlatformType:
        """自动检测URL所属平台

        Args:
            url: 网址

        Returns:
            平台名称
        """
        for platform, identifiers in self.PLATFORM_IDENTIFIERS.items():
            if any(identifier in url for identifier in identifiers):
                return platform

        return PlatformType.GENERIC

    # ==================== 核心 API ====================

    async def extract_summary_stream(
        self,
        urls: List[str],
        platform: PlatformType,
        source: str = "default",
        source_id: str = "default",
        concurrency: int = 10
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式提取URL内容摘要

        Args:
            urls: 要提取的URL列表
            platform: 平台名称（必须指定）
            source: 系统标识
            source_id: 用户标识
            concurrency: 并发数量

        Yields:
            提取结果字典，包含 url、success、data 等字段
        """
        try:
            connector = self._get_connector(platform)
            logger.info(f"[ConnectorService] Streaming extraction from {platform}, {len(urls)} URLs, source={source}, source_id={source_id}")
            
            # 发送开始事件
            yield {
                'type': 'start',
                'message': '提取已启动',
                'data': {
                    'urls': urls,
                    'platform': platform,
                    'url_count': len(urls),
                    'concurrency': concurrency
                }
            }
            
            processed = 0
            success_count = 0
            
            # 检查 connector 是否有 extract_summary_stream 方法
            if hasattr(connector, 'extract_summary_stream'):
                # 直接使用 connector 的流式方法
                async for result in connector.extract_summary_stream(urls, concurrency, source, source_id):
                    processed += 1
                    if result.get('success'):
                        success_count += 1
                    
                    # 发送结果事件
                    yield {
                        'type': 'result',
                        'data': result,
                        'progress': {
                            'current': processed,
                            'total': len(urls),
                            'success_count': success_count
                        }
                    }
            else:
                yield {
                    'type': 'error',
                    'message': '此渠道没有extract_summary_stream方法',
                    'data': {
                        'platform': platform,
                        'error': 'method_not_supported'
                    }
                }
                return
            
            # 发送完成事件
            failed_count = processed - success_count
            yield {
                'type': 'complete',
                'message': f'提取完成：{success_count}/{processed} 成功',
                'data': {
                    'total': processed,
                    'success_count': success_count,
                    'failed_count': failed_count
                }
            }
            
        except ValueError as e:
            logger.error(f"[ConnectorService] ValueError in extract_summary_stream: {e}")
            yield {
                'type': 'error',
                'message': str(e),
                'data': {
                    'platform': platform,
                    'error_type': 'value_error'
                }
            }
        except Exception as e:
            logger.error(f"[ConnectorService] Unexpected error in extract_summary_stream: {e}")
            yield {
                'type': 'error',
                'message': f'提取过程中发生错误: {str(e)}',
                'data': {
                    'platform': platform,
                    'error_type': 'unexpected_error'
                }
            }
    
    async def get_note_details(
        self,
        urls: List[str],
        platform: PlatformType,
        source: str = "default",
        source_id: str = "default",
        concurrency: int = 3,
    ) -> List[Dict[str, Any]]:
        """获取笔记/文章详情（快速提取，不使用Agent）

        Args:
            urls: 要提取的URL列表
            platform: 平台名称
            source: 系统标识
            source_id: 用户标识
            concurrency: 并发数

        Returns:
            提取结果列表，每个元素包含 url、success、data 等字段
        """
        try:
            connector = self._get_connector(platform)
            logger.info(f"[ConnectorService] Getting note details for {len(urls)} URLs from {platform}, source={source}, source_id={source_id}")
                
            # 调用 get_note_detail 方法
            results = await connector.get_note_detail(urls, concurrency=concurrency, source=source, source_id=source_id)

            success_count = sum(1 for r in results if r.get("success"))
            logger.info(f"[ConnectorService] Get note details completed: {success_count}/{len(results)} successful")

            return results

        except Exception as e:
            import traceback
            logger.error(f"[ConnectorService] Get note details error: {traceback.format_exc()}")
            raise

    async def harvest_user_content(
        self,
        platform: str | PlatformType,
        user_id: str,
        source: str = "default",
        source_id: str = "default",
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """采收用户/账号的所有内容

        Args:
            platform: 平台名称
            user_id: 用户ID或账号标识
            source: 系统标识
            source_id: 用户标识
            limit: 限制数量

        Returns:
            内容列表
        """
        try:
            connector = self._get_connector(platform)
            logger.info(f"[ConnectorService] Harvesting user content from {platform}, user={user_id}, limit={limit}, source={source}, source_id={source_id}")
            
            result = await connector.harvest_user_content(user_id, limit, source, source_id)

            logger.info(f"[ConnectorService] Harvested {len(result)} items")
            return result

        except NotImplementedError:
            logger.error(f"[ConnectorService] Platform {platform} does not support harvest")
            raise ValueError(f"平台 {platform} 不支持采收功能")
        except Exception as e:
            logger.error(f"[ConnectorService] Harvest error: {e}")
            raise

    async def publish_content(
        self,
        platform: str | PlatformType,
        content: str,
        source: str = "default",
        source_id: str = "default",
        content_type: str = "text",
        images: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """发布内容到平台

        Args:
            platform: 平台名称
            content: 内容文本
            source: 系统标识
            source_id: 用户标识
            content_type: 内容类型 (text/image/video)
            images: 图片URL列表
            tags: 标签列表
            context_id: 上下文ID，用于保持登录态

        Returns:
            发布结果字典，包含 success、platform 等字段
        """
        try:
            connector = self._get_connector(platform)
            logger.info(f"[ConnectorService] Publishing content to {platform}, type={content_type}, source={source}, source_id={source_id}")

            result = await connector.publish_content(content, content_type, images, tags, context_id, source, source_id)

            status = "successful" if result.get("success") else "failed"
            logger.info(f"[ConnectorService] Publish {status}")

            return result

        except NotImplementedError:
            logger.error(f"[ConnectorService] Platform {platform} does not support publish")
            raise ValueError(f"平台 {platform} 不支持发布功能")
        except Exception as e:
            logger.error(f"[ConnectorService] Publish error: {e}")
            raise

    async def extract_by_creator_id(
        self,
        platform: str | PlatformType,
        creator_id: str,
        source: str = "default",
        source_id: str = "default",
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """通过创作者ID提取内容

        Args:
            platform: 平台名称
            creator_id: 创作者ID
            source: 系统标识
            source_id: 用户标识
            limit: 限制数量
            extract_details: 是否提取详情

        Returns:
            提取结果列表
        """
        try:
            connector = self._get_connector(platform)
            logger.info(f"[ConnectorService] Extracting by creator ID from {platform}, creator={creator_id}, source={source}, source_id={source_id}")
            
            results = await connector.extract_by_creator_id(
                creator_id=creator_id,
                limit=limit,
                source=source,
                source_id=source_id
            )
            
            logger.info(f"[ConnectorService] Extracted {len(results)} items by creator ID")
            return results
            
        except Exception as e:
            logger.error(f"[ConnectorService] Extract by creator ID error: {e}")
            raise
    
    async def search_and_extract(
        self,
        platform: str | PlatformType,
        keyword: str,
        source: str = "default",
        source_id: str = "default",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """搜索并提取内容

        Args:
            platform: 平台名称
            keyword: 搜索关键词
            source: 系统标识
            source_id: 用户标识
            limit: 限制数量
            extract_details: 是否提取详情

        Returns:
            搜索结果列表
        """
        try:
            connector = self._get_connector(platform)
            logger.info(f"[ConnectorService] Searching and extracting from {platform}, keyword={keyword}, source={source}, source_id={source_id}")
            
            results = await connector.search_and_extract(
                keyword=keyword,
                limit=limit,
                source=source,
                source_id=source_id
            )
            
            logger.info(f"[ConnectorService] Found {len(results)} search results")
            return results
            
        except Exception as e:
            logger.error(f"[ConnectorService] Search and extract error: {e}")
            raise

    async def login(
        self,
        platform: PlatformType,
        method: LoginMethod,
        **kwargs
    ) -> bool:
        """登录平台

        Args:
            platform: 平台名称
            method: 登录方法 (目前仅支持 cookie)
            **kwargs: 登录参数，例如 cookies, source, source_id

        Returns:
            是否登录成功
        """
        try:
            if platform == PlatformType.XIAOHONGSHU and method == LoginMethod.COOKIE:
                cookies = kwargs.get("cookies", {})
                if not cookies:
                    raise ValueError("Cookie 登录需要提供 cookies 参数")

                connector = self._get_connector(platform)
                
                # 获取 source 和 source_id
                source = kwargs.get("source", "default")
                source_id = kwargs.get("source_id", "default")
                
                logger.info(f"[ConnectorService] Logging in to {platform} with cookies for source:{source}, source_id:{source_id}")
                context_id = await connector.login_with_cookies(cookies, source, source_id)

                logger.info(f"[ConnectorService] Login Res: context_id: {context_id}")

                return context_id
            else:
                raise ValueError(f"不支持的登录方式: platform={platform}, method={method}")

        except Exception as e:
            logger.error(f"[ConnectorService] Login error: {e}")
            raise

    async def cleanup(self):
        """清理所有连接器资源"""
        logger.info("[ConnectorService] Cleaning up all connectors")
        
        # 清理所有连接器
        for key, connector in self._connectors.items():
            try:
                if hasattr(connector, 'cleanup'):
                    connector.cleanup()
            except Exception as e:
                logger.error(f"[ConnectorService] Error cleaning up connector {key}: {e}")

        self._connectors.clear()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.cleanup()


# 全局服务实例
connector_service = ConnectorService()