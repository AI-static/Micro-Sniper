# -*- coding: utf-8 -*-
"""Sniper API 路由 - 支持 Agent/Workflow 任务执行"""

from sanic import Blueprint, Request
from sanic.response import json
import asyncio

from api.schema.base import BaseResponse, ErrorCode
from services.task_service import TaskService
from utils.logger import logger

# 导入所有 Agent 类
from services.sniper.agent.xhs_trend import XiaohongshuTrendAgent
from services.sniper.agent.xhs_creator import CreatorSniper
from services.sniper.agent.douyin_trend import DouyinDeepAgent
from services.sniper.agent.wechat_harvest import WechatHarvestAgent
from services.sniper.agent.wechat_analyze import WechatAnalyzeAgent
from config.settings import global_settings

# 导入 Task 模型
from models.task import Task, TaskStatus

sniper_bp = Blueprint("sniper", url_prefix="/sniper")

# Redis Pub/Sub 频道前缀
CANCEL_CHANNEL_PREFIX = "task_cancel:"

# Agent 时间节省配置（与 list_agents 保持一致）
AGENT_TIME_SAVINGS: dict[str, int] = {
    "xhs_trend_agent": 85,
    "xhs_creator_sniper": 25,
    "douyin_trend_agent": 85,
    "douyin_creator_sniper": 25,
    "wechat_harvest_agent": 30,
    "wechat_analyze_agent": 60,
}

# Agent/Workflow 映射表 - 直接存储类对象
AGENT_WORKFLOW_MAPPING = {
    # 小红书 Agent
    "xhs_trend_agent": XiaohongshuTrendAgent,
    "xhs_creator_sniper": CreatorSniper,

    # 抖音 Agent
    "douyin_trend_agent": DouyinDeepAgent,

    # 微信 Agent
    "wechat_harvest_agent": WechatHarvestAgent,
    "wechat_analyze_agent": WechatAnalyzeAgent,

    # 可以继续添加更多 Agent 和 Workflow
    # "custom_workflow": CustomWorkflow,
}


class GlobalCancelManager:
    """全局取消管理器 - 统一管理所有任务的取消

    使用单例模式，全局只有一个 Pub/Sub 订阅
    """

    _instance = None
    _pubsub = None
    _listener_task = None
    _cancel_events: dict[str, asyncio.Event] = {}  # task_id -> Event

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def start_listener(self):
        """启动全局 Pub/Sub 监听器"""
        if self._listener_task is not None:
            logger.warning("[CancelManager] 全局监听器已在运行")
            return

        self._listener_task = asyncio.create_task(self._listen_cancel_messages())
        logger.info("[CancelManager] 全局 Pub/Sub 监听器已启动")

    async def _listen_cancel_messages(self):
        """监听 Redis Pub/Sub 取消消息"""
        from utils.cache import get_redis

        try:
            redis = await get_redis()
            pubsub = redis.pubsub()

            # 订阅所有取消频道（使用模式匹配）
            await pubsub.subscribe(f"{CANCEL_CHANNEL_PREFIX}*")

            logger.info("[CancelManager] 已订阅取消频道: task_cancel:*")

            async for message in pubsub.listen():
                if message["type"] == "message":
                    # 解析频道名，提取 task_id
                    channel = message["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode("utf-8")

                    # 从频道名中提取 task_id: "task_cancel:{task_id}" -> "{task_id}"
                    task_id = channel.replace(CANCEL_CHANNEL_PREFIX, "")
                    logger.info(f"[CancelManager] 收到任务 {task_id} 的取消消息")

                    # 触发对应任务的取消事件
                    if task_id in self._cancel_events:
                        self._cancel_events[task_id].set()
                        logger.info(f"[CancelManager] 任务 {task_id} 取消事件已触发")
                    else:
                        logger.warning(f"[CancelManager] 任务 {task_id} 未注册，忽略取消消息")

        except Exception as e:
            logger.error(f"[CancelManager] 监听器出错: {e}")
        finally:
            if pubsub:
                await pubsub.close()
            logger.info("[CancelManager] 全局 Pub/Sub 监听器已停止")

    def register_task(self, task_id: str) -> asyncio.Event:
        """注册任务并返回取消事件

        Args:
            task_id: 任务 ID

        Returns:
            asyncio.Event: 取消事件
        """
        if task_id not in self._cancel_events:
            self._cancel_events[task_id] = asyncio.Event()
            logger.debug(f"[CancelManager] 任务 {task_id} 已注册")
        return self._cancel_events[task_id]

    def unregister_task(self, task_id: str):
        """注销任务"""
        if task_id in self._cancel_events:
            del self._cancel_events[task_id]
            logger.debug(f"[CancelManager] 任务 {task_id} 已注销")

    async def stop_listener(self):
        """停止全局监听器"""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
            logger.info("[CancelManager] 全局 Pub/Sub 监听器已停止")


# 全局取消管理器实例
cancel_manager = GlobalCancelManager()


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
            task_type=agent_id,
            params=params
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
    """在后台运行 Agent 任务（支持跨进程实时取消）

    使用 Redis Pub/Sub + asyncio.Event 实现实时取消：
    - 后台任务订阅 Redis Pub/Sub 频道
    - 收到取消消息时设置 asyncio.Event
    - 主任务通过 asyncio.wait 等待取消或完成

    状态管理由 ConnectorService 统一负责（__aexit__）

    Args:
        agent_class: Agent 类对象
        request: Sanic Request 对象
        task: 任务对象
        **kwargs: 传递给 Agent 的参数
    """
    from utils.cache import get_redis

    # 创建 Agent 实例
    auth_info = request.ctx.auth_info
    agent = agent_class(
        source_id=auth_info.source_id,
        source=auth_info.source.value,
        playwright=request.app.ctx.playwright,
        task=task
    )

    # 超时配置
    timeout_seconds = global_settings.task.timeout

    # Redis Pub/Sub 频道名
    cancel_channel = f"{CANCEL_CHANNEL_PREFIX}{task.id}"

    # PubSub 连接
    redis = await get_redis()
    pubsub = None

    try:
        # 创建取消事件
        cancel_event = asyncio.Event()

        # 启动 Pub/Sub 监听任务
        async def listen_cancel():
            nonlocal pubsub
            pubsub = redis.pubsub()
            await pubsub.subscribe(cancel_channel)

            async for message in pubsub.listen():
                if message["type"] == "message":
                    logger.info(f"收到任务 {task.id} 的取消消息（Redis Pub/Sub）")
                    cancel_event.set()
                    break

        # 启动监听任务
        listen_task = asyncio.create_task(listen_cancel())

        # 创建一个可以被取消的协程任务（带超时）
        async def execute_with_timeout():
            return await asyncio.wait_for(agent.execute(**kwargs), timeout=timeout_seconds)

        # 启动执行任务
        execute_task = asyncio.create_task(execute_with_timeout())

        # 等待取消信号或任务完成
        done, pending = await asyncio.wait(
            [execute_task, listen_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # 取消未完成的任务
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        # 检查是否被取消
        if cancel_event.is_set():
            logger.info(f"任务 {task.id} 被取消，正在清理资源...")
            logger.info(f"任务 {task.id} 资源清理完成")
            return

        # 检查执行任务的结果（状态由 ConnectorService.__aexit__ 管理）
        if execute_task.done():
            try:
                await execute_task
            except Exception:
                import traceback
                logger.error(f"Agent {agent_class.__name__} 执行失败: {traceback.format_exc()}")

    finally:
        # 无论成功、失败还是取消，都清理资源
        # 1. 清理 Pub/Sub 连接
        if pubsub:
            try:
                await pubsub.unsubscribe(cancel_channel)
                await pubsub.close()
                logger.debug(f"任务 {task.id} 的 Pub/Sub 连接已关闭")
            except Exception as e:
                logger.error(f"关闭 Pub/Sub 连接时出错: {e}")

        # 2. 清理 Agent 资源
        try:
            await agent.cleanup()
        except Exception as e:
            logger.error(f"清理 Agent 资源时出错: {e}")


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


@sniper_bp.post("/task/<task_id:str>/retry")
async def retry_task(request: Request, task_id: str):
    """重试任务"""
    try:
        # 获取原任务（会复用此任务对象）
        task = await Task.get_or_none(id=task_id)
        if not task:
            return json(BaseResponse(
                code=ErrorCode.NOT_FOUND,
                message="任务不存在",
                data=None
            ).model_dump(), status=404)

        # 获取 Agent 类
        agent_id = task.task_type
        if agent_id not in AGENT_WORKFLOW_MAPPING:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"不支持的 Agent/Workflow: {agent_id}",
                data=None
            ).model_dump(), status=400)

        # 重置任务状态（复用原任务对象）
        task.status = TaskStatus.RUNNING
        task.progress = 0
        task.error = None
        task.result = None
        task.started_at = None
        task.completed_at = None
        # logs 保留，作为历史记录参考
        await task.save()

        # 获取原参数
        original_params = task.params or {}

        # 获取 Agent 类
        agent_class = AGENT_WORKFLOW_MAPPING[agent_id]

        # 在后台执行 Agent，复用同一个 task
        asyncio.create_task(_run_agent_task(agent_class, request, task, **original_params))

        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message="任务已重新开始",
            data={
                "task_id": str(task.id),
                "agent_or_workflow": agent_id,
                "message": f"{agent_id} 任务已重新开始执行"
            }
        ).model_dump())
    except Exception as e:
        logger.error(f"重试任务失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            data=None
        ).model_dump(), status=500)


@sniper_bp.post("/task/<task_id:str>/cancel")
async def cancel_task(request: Request, task_id: str):
    """取消任务（支持跨进程实时取消）

    通过 Redis Pub/Sub 发布取消消息：
    - 任务进程订阅了 Redis 频道，会立即收到取消消息
    - 适用于多进程部署环境

    Args:
        request: Sanic Request 对象
        task_id: 任务 ID
    """
    from utils.cache import get_redis

    try:
        # 获取任务
        task = await Task.get_or_none(id=task_id)
        if not task:
            return json(BaseResponse(
                code=ErrorCode.NOT_FOUND,
                message="任务不存在",
                data=None
            ).model_dump(), status=404)

        # 检查任务状态
        if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.WAITING_LOGIN]:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"任务状态为 {task.status}，无法取消",
                data=None
            ).model_dump(), status=400)

        # 通过 Redis Pub/Sub 发布取消消息
        cancel_channel = f"{CANCEL_CHANNEL_PREFIX}{task_id}"
        redis = await get_redis()

        # 发布取消消息（跨进程通知）
        await redis.publish(cancel_channel, "cancel")
        logger.info(f"已向任务 {task_id} 发布取消消息（Redis Pub/Sub）")

        # 标记任务为已取消
        await task.cancel()

        logger.info(f"任务 {task_id} 已被用户取消")

        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message="任务已取消",
            data={
                "task_id": str(task.id),
                "status": TaskStatus.CANCELLED,
                "message": "任务已成功取消"
            }
        ).model_dump())

    except Exception as e:
        logger.error(f"取消任务失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            data=None
        ).model_dump(), status=500)


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
            "display_name": "小红书爆款分析(需要登陆)",
            "description": "小红书平台爆款分析",
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
            "display_name": "小红书创作者监控(需要登陆)",
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
                "latency": {
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
            "display_name": "抖音趋势追踪(需要登陆)",
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
            "display_name": "抖音创作者监控(需要登陆)",
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
        },
        {
            "id": "wechat_harvest_agent",
            "display_name": "微信公众号采集(无需登陆)",
            "description": "采集微信公众号文章的结构化数据（标题、作者、内容、图片等）",
            "platform": "wechat",
            "icon": "fab fa-weixin",
            "tags": ["Harvest", "WeChat"],
            "params": {
                "urls": {
                    "type": "list[str]",
                    "required": True,
                    "description": "文章URL列表",
                    "placeholder": "每行一个微信文章URL\nhttps://mp.weixin.qq.com/s/quwXBvQ_binMZvq43gNfXA\nhttps://mp.weixin.qq.com/s/quwXBvQ_binMZvq43gNfXA"
                }
            }
        },
        {
            "id": "wechat_analyze_agent",
            "display_name": "微信公众号分析(无需登陆)",
            "description": "使用 LLM 深度分析公众号文章内容（核心观点、目标受众、价值评估等）",
            "platform": "wechat",
            "icon": "fas fa-brain",
            "tags": ["Analysis", "WeChat", "LLM"],
            "params": {
                "articles": {
                    "type": "str",
                    "required": True,
                    "description": "文章URL列表或JSON数据",
                    "placeholder": "输入公众号内容"
                },
                "analysis_type": {
                    "type": "str",
                    "required": False,
                    "description": "分析类型",
                    "default": "comprehensive",
                    "options": [
                        {"value": "comprehensive", "label": "全面分析"},
                        {"value": "quick", "label": "快速分析"},
                        {"value": "comparison", "label": "对比分析"},
                        {"value": "trend", "label": "趋势分析"}
                    ]
                }
            }
        }
    ]

    for agent in agents:
        agent["time_savings"] = AGENT_TIME_SAVINGS.get(str(agent.get("id", "")), "0")

    return json(BaseResponse(
        code=ErrorCode.SUCCESS,
        message="获取成功",
        data={"agents": agents, "total": len(agents)}
    ).model_dump())


def format_savings(minutes: int) -> str:
    """格式化时间节省显示

    Args:
        minutes: 分钟数

    Returns:
        格式化后的字符串，如 "2h 30m" 或 "45m"
    """
    if minutes >= 60:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m" if mins > 0 else f"{hours}h"
    return f"{minutes}m"


@sniper_bp.get("/time-savings")
async def get_time_savings(request: Request):
    """获取累计节约时间

    Returns:
        {
            "total_savings_minutes": 360,
            "total_savings_formatted": "6h 0m",
            "task_count": 5,
            "breakdown": {
                "xhs_trend_agent": {"count": 3, "savings": 360},
                "xhs_creator_sniper": {"count": 2, "savings": 120}
            }
        }
    """
    try:
        from models.task import Task, TaskStatus

        auth_info = request.ctx.auth_info
        task_service = TaskService()

        # 获取所有已完成的任务
        completed_tasks = await task_service.list_tasks(
            source=auth_info.source.value,
            source_id=auth_info.source_id,
            status=TaskStatus.COMPLETED,
            limit=1000
        )

        total_savings = 0
        breakdown = {}

        for task in completed_tasks:
            task_type = task.task_type

            # 从配置中获取该 agent 的时间节省值
            time_savings = AGENT_TIME_SAVINGS.get(task_type, 0)
            total_savings += time_savings

            # 按任务类型分组统计
            if task_type not in breakdown:
                breakdown[task_type] = {"count": 0, "savings": 0}
            breakdown[task_type]["count"] += 1
            breakdown[task_type]["savings"] += time_savings

        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message="获取成功",
            data={
                "total_savings_minutes": total_savings,
                "total_savings_formatted": format_savings(total_savings),
                "task_count": len(completed_tasks),
                "breakdown": breakdown
            }
        ).model_dump())

    except Exception as e:
        logger.error(f"获取时间节约失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            data=None
        ).model_dump(), status=500)