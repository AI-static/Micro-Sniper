# -*- coding: utf-8 -*-
"""任务超时检查器 - 轮询模式 + Redis 分布式锁"""

import asyncio
from datetime import datetime, timedelta, timezone
from utils.logger import logger
from models.task import Task, TaskStatus
from utils.cache import get_redis
from config.settings import settings


class TaskTimeoutChecker:
    """任务超时检查器 - 定期扫描并标记超时任务"""

    # 检查间隔（秒）
    CHECK_INTERVAL = 60

    # Redis 锁配置
    LOCK_KEY = "task_timeout_checker:lock"
    LOCK_TIMEOUT = 70  # 锁超时（必须 > CHECK_INTERVAL）

    def __init__(self):
        self._running = False
        self._task = None

    async def start(self):
        """启动超时检查器"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        logger.info("⏱️ 任务超时检查器已启动（Redis 分布式锁）")

    async def stop(self):
        """停止超时检查器"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("⏱️ 任务超时检查器已停止")

    async def _check_loop(self):
        """定期检查超时任务"""
        while self._running:
            try:
                # 尝试获取锁
                acquired = await self._try_acquire_lock()

                if acquired:
                    logger.debug("获取到锁，执行超时检查")
                    try:
                        await self._check_timeouts()
                    finally:
                        # 释放锁
                        await self._release_lock()
                else:
                    logger.debug("未获取到锁，跳过本次检查")

                await asyncio.sleep(self.CHECK_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"超时检查出错: {e}")
                await asyncio.sleep(self.CHECK_INTERVAL)

    async def _try_acquire_lock(self) -> bool:
        """尝试获取锁"""
        try:
            redis = await get_redis()
            # SET key value NX EX seconds
            result = await redis.set(
                self.LOCK_KEY,
                "locked",
                nx=True,
                ex=self.LOCK_TIMEOUT
            )
            return result is True
        except Exception as e:
            logger.error(f"获取锁失败: {e}")
            return False

    async def _release_lock(self):
        """释放锁"""
        try:
            redis = await get_redis()
            await redis.delete(self.LOCK_KEY)
        except Exception as e:
            logger.error(f"释放锁失败: {e}")

    async def _check_timeouts(self):
        """检查并标记超时任务"""
        # 使用带时区的 UTC 时间
        now = datetime.now(timezone.utc)

        # 从配置中获取统一的超时时间
        timeout_seconds = settings.task.timeout

        # 查找所有运行中的任务
        running_tasks = await Task.filter(
            status=TaskStatus.RUNNING.value
        ).all()

        for task in running_tasks:
            # 检查是否超时
            # 确保 task.started_at 带有时区信息
            if task.started_at.tzinfo is None:
                # 如果没有时区，假设是 UTC 并添加时区
                started_at = task.started_at.replace(tzinfo=timezone.utc)
            else:
                started_at = task.started_at

            timeout_threshold = started_at + timedelta(seconds=timeout_seconds)

            if now > timeout_threshold:
                logger.warning(
                    f"任务 {task.id} ({task.task_type}) 超时，"
                    f"开始时间: {task.started_at}, "
                    f"超时阈值: {timeout_threshold}, "
                    f"当前时间: {now}"
                )

                # 标记任务为失败
                await task.fail(
                    f"任务执行超时（超过 {timeout_seconds} 秒）",
                    task.progress
                )

                logger.info(f"已标记超时任务 {task.id} 为失败状态")


# 全局单例
timeout_checker = TaskTimeoutChecker()
