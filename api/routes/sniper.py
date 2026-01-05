# -*- coding: utf-8 -*-
"""Sniper API 路由 - 支持多平台趋势分析"""

from sanic import Blueprint, Request
from sanic.response import json
import asyncio

from api.schema.base import BaseResponse, ErrorCode
from services.task_service import TaskService
from utils.logger import logger
from models.connectors import PlatformType

sniper_bp = Blueprint("sniper", url_prefix="/sniper")

# 平台 Agent 映射
PLATFORM_AGENTS = {
    PlatformType.XIAOHONGSHU: "services.sniper.xhs_trend.XiaohongshuDeepAgent",
    PlatformType.DOUYIN: "services.sniper.douyin_trend.DouyinDeepAgent",
}


def _get_agent_class(platform: PlatformType):
    """动态导入平台 Agent 类"""
    if platform not in PLATFORM_AGENTS:
        raise ValueError(f"不支持的平台: {platform}")

    module_path = PLATFORM_AGENTS[platform]
    module_path_parts = module_path.split(".")
    module_name = ".".join(module_path_parts[:-1])
    class_name = module_path_parts[-1]

    import importlib
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


@sniper_bp.post("/<platform:str>/trend")
async def create_trend_task(request: Request, platform: str):
    """创建趋势分析任务（支持多平台）

    Args:
        platform: 平台名称 (xiaohongshu, douyin)
    """
    try:
        # 验证平台
        try:
            platform_type = PlatformType(platform)
        except ValueError:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"不支持的平台: {platform}，支持的平台: xiaohongshu, douyin",
                data=None
            ).model_dump(), status=400)

        data = request.json
        keywords = data.get("keywords", [])

        if not keywords:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message="keywords 不能为空",
                data=None
            ).model_dump(), status=400)

        auth_info = request.ctx.auth_info

        # 导入 Agent 类
        agent_class = _get_agent_class(platform_type)

        # 创建 Agent 实例
        agent = agent_class(
            source_id=auth_info.source_id,
            source=auth_info.source.value,
            playwright=request.app.ctx.playwright,
            keywords=keywords
        )

        # 创建并启动任务
        from models.task import Task
        task = await Task.create(
            source=auth_info.source.value,
            source_id=auth_info.source_id,
            task_type=f"trend_analysis_{platform}"
        )
        await task.start()

        # 启动后台任务
        asyncio.create_task(agent.analyze_trends(task=task))

        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message="任务已创建",
            data={
                "task_id": str(task.id),
                "platform": platform,
                "message": f"{platform} 趋势分析任务已在后台执行，关键词: {keywords}"
            }
        ).model_dump())

    except Exception as e:
        logger.error(f"创建趋势分析任务失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            data=None
        ).model_dump(), status=500)


@sniper_bp.post("/<platform:str>/harvest")
async def create_harvest_task(request: Request, platform: str):
    """创建创作者监控任务（支持多平台）

    Args:
        platform: 平台名称 (xiaohongshu, douyin)
    """
    try:
        # 验证平台
        try:
            platform_type = PlatformType(platform)
        except ValueError:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"不支持的平台: {platform}，支持的平台: xiaohongshu, douyin",
                data=None
            ).model_dump(), status=400)

        data = request.json
        creator_ids = data.get("creator_ids", [])

        if not creator_ids:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message="creator_ids 不能为空",
                data=None
            ).model_dump(), status=400)

        auth_info = request.ctx.auth_info

        # 导入对应的 Sniper 类
        if platform_type == PlatformType.XIAOHONGSHU:
            from services.sniper.xhs_creator import CreatorSniper
            sniper_class = CreatorSniper
        elif platform_type == PlatformType.DOUYIN:
            # TODO: 创建 douyin_creator.py
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"{platform} 创作者监控功能开发中",
                data=None
            ).model_dump(), status=501)
        else:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"平台 {platform} 暂不支持创作者监控",
                data=None
            ).model_dump(), status=400)

        # 创建 Sniper 实例
        sniper = sniper_class(
            source_id=auth_info.source_id,
            source=auth_info.source.value,
            playwright=request.app.ctx.playwright
        )

        # 创建并启动任务
        from models.task import Task
        task = await Task.create(
            source=auth_info.source.value,
            source_id=auth_info.source_id,
            task_type=f"creator_monitor_{platform}"
        )
        await task.start()

        # 启动后台任务
        asyncio.create_task(sniper.monitor_creators(creator_ids, task=task))

        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message="任务已创建",
            data={
                "task_id": str(task.id),
                "platform": platform,
                "message": f"{platform} 创作者监控任务已在后台执行，监控 {len(creator_ids)} 个创作者"
            }
        ).model_dump())

    except Exception as e:
        logger.error(f"创建创作者监控任务失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            data=None
        ).model_dump(), status=500)


@sniper_bp.get("/task/<task_id:str>")
async def get_task(request: Request, task_id: str):
    """获取任务详情"""
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
        source=data.get("source") or auth_info.source.value,
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


@sniper_bp.get("/platforms")
async def get_platforms(request: Request):
    """获取支持的平台列表"""
    platforms = [
        {
            "name": "xiaohongshu",
            "display_name": "小红书",
            "features": ["trend_analysis", "creator_monitor"],
            "description": "小红书平台爆款分析和创作者监控"
        },
        {
            "name": "douyin",
            "display_name": "抖音",
            "features": ["trend_analysis"],
            "description": "抖音平台爆款分析"
        }
    ]

    return json(BaseResponse(
        code=ErrorCode.SUCCESS,
        message="获取成功",
        data={"platforms": platforms}
    ).model_dump())