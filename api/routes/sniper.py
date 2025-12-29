# -*- coding: utf-8 -*-
"""Sniper API 路由 - 简化版，支持任务记录和上下文追踪"""

from sanic import Blueprint, Request
from sanic.response import json, ResponseStream
import ujson as json_lib
import asyncio

from api.schema.base import BaseResponse, ErrorCode
from services.sniper.task_service import TaskService
from utils.logger import logger

sniper_bp = Blueprint("sniper", url_prefix="/sniper")


@sniper_bp.post("/xhs-creator")
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

        # 启动后台执行
        from services.sniper.xhs_creator import CreatorSniper
        background_task = asyncio.create_task(
            _run_creator_monitor(request.app.ctx.playwright, creator_ids, auth_info)
        )

        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message="任务已创建",
            data={
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


async def _run_creator_monitor(playwright, creator_ids, auth_info):
    """后台执行创作者监控"""
    from services.sniper.xhs_creator import CreatorSniper
    
    try:
        sniper = CreatorSniper(
            source_id=auth_info.source_id,
            source=auth_info.source.value,
            playwright=playwright
        )
        
        # 调用 monitor_creators 方法，内部会创建 Task 并管理状态
        task, report = await sniper.monitor_creators(creator_ids)
        logger.info(f"创作者监控任务完成: {task.id}")
        logger.info(f"监控结果: 发现 {report.count('新增笔记')} 篇新笔记" if '新增笔记' in report else "监控完成")
        
    except Exception as e:
        logger.error(f"创作者监控失败: {e}")
        import traceback
        traceback.print_exc()
        raise


@sniper_bp.post("/xhs-trend")
async def create_trend_task(request: Request):
    """创建趋势分析任务"""
    try:
        data = request.json
        keywords = data.get("keywords", [])

        auth_info = request.ctx.auth_info

        from services.sniper.xhs_trend import XiaohongshuDeepAgent
        background_task = asyncio.create_task(
            _run_trend_analysis(request.app.ctx.playwright, keywords, auth_info)
        )

        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message="任务已创建",
            data={
                "message": "趋势分析任务已在后台执行，请到任务列表查看"
            }
        ).model_dump())

    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            data=None
        ).model_dump(), status=500)


async def _run_trend_analysis(playwright, keywords, auth_info):
    """后台执行趋势分析"""
    from services.sniper.xhs_trend import XiaohongshuDeepAgent
    
    try:
        agent = XiaohongshuDeepAgent(
            source_id=auth_info.source_id,
            source=auth_info.source.value,
            playwright=playwright,
            keywords=keywords[0] if keywords else ""
        )
        
        # 调用 analyze_trends 方法，内部会创建 Task 并管理状态
        task_id = await agent.analyze_trends()
        logger.info(f"趋势分析任务完成: {task_id}")
        
    except Exception as e:
        logger.error(f"趋势分析失败: {e}")
        raise


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
