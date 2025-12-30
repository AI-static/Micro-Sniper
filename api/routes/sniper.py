# -*- coding: utf-8 -*-
"""Sniper API 路由 - 简化版，支持任务记录和上下文追踪"""

from sanic import Blueprint, Request
from sanic.response import json, ResponseStream
import ujson as json_lib
import asyncio

from api.schema.base import BaseResponse, ErrorCode
from services.task_service import TaskService
from utils.logger import logger

sniper_bp = Blueprint("sniper", url_prefix="/sniper")


@sniper_bp.post("/xhs/harvest")
async def create_creator_task(request: Request):
    """创建创作者监控任务"""
    try:
        data = request.json
        creator_ids = data.get("creator_ids", [])

        if not creator_ids:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message="creator_ids 不能为空",
                data=None
            ).model_dump(), status=400)

        auth_info = request.ctx.auth_info

        # 先创建 Task，获取 task_id
        from models.task import Task
        from services.sniper.xhs_creator import CreatorSniper

        sniper = CreatorSniper(
            source_id=auth_info.source_id,
            source=auth_info.source.value,
            playwright=request.app.ctx.playwright
        )

        # 创建并启动任务
        task = await Task.create(
            source=auth_info.source.value,
            source_id=auth_info.source_id,
            task_type="creator_monitor"
        )
        await task.start()

        # 启动后台任务，传入已创建的 task 对象
        asyncio.create_task(sniper.monitor_creators(creator_ids, task=task))

        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message="任务已创建",
            data={
                "task_id": str(task.id),
                "message": f"创作者监控任务已在后台执行，监控 {len(creator_ids)} 个创作者"
            }
        ).model_dump())

    except Exception as e:
        logger.error(f"创建创作者监控任务失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            data=None
        ).model_dump(), status=500)


@sniper_bp.post("/xhs/trend")
async def create_trend_task(request: Request):
    """创建趋势分析任务"""
    try:
        data = request.json
        keywords = data.get("keywords", [])

        if not keywords:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message="keywords 不能为空",
                data=None
            ).model_dump(), status=400)

        auth_info = request.ctx.auth_info

        # 先创建 Task，获取 task_id
        from models.task import Task
        from services.sniper.xhs_trend import XiaohongshuDeepAgent

        agent = XiaohongshuDeepAgent(
            source_id=auth_info.source_id,
            source=auth_info.source.value,
            playwright=request.app.ctx.playwright,
            keywords=keywords
        )

        # 创建并启动任务
        task = await Task.create(
            source=auth_info.source.value,
            source_id=auth_info.source_id,
            task_type="trend_analysis"
        )
        await task.start()

        # 启动后台任务，传入已创建的 task 对象
        asyncio.create_task(agent.analyze_trends(task=task))

        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message="任务已创建",
            data={
                "task_id": str(task.id),
                "message": f"趋势分析任务已在后台执行，关键词: {keywords}"
            }
        ).model_dump())

    except Exception as e:
        logger.error(f"创建趋势分析任务失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            data=None
        ).model_dump(), status=500)


@sniper_bp.get("/task/<task_id:str>")
async def get_task(request: Request, task_id: str):
    """获取任务详情 - Agent 可读格式"""
    task_service = TaskService()
    task = await task_service.get_task(task_id)

    if not task:
        return json(BaseResponse(
            code=ErrorCode.NOT_FOUND,
            message="任务不存在",
            data=None
        ).model_dump(), status=404)

    return json(BaseResponse(
        code=ErrorCode.SUCCESS,
        message="获取成功",
        data=task.to_agent_readable()
    ).model_dump())


@sniper_bp.get("/task/<task_id:str>/logs")
async def get_logs(request: Request, task_id: str):
    """获取日志流"""
    offset = int(request.args.get("offset", 0))
    task_service = TaskService()
    data = await task_service.get_task_logs(task_id, offset)

    return json(BaseResponse(
        code=ErrorCode.SUCCESS,
        message="获取成功",
        data=data
    ).model_dump())


@sniper_bp.post("/tasks")
async def list_tasks(request: Request):
    """查询任务列表"""
    data = request.json or {}
    auth_info = request.ctx.auth_info
    task_service = TaskService()

    tasks = await task_service.list_tasks(
        source_id=data.get("source_id") or auth_info.source_id,
        status=data.get("status"),
        task_type=data.get("task_type"),
        limit=data.get("limit", 20)
    )

    return json(BaseResponse(
        code=ErrorCode.SUCCESS,
        message="获取成功",
        data={
            "tasks": [task.to_agent_readable() for task in tasks],
            "total": len(tasks)
        }
    ).model_dump())
