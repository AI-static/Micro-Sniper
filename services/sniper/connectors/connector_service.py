"""
连接器服务层 - 统一的连接器管理和调度

提供四大核心功能：
- 监控 (monitor): 持续追踪URL变化，实时推送更新
- 提取 (extract): 一次性获取指定URL的内容
- 采收 (harvest): 批量获取用户/账号的所有内容
- 发布 (publish): 发布内容到指定平台
"""

from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from pydantic import BaseModel, Field

from .xiaohongshu import XiaohongshuConnector
from .wechat import WechatConnector
from .douyin import DouyinConnector
from utils.logger import logger
from utils.cache import distributed_lock, check_rate_limit
from utils.exceptions import RateLimitException, LockConflictException
from models.connectors import PlatformType, LoginMethod
from models.task import Task


class OperationRateLimit(BaseModel):
    """操作级别的频率限制配置"""
    max_requests: int = Field(..., description="时间窗口内最大请求数")
    window: int = Field(..., description="时间窗口（秒）")
    lock_timeout: int = Field(..., description="锁超时时间（秒）")


class PlatformRateLimits(BaseModel):
    """平台级别的频率限制配置"""
    login: Optional[OperationRateLimit] = None
    get_note_detail: Optional[OperationRateLimit] = None
    harvest_user_content: Optional[OperationRateLimit] = None
    search_and_extract: Optional[OperationRateLimit] = None
    publish_content: Optional[OperationRateLimit] = None


class RateLimitConfigs(BaseModel):
    """所有平台的频率限制配置"""
    xiaohongshu: PlatformRateLimits
    wechat: PlatformRateLimits
    douyin: PlatformRateLimits


RATE_LIMIT_CONFIGS = RateLimitConfigs(
    xiaohongshu=PlatformRateLimits(
        login=OperationRateLimit(max_requests=3, window=60, lock_timeout=120),
        get_note_detail=OperationRateLimit(max_requests=10, window=60, lock_timeout=180),
        harvest_user_content=OperationRateLimit(max_requests=5, window=60, lock_timeout=300),
        search_and_extract=OperationRateLimit(max_requests=10, window=60, lock_timeout=180),
        publish_content=OperationRateLimit(max_requests=2, window=60, lock_timeout=300),
    ),
    wechat=PlatformRateLimits(
        login=OperationRateLimit(max_requests=3, window=60, lock_timeout=120),
        get_note_detail=OperationRateLimit(max_requests=10, window=60, lock_timeout=180),
        harvest_user_content=OperationRateLimit(max_requests=5, window=60, lock_timeout=300),
    ),
    douyin=PlatformRateLimits(
        login=OperationRateLimit(max_requests=3, window=60, lock_timeout=120),
        get_note_detail=OperationRateLimit(max_requests=10, window=60, lock_timeout=180),
        harvest_user_content=OperationRateLimit(max_requests=5, window=60, lock_timeout=300),
        search_and_extract=OperationRateLimit(max_requests=10, window=60, lock_timeout=180),
        publish_content=OperationRateLimit(max_requests=2, window=60, lock_timeout=300),
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

    @classmethod
    async def cleanup_all_locks(cls):
        """清理所有锁（程序关闭时调用）

        注意：
        - 锁的 key 格式：lock:{source}:{source_id}:{platform}:{operation}
        - 此方法仅在服务关闭时调用，用于清理所有残留的分布式锁
        - 正常情况下，任务退出时会通过 cleanup() 释放锁
        """
        from utils.cache import get_redis

        redis_client = await get_redis()
        count = 0

        try:
            # 清理所有锁
            async for key in redis_client.scan_iter(match="lock:*", count=100):
                await redis_client.delete(key)
                count += 1

            if count > 0:
                logger.info(f"[ConnectorService] Cleaned up {count} locks (all)")
        except Exception as e:
            logger.error(f"[ConnectorService] Error cleaning up all locks: {e}")

    def __init__(self, playwright, source, source_id, task: Optional[Task]):
        """初始化连接器服务

        Args:
            playwright: Playwright 实例，如果不提供则 connector 会从 Sanic app 获取
            source: 系统标识
            source_id: 用户标识
            task: 任务对象
        """
        self._connectors = {}
        self._playwright = playwright
        self._source = source
        self._source_id = source_id
        self._task = task
        self.connector = None

        # 实例级别的锁追踪（只追踪当前实例持有的锁）
        self._held_locks: List[str] = []

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

        Args:
            platform: 平台类型
            operation: 操作名称
            func: 要执行的函数
        """
        config = getattr(RATE_LIMIT_CONFIGS, platform.value)
        limit_config = getattr(config, operation, None)

        if not limit_config:
            return await func()

        # task_id 是必填的
        if not self._task:
            raise ValueError("task_id is required for lock management")

        task_id = str(self._task.id)
        # 键格式：lock:{source}:{source_id}:{platform}:{operation}
        # 不包含 task_id，使得锁的粒度是用户级别的，不同任务竞争同一个锁
        key = f"{self._source}:{self._source_id}:{platform.value}:{operation}"

        # 检查频率限制
        if not await check_rate_limit(key, limit_config.max_requests, limit_config.window):
            raise RateLimitException(f"频率限制：{operation} 操作过于频繁，请稍后再试")

        # 获取分布式锁
        async with distributed_lock(key, task_id, limit_config.lock_timeout):
            # 追踪当前实例持有的锁
            self._held_locks.append(key)
            return await func()

    def _get_connector(self, platform: PlatformType):
        """获取或创建平台连接器

        Args:
            platform: 平台名称 (xiaohongshu/wechat/douyin)
            source: 系统标识
            source_id: 用户标识

        Returns:
            对应的连接器实例

        Raises:
            ValueError: 不支持的平台
        """
        if isinstance(platform, str):
            platform = PlatformType(platform)

        if platform not in self._connectors:
            if platform == PlatformType.XIAOHONGSHU:
                self._connectors[platform] = XiaohongshuConnector(playwright=self._playwright)
            elif platform == PlatformType.WECHAT:
                self._connectors[platform] = WechatConnector(playwright=self._playwright)
            elif platform == PlatformType.DOUYIN:
                self._connectors[platform] = DouyinConnector(playwright=self._playwright)
            else:
                raise ValueError(f"不支持的平台: {platform}")

        return self._connectors[platform]

    # ==================== 核心 API ====================

    async def get_note_details(
        self,
        urls: List[str],
        platform: PlatformType,
        concurrency: int = 2
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
        self.connector = connector
        async def _execute():
            logger.info(f"[ConnectorService] Getting note details for {len(urls)} URLs from {platform}, concurrency={concurrency}, source={self._source}, source_id={self._source_id}")
            results = await connector.get_note_detail(urls, source=self._source, source_id=self._source_id, concurrency=concurrency)
            success_count = sum(1 for r in results if r.get("success"))
            logger.info(f"[ConnectorService] Get note details completed: {success_count}/{len(results)} successful")
            return results

        return await self._execute_with_lock_and_limit(platform, "get_note_detail", _execute)


    async def publish_content(
        self,
        platform: PlatformType,
        content: str,
        content_type: str = "text",
        images: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """发布内容到平台

        Args:
            platform: 平台名称
            content: 内容文本
            content_type: 内容类型 (text/image/video)
            images: 图片URL列表
            tags: 标签列表

        Returns:
            发布结果字典，包含 success、platform 等字段
        """
        connector = self._get_connector(platform)
        self.connector = connector

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
        platform: PlatformType,
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
        self.connector = connector
        
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
        
        return await self._execute_with_lock_and_limit(platform, "harvest_user_content", _execute)
    
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
        self.connector = connector
        
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
            method: 登录方法 (支持 qrcode 和 cookie)
            cookies: Cookie 数据（仅用于 cookie 登录）

        Returns:
            是否登录成功
        """
        # Cookie 登录
        if method == LoginMethod.COOKIE:
            if not cookies:
                raise ValueError("Cookie 登录需要提供 cookies 参数")

            connector = self._get_connector(platform)
            self.connector = connector

            async def _execute():
                logger.info(f"[ConnectorService] Logging in to {platform} with cookies for source:{self._source}, source_id:{self._source_id}")
                context_id = await connector.login_with_cookies(cookies, self._source, self._source_id)
                logger.info(f"[ConnectorService] Login Res: context_id: {context_id}")
                return context_id

            return await self._execute_with_lock_and_limit(platform, "login", _execute)

        # 二维码登录
        elif method == LoginMethod.QRCODE:
            connector = self._get_connector(platform)
            self.connector = connector

            async def _execute():
                logger.info(f"[ConnectorService] QRCode login to {platform} for source:{self._source}, source_id:{self._source_id}")
                result = await connector.login_with_qrcode(self._source, self._source_id)
                logger.info(f"[ConnectorService] QRCode login result: {result.get('message', 'success')}")
                return result

            return await self._execute_with_lock_and_limit(platform, "login", _execute)

        else:
            raise ValueError(f"不支持的登录方式: platform={platform}, method={method}")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出

        统一负责任务状态管理：
        - 无异常 -> COMPLETED（保存返回值）
        - CancelledError -> CANCELLED
        - 其他异常 -> FAILED
        """
        if self._task:
            from models.task import TaskStatus
            import asyncio

            task_id = str(self._task.id)

            # 如果是任务被取消（CancelledError），标记为 CANCELLED
            if exc_type is asyncio.CancelledError:
                logger.info(f"[ConnectorService] Task {task_id} was cancelled, marking as CANCELLED")
                if self._task.status != TaskStatus.CANCELLED:
                    await self._task.cancel()

            # 如果任务正在运行或等待登录且发生了其他异常，将其标记为失败
            elif self._task.status in [TaskStatus.RUNNING, TaskStatus.WAITING_LOGIN] and exc_val:
                error_msg = "任务被异常终止"
                if exc_val:
                    error_msg = f"任务被异常终止: {str(exc_val)}"
                await self._task.fail(error_msg, current_progress=self._task.progress)
                logger.warning(f"[ConnectorService] Task {task_id} was {self._task.status}, marked as failed on exit")

            # 如果任务仍在运行且没有异常，说明正常完成
            # 检查是否有返回值需要保存
            elif self._task.status in [TaskStatus.RUNNING, TaskStatus.PENDING] and not exc_val:
                # 获取 Agent 的返回值（如果有的话）
                # 注意：__aexit__ 无法直接获取 async with 块的返回值
                # 需要 Agent 在完成时自己保存结果
                logger.debug(f"[ConnectorService] Task {task_id} 正常退出，等待 Agent 保存结果")

        # 调用清理方法
        await self.cleanup()

    async def cleanup(self):
        """清理 ConnectorService 资源

        包括：
        1. 释放所有持有的分布式锁
        2. 清理 connector 实例
        """
        # 1. 释放所有持有的分布式锁
        if self._held_locks:
            from utils.cache import get_redis
            redis_client = await get_redis()
            released_count = 0

            for lock_key in self._held_locks:
                full_lock_key = f"lock:{lock_key}"
                try:
                    # 使用 Lua 脚本安全删除锁
                    lua_script = """
                    if redis.call("exists", KEYS[1]) == 1 then
                        return redis.call("del", KEYS[1])
                    else
                        return 0
                    end
                    """
                    result = await redis_client.eval(lua_script, 1, full_lock_key)
                    if result:
                        released_count += 1
                        logger.debug(f"[ConnectorService] Released lock: {full_lock_key}")
                except Exception as e:
                    logger.error(f"[ConnectorService] Error releasing lock {full_lock_key}: {e}")

            logger.info(f"[ConnectorService] Released {released_count}/{len(self._held_locks)} locks")
            self._held_locks.clear()
