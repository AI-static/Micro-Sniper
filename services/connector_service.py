"""
连接器服务层 - 统一的连接器管理和调度

提供四大核心功能：
- 监控 (monitor): 持续追踪URL变化，实时推送更新
- 提取 (extract): 一次性获取指定URL的内容
- 采收 (harvest): 批量获取用户/账号的所有内容
- 发布 (publish): 发布内容到指定平台
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
from pydantic import BaseModel, Field

from services.connectors.xiaohongshu import XiaohongshuConnector
from services.connectors.wechat import WechatConnector
from utils.logger import logger
from utils.cache import distributed_lock, check_rate_limit
from utils.exceptions import RateLimitException, LockConflictException
from models.connectors import PlatformType, LoginMethod


class OperationRateLimit(BaseModel):
    """操作级别的频率限制配置"""
    max_requests: int = Field(..., description="时间窗口内最大请求数")
    window: int = Field(..., description="时间窗口（秒）")
    lock_timeout: int = Field(..., description="锁超时时间（秒）")


class PlatformRateLimits(BaseModel):
    """平台级别的频率限制配置"""
    login: Optional[OperationRateLimit] = None
    extract_summary_stream: Optional[OperationRateLimit] = None
    get_note_detail: Optional[OperationRateLimit] = None
    harvest_user_content: Optional[OperationRateLimit] = None
    search_and_extract: Optional[OperationRateLimit] = None
    publish_content: Optional[OperationRateLimit] = None


class RateLimitConfigs(BaseModel):
    """所有平台的频率限制配置"""
    xiaohongshu: PlatformRateLimits
    wechat: PlatformRateLimits


RATE_LIMIT_CONFIGS = RateLimitConfigs(
    xiaohongshu=PlatformRateLimits(
        login=OperationRateLimit(max_requests=3, window=60, lock_timeout=120),
        extract_summary_stream=OperationRateLimit(max_requests=10, window=60, lock_timeout=300),
        get_note_detail=OperationRateLimit(max_requests=10, window=60, lock_timeout=180),
        harvest_user_content=OperationRateLimit(max_requests=5, window=60, lock_timeout=300),
        extract_by_creator_id=OperationRateLimit(max_requests=5, window=60, lock_timeout=300),
        search_and_extract=OperationRateLimit(max_requests=10, window=60, lock_timeout=180),
        publish_content=OperationRateLimit(max_requests=2, window=60, lock_timeout=300),
    ),
    wechat=PlatformRateLimits(
        login=OperationRateLimit(max_requests=3, window=60, lock_timeout=120),
        extract_summary_stream=OperationRateLimit(max_requests=10, window=60, lock_timeout=300),
        get_note_detail=OperationRateLimit(max_requests=10, window=60, lock_timeout=180),
        harvest_user_content=OperationRateLimit(max_requests=5, window=60, lock_timeout=300),
    )
)


class ConnectorService:
    """连接器服务 - 统一的连接器管理和调度中心
    
    设计原则：
    - connector 实例按平台缓存，不再按 source:source_id
    - source/source_id 由各 connector 在调用时自行处理
    - playwright 实例可外部传入，支持独立脚本运行
    """

    # 平台标识映射
    PLATFORM_IDENTIFIERS = {
        PlatformType.XIAOHONGSHU: ["xiaohongshu.com", "xhslink.com"],
        PlatformType.WECHAT: ["mp.weixin.qq.com"],
    }

    def __init__(self, playwright, source, source_id):
        """初始化连接器服务
        
        Args:
            playwright: Playwright 实例，如果不提供则 connector 会从 Sanic app 获取
        """
        self._connectors = {}
        self._playwright = playwright
        self._source = source
        self._source_id = source_id

    async def _execute_with_lock_and_limit(
        self,
        platform: PlatformType,
        operation: str,
        func
    ):
        """在锁和频率限制保护下执行操作
        
        Raises:
            RateLimitException: 频率限制超限
            LockConflictException: 锁冲突，正在运行相同任务
        """
        config = getattr(RATE_LIMIT_CONFIGS, platform.value)
        limit_config = getattr(config, operation, None)
        
        if not limit_config:
            return await func()
        
        key = f"{self._source}:{self._source_id}:{platform.value}:{operation}"
        
        # 检查频率限制
        if not await check_rate_limit(key, limit_config.max_requests, limit_config.window):
            raise RateLimitException(f"频率限制：{operation} 操作过于频繁，请稍后再试")
        
        # 获取分布式锁
        try:
            async with distributed_lock(key, limit_config.lock_timeout):
                return await func()
        except Exception as e:
            if "Failed to acquire lock" in str(e):
                raise LockConflictException(f"当前正在运行另外一个 {platform.value}:{operation} 任务，请等待完成后再试")
            raise

    def _get_connector(self, platform: PlatformType):
        """获取或创建平台连接器

        Args:
            platform: 平台名称 (xiaohongshu/wechat)
            source: 系统标识
            source_id: 用户标识

        Returns:
            对应的连接器实例

        Raises:
            ValueError: 不支持的平台
        """
        if isinstance(platform, str):
            platform = PlatformType(platform)
        
        # 使用 source:source_id 缓存 connector 实例，确保每个会话有独立的 connector
        cache_key = f"{platform.value}:{self._source}:{self._source_id}"
        
        if cache_key not in self._connectors:
            if platform == PlatformType.XIAOHONGSHU:
                self._connectors[cache_key] = XiaohongshuConnector(playwright=self._playwright)
            elif platform == PlatformType.WECHAT:
                self._connectors[cache_key] = WechatConnector(playwright=self._playwright)
            else:
                raise ValueError(f"不支持的平台: {platform}")

        return self._connectors[cache_key]

    # ==================== 核心 API ====================

    async def extract_summary_stream(
        self,
        urls: List[str],
        platform: PlatformType,
        concurrency: int = 10
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式提取URL内容摘要

        Args:
            urls: 要提取的URL列表
            platform: 平台名称（必须指定）
            concurrency: 并发数量

        Yields:
            提取结果字典，包含 url、success、data 等字段
        """
        try:
            connector = self._get_connector(platform)
            logger.info(f"[ConnectorService] Streaming extraction from {platform}, {len(urls)} URLs, source={self._source}, source_id={self._source_id}")
            
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
                async for result in connector.extract_summary_stream(urls, concurrency, self._source, self._source_id):
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
        concurrency: int = 2,
    ) -> List[Dict[str, Any]]:
        """获取笔记/文章详情（快速提取，不使用Agent）

        Args:
            urls: 要提取的URL列表
            platform: 平台名称
            concurrency: 并发数（默认2）

        Returns:
            提取结果列表，每个元素包含 url、success、data 等字段
        """
        connector = self._get_connector(platform)
        
        async def _execute():
            logger.info(f"[ConnectorService] Getting note details for {len(urls)} URLs from {platform}, concurrency={concurrency}, source={self._source}, source_id={self._source_id}")
            results = await connector.get_note_detail(urls, source=self._source, source_id=self._source_id, concurrency=concurrency)
            success_count = sum(1 for r in results if r.get("success"))
            logger.info(f"[ConnectorService] Get note details completed: {success_count}/{len(results)} successful")
            return results
        
        return await self._execute_with_lock_and_limit(platform, "get_note_detail", _execute)


    async def publish_content(
        self,
        platform: str | PlatformType,
        content: str,
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

        Returns:
            发布结果字典，包含 success、platform 等字段
        """
        connector = self._get_connector(platform)
        
        async def _execute():
            logger.info(f"[ConnectorService] Publishing content to {platform}, type={content_type}, source={self._source}, source_id={self._source_id}")
            result = await connector.publish_content(content, content_type, images, tags, source=self._source, source_id=self._source_id)
            status = "successful" if result.get("success") else "failed"
            logger.info(f"[ConnectorService] Publish {status}")
            return result
        
        try:
            return await self._execute_with_lock_and_limit(platform, "publish_content", _execute)
        except NotImplementedError:
            raise ValueError(f"平台 {platform} 不支持发布功能")

    async def harvest_user_content(
        self,
        platform: str | PlatformType,
        creator_ids: List[str],
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """通过创作者ID提取内容

        Args:harvest_user_content
            platform: 平台名称
            creator_id: 创作者ID
            source: 系统标识
            source_id: 用户标识
            limit: 限制数量

        Returns:
            提取结果列表
        """
        connector = self._get_connector(platform)
        
        async def _execute():
            logger.info(f"[ConnectorService] Extracting by creator ID from {platform}, creators={creator_ids}, source={self._source}, source_id={self._source_id}")
            results = await connector.harvest_user_content(
                creator_ids=creator_ids,
                limit=limit,
                source=self._source,
                source_id=self._source_id
            )
            logger.info(f"[ConnectorService] Extracted {len(results)} items by creator ID")
            return results
        
        return await self._execute_with_lock_and_limit(platform, "extract_by_creator_id", _execute)
    
    async def search_and_extract(
        self,
        platform: PlatformType,
        keywords: List[str],
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """搜索并提取内容

        Args:
            platform: 平台名称
            keyword: 搜索关键词
            source: 系统标识
            source_id: 用户标识
            limit: 限制数量

        Returns:
            搜索结果列表
        """
        connector = self._get_connector(platform)
        
        async def _execute():
            logger.info(f"[ConnectorService] Searching and extracting from {platform}, keywords={keywords}, source={self._source}, source_id={self._source_id}")
            results = await connector.search_and_extract(
                keywords=keywords,
                limit=limit,
                source=self._source,
                source_id=self._source_id
            )
            logger.info(f"[ConnectorService] Found {len(results)} search results")
            return results
        
        return await self._execute_with_lock_and_limit(platform, "search_and_extract", _execute)

    async def login(
        self,
        platform: PlatformType,
        method: LoginMethod,
        cookies: dict = None
    ) -> bool:
        """登录平台

        Args:
            platform: 平台名称
            method: 登录方法 (目前仅支持 cookie)
            cookies: Cookie 数据

        Returns:
            是否登录成功
        """
        if platform == PlatformType.XIAOHONGSHU and method == LoginMethod.COOKIE:
            if not cookies:
                raise ValueError("Cookie 登录需要提供 cookies 参数")

            connector = self._get_connector(platform)
            
            async def _execute():
                logger.info(f"[ConnectorService] Logging in to {platform} with cookies for source:{self._source}, source_id:{self._source_id}")
                context_id = await connector.login_with_cookies(cookies, self._source, self._source_id)
                logger.info(f"[ConnectorService] Login Res: context_id: {context_id}")
                return context_id
            
            return await self._execute_with_lock_and_limit(platform, "login", _execute)
        elif platform == PlatformType.XIAOHONGSHU and method == LoginMethod.QRCODE:
            connector = self._get_connector(platform)
            
            async def _execute():
                logger.info(f"[ConnectorService] QRCode login to {platform} for source:{self._source}, source_id:{self._source_id}")
                result = await connector.login_with_qrcode(self._source, self._source_id)
                logger.info(f"[ConnectorService] QRCode login result: {result.get('message')}")
                return result
            
            return await self._execute_with_lock_and_limit(platform, "login", _execute)
        else:
            raise ValueError(f"不支持的登录方式: platform={platform}, method={method}")

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
