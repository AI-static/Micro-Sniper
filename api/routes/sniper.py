# -*- coding: utf-8 -*-
"""Sniper API 路由 - 支持 Agent/Workflow 任务执行"""

from sanic import Blueprint, Request
from sanic.response import json
import asyncio

from api.schema.base import BaseResponse, ErrorCode
from services.task_service import TaskService
from utils.logger import logger

# 导入所有 Agent 类
from services.sniper.xhs_trend import XiaohongshuTrendAgent
from services.sniper.xhs_creator import CreatorSniper
from services.sniper.douyin_trend import DouyinDeepAgent

sniper_bp = Blueprint("sniper", url_prefix="/sniper")

# Agent/Workflow 映射表 - 直接存储类对象
AGENT_WORKFLOW_MAPPING = {
    # 小红书 Agent
    "xhs_trend_agent": XiaohongshuTrendAgent,
    "xhs_creator_sniper": CreatorSniper,

    # 抖音 Agent
    "douyin_trend_agent": DouyinDeepAgent,

    # 可以继续添加更多 Agent 和 Workflow
    # "custom_workflow": CustomWorkflow,
}


@sniper_bp.post("/execute")
async def execute_agent(request: Request):
    """执行 Agent/Workflow 任务（统一入口）

    Body:
        agent_or_workflow: Agent/Workflow 唯一标识（如 "xhs_trend_agent"）
        params: 传递给 Agent 的参数（如 {"keywords": ["美食", "旅游"]}）
    """
    try:
        from models.task import Task

        data = request.json
        agent_id = data.get("agent_or_workflow")
        params = data.get("params", {})

        if not agent_id:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message="agent_or_workflow 不能为空",
                data=None
            ).model_dump(), status=400)

        if agent_id not in AGENT_WORKFLOW_MAPPING:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"不支持的 Agent/Workflow: {agent_id}",
                data=None
            ).model_dump(), status=400)

        auth_info = request.ctx.auth_info

        # 创建任务
        task = await Task.create(
            source=auth_info.source.value,
            source_id=auth_info.source_id,
            task_type=agent_id
        )
        await task.start()

        # 获取 Agent 类
        agent_class = AGENT_WORKFLOW_MAPPING[agent_id]

        # 在后台执行 Agent
        asyncio.create_task(_run_agent_task(agent_class, request, task, **params))

        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message="任务已创建",
            data={
                "task_id": str(task.id),
                "agent_or_workflow": agent_id,
                "message": f"{agent_id} 任务已在后台执行"
            }
        ).model_dump())

    except Exception as e:
        logger.error(f"执行 Agent 任务失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            data=None
        ).model_dump(), status=500)


async def _run_agent_task(agent_class, request: Request, task, **kwargs):
    """在后台运行 Agent 任务

    Args:
        agent_class: Agent 类对象
        request: Sanic Request 对象
        task: 任务对象
        **kwargs: 传递给 Agent 的参数
    """
    try:
        # 创建实例
        auth_info = request.ctx.auth_info
        agent = agent_class(
            source_id=auth_info.source_id,
            source=auth_info.source.value,
            playwright=request.app.ctx.playwright,
            **kwargs
        )

        # 执行任务 - 所有 Agent/Workflow 统一使用 execute 方法
        await agent.execute(task=task)

    except Exception as e:
        logger.error(f"Agent {agent_class.__name__} 执行失败: {e}")
        await task.fail(str(e), 0)


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


@sniper_bp.get("/agents")
async def list_agents(request: Request):
    """获取所有可用的 Agent 和 Workflow"""
    agents = [
        {
            "id": "xhs_trend_agent",
            "display_name": "小红书趋势追踪",
            "description": "小红书平台爆款趋势追踪与分析",
            "platform": "xiaohongshu",
            "icon": "fas fa-chart-line",
            "tags": ["Trend", "Analysis"],
            "params": {
                "keywords": {
                    "type": "list[str]",
                    "required": True,
                    "description": "分析关键词列表",
                    "placeholder": "每行一个关键词\n杭州旅游\nPython教程\nAI工具"
                }
            }
        },
        {
            "id": "xhs_creator_sniper",
            "display_name": "小红书创作者监控",
            "description": "监控小红书指定创作者的最新内容动态",
            "platform": "xiaohongshu",
            "icon": "fas fa-user-astronaut",
            "tags": ["Monitor", "Creator"],
            "params": {
                "creator_ids": {
                    "type": "list[str]",
                    "required": True,
                    "description": "创作者ID列表",
                    "placeholder": "每行一个创作者ID\n5c4c5848000000001200de55\n657f31eb000000003d036737"
                },
                "days": {
                    "type": "int",
                    "required": False,
                    "description": "监控天数",
                    "default": 7,
                    "min": 1,
                    "max": 30
                }
            }
        },
        {
            "id": "douyin_trend_agent",
            "display_name": "抖音趋势追踪",
            "description": "抖音平台爆款趋势追踪与分析",
            "platform": "douyin",
            "icon": "fas fa-chart-line",
            "tags": ["Trend", "Analysis"],
            "params": {
                "keywords": {
                    "type": "list[str]",
                    "required": True,
                    "description": "分析关键词列表",
                    "placeholder": "每行一个关键词\nagent interview\nPython tutorial\nAI tools"
                }
            }
        },
        {
            "id": "douyin_creator_sniper",
            "display_name": "抖音创作者监控",
            "description": "监控抖音指定创作者的最新内容动态",
            "platform": "douyin",
            "icon": "fas fa-user-astronaut",
            "tags": ["Monitor", "Creator"],
            "params": {
                "creator_ids": {
                    "type": "list[str]",
                    "required": True,
                    "description": "创作者ID列表",
                    "placeholder": "每行一个创作者ID"
                }
            }
        }
    ]

    return json(BaseResponse(
        code=ErrorCode.SUCCESS,
        message="获取成功",
        data={"agents": agents, "total": len(agents)}
    ).model_dump())