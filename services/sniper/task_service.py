# -*- coding: utf-8 -*-
"""Task 服务 - 简化版，直接操作 Task 模型"""

import asyncio
from typing import Optional, List
from datetime import datetime

from models.task import Task, TaskStatus
from utils.logger import logger


class TaskService:
    """任务服务 - 提供 Task 的 CRUD 和状态管理"""

    def __init__(self, playwright=None):
        self.playwright = playwright
        self._running_tasks = {}  # task_id -> asyncio.Task

    async def create_task(self, source_id: str, task_type: str, source: str = "system") -> Task:
        """创建任务"""
        task = await Task.create(
            source=source,
            source_id=source_id,
            task_type=task_type
        )
        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return await Task.filter(id=task_id).first()

    async def list_tasks(
        self,
        source_id: Optional[str] = None,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Task]:
        """查询任务列表"""
        query = Task.all()
        if source_id:
            query = query.filter(source_id=source_id)
        if status:
            query = query.filter(status=status)
        if task_type:
            query = query.filter(task_type=task_type)
        return await query.order_by("-created_at").limit(limit)

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = await self.get_task(task_id)
        if not task:
            return False

        # 取消后台任务
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            self._running_tasks.pop(task_id, None)

        await task.cancel()
        return True

    async def get_task_logs(self, task_id: str, offset: int = 0) -> dict:
        """获取任务日志"""
        task = await self.get_task(task_id)
        if not task:
            return {"logs": [], "has_more": False}

        logs = task.logs[offset:]
        return {
            "logs": logs,
            "has_more": len(task.logs) > offset + len(logs)
        }

    # ===== 后台任务执行器 =====

    def _start_background_task(self, task: Task, coro):
        """启动后台任务"""
        async def wrapper():
            try:
                await coro
            except Exception as e:
                logger.error(f"后台任务异常: {task.id}, {e}")
                if task.status == TaskStatus.RUNNING:
                    await task.fail(str(e))

        background_task = asyncio.create_task(wrapper())
        self._running_tasks[str(task.id)] = background_task

        # 清理回调
        background_task.add_done_callback(
            lambda t: self._running_tasks.pop(str(task.id), None)
        )
