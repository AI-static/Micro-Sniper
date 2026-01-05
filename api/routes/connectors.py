# -*- coding: utf-8 -*-
"""连接器API路由"""
from pickle import FALSE

from sanic import Blueprint, Request
from sanic.response import json, ResponseStream
import ujson as json_lib
import asyncio
from services.sniper.connectors import ConnectorService
from utils.logger import logger
from utils.exceptions import BusinessException, RateLimitException, LockConflictException, ContextNotFoundException
from api.schema.base import BaseResponse, ErrorCode, ErrorMessage
from api.schema.connectors import ExtractRequest, HarvestRequest, PublishRequest, LoginRequest, SearchRequest
from pydantic import BaseModel, Field, ValidationError
from models.connectors import PlatformType, LoginMethod
from models.task import Task

# 创建蓝图
connectors_bp = Blueprint("connectors", url_prefix="/connectors")



# ==================== 路由处理 ====================

@connectors_bp.post("/extract-summary")
async def extract_summary(request: Request):
    """提取URL内容摘要 - SSE 流式输出"""

    async def stream_response(response):
        try:
            data = ExtractRequest.model_validate(request.json)
        except ValidationError as e:
            # 参数验证失败，发送错误事件
            await response.write(f"data: {json_lib.dumps({'type': 'error', 'message': f'参数验证失败: {str(e)}', 'data': {'error_type': 'validation_error'}}, ensure_ascii=False)}\n\n")
            return
        except Exception as e:
            # 其他错误
            await response.write(f"data: {json_lib.dumps({'type': 'error', 'message': f'请求数据格式错误: {str(e)}', 'data': {'error_type': 'request_error'}}, ensure_ascii=False)}\n\n")
            return
        
        # 获取认证上下文
        auth_info = request.ctx.auth_info
        connector_service = ConnectorService(request.app.ctx.playwright, auth_info.source.value, auth_info.source_id)
        # 流式获取结果并发送SSE事件
        async for event in connector_service.extract_summary_stream(
            urls=data.urls,
            platform=data.platform,
            concurrency=data.concurrency
        ):
            await response.write(f"data: {json_lib.dumps(event, ensure_ascii=False)}\n\n")

    return ResponseStream(
        stream_response,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@connectors_bp.post("/harvest")
async def harvest_content(request: Request):
    """采收用户内容"""
    try:
        data = HarvestRequest(**request.json)
        logger.info(f"收到采收请求: platform={data.platform}, user_id={data.creator_ids}, limit={data.limit}")

        # 获取认证上下文
        auth_info = request.ctx.auth_info

        # 创建并启动任务
        task = await Task.create(
            source=auth_info.source.value,
            source_id=auth_info.source_id,
            task_type="harvest_content"
        )
        await task.start()

        async with ConnectorService(request.app.ctx.playwright, auth_info.source.value, auth_info.source_id, task=task) as connector_service:
            results = await connector_service.harvest_user_content(
                platform=data.platform,
                creator_ids=data.creator_ids,
                limit=data.limit
            )

            # 重组结果：按 creator_id 分组
            results_by_creator = {}
            successful_creators = 0
            failed_creators = 0
            total_notes = 0

            for result in results:
                creator_id = result.get("creator_id")
                if creator_id:
                    if result.get("success"):
                        notes = result.get("data", [])
                        results_by_creator[creator_id] = {
                            "success": True,
                            "note_count": len(notes),
                            "notes": notes
                        }
                        successful_creators += 1
                        total_notes += len(notes)
                    else:
                        results_by_creator[creator_id] = {
                            "success": False,
                            "error": result.get("error"),
                            "note_count": 0,
                            "notes": []
                        }
                        failed_creators += 1

            # 完成任务
            await task.complete({
                "total_creators": len(data.creator_ids),
                "successful_creators": successful_creators,
                "total_notes": total_notes
            })

            return json(BaseResponse(
                code=ErrorCode.SUCCESS,
                message=f"采收完成：{successful_creators}/{len(data.creator_ids)} 个创作者成功，共 {total_notes} 条笔记",
                data={
                    "task_id": str(task.id),
                    "total_creators": len(data.creator_ids),
                    "successful_creators": successful_creators,
                    "failed_creators": failed_creators,
                    "total_notes": total_notes,
                    "results": results_by_creator
                }
            ).model_dump())

    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message=ErrorMessage.VALIDATION_ERROR,
            data={"detail": str(e)}
        ).model_dump(), status=400)
    except ValueError as e:
        logger.error(f"参数错误: {e}")
        return json(BaseResponse(
            code=ErrorCode.BAD_REQUEST,
            message=str(e),
            data={"error": str(e)}
        ).model_dump(), status=400)
    except Exception as e:
        logger.error(f"采收内容失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=ErrorMessage.INTERNAL_ERROR,
            data={"error": str(e)}
        ).model_dump(), status=500)


@connectors_bp.post("/publish")
async def publish_content(request: Request):
    """发布内容到平台"""
    try:
        data = PublishRequest(**request.json)
        logger.info(f"收到发布请求: platform={data.platform}, type={data.content_type}")

        # 获取认证上下文
        auth_info = request.ctx.auth_info

        # 创建并启动任务
        task = await Task.create(
            source=auth_info.source.value,
            source_id=auth_info.source_id,
            task_type="publish_content"
        )
        await task.start()

        async with ConnectorService(request.app.ctx.playwright, auth_info.source.value, auth_info.source_id, task=task) as connector_service:
            result = await connector_service.publish_content(
                platform=data.platform,
                content=data.content,
                content_type=data.content_type,
                images=data.images or [],
                tags=data.tags or []
            )

            # 完成任务
            await task.complete({"success": result.get("success", False)})

            return json(BaseResponse(
                code=ErrorCode.SUCCESS if result.get("success") else ErrorCode.INTERNAL_ERROR,
                message="发布成功" if result.get("success") else "发布失败",
                data={
                    "task_id": str(task.id),
                    **result
                }
            ).model_dump())

    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message=ErrorMessage.VALIDATION_ERROR,
            data={"detail": str(e)}
        ).model_dump(), status=400)
    except ValueError as e:
        logger.error(f"参数错误: {e}")
        return json(BaseResponse(
            code=ErrorCode.BAD_REQUEST,
            message=str(e),
            data={"error": str(e)}
        ).model_dump(), status=400)
    except Exception as e:
        logger.error(f"发布内容失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=ErrorMessage.INTERNAL_ERROR,
            data={"error": str(e)}
        ).model_dump(), status=500)


@connectors_bp.post("/login")
async def login(request: Request):
    """登录平台"""
    try:
        data = LoginRequest(**request.json)
        logger.info(f"收到登录请求: platform={data.platform}, method={data.method}")

        # 获取认证上下文
        auth_info = request.ctx.auth_info

        # 创建并启动任务
        task = await Task.create(
            source=auth_info.source.value,
            source_id=auth_info.source_id,
            task_type="login"
        )
        await task.start()

        async with ConnectorService(request.app.ctx.playwright, auth_info.source.value, auth_info.source_id, task=task) as connector_service:
            logger.info(f"[Auth] 从认证上下文获取: 鉴权数据AuthInfo: {auth_info.source}")

            # 调用 connector_service 的 login 方法
            result = await connector_service.login(
                platform=data.platform,
                method=data.method,
                cookies=data.cookies or {}
            )

            # 完成任务
            await task.complete({"success": bool(result)})

            # 根据登录方法处理不同返回格式
            if data.method == LoginMethod.QRCODE:
                # 二维码登录返回字典，包含 qrcode, context_id, is_logged_in 等
                return json(BaseResponse(
                    code=ErrorCode.SUCCESS if result.get("success") else ErrorCode.INTERNAL_ERROR,
                    message=result.get("message", "登录请求处理完成"),
                    data={
                        "task_id": str(task.id),
                        **result,  # 包含 qrcode, context_id, is_logged_in, timeout 等
                        "source": auth_info.source,
                        "source_id": auth_info.source_id
                    }
                ).model_dump())
            else:
                # Cookie 登录返回 context_id 字符串
                return json(BaseResponse(
                    code=ErrorCode.SUCCESS if result else ErrorCode.INTERNAL_ERROR,
                    message="登录成功" if result else "登录失败",
                    data={
                        "task_id": str(task.id),
                        "context_id": result,
                        "source": auth_info.source,
                        "source_id": auth_info.source_id
                    }
                ).model_dump())

    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message=ErrorMessage.VALIDATION_ERROR,
            data={"detail": str(e)}
        ).model_dump(), status=400)
    except ValueError as e:
        logger.error(f"参数错误: {e}")
        return json(BaseResponse(
            code=ErrorCode.BAD_REQUEST,
            message=str(e),
            data={"error": str(e)}
        ).model_dump(), status=400)
    except Exception as e:
        logger.error(f"登录失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=ErrorMessage.INTERNAL_ERROR,
            data={"error": str(e)}
        ).model_dump(), status=500)


@connectors_bp.post("/login/<platform:str>/confirm")
async def confirm_login(request: Request, platform: str):
    """用户确认已完成登录 - 保存 context

    用户在云浏览器中完成登录后，点击"我已完成登录"按钮调用此接口：
    1. 从 connector._login_tasks 获取 session 和 browser
    2. 调用 _cleanup_resources 清理资源
    3. 调用 agent_bay.delete(session, sync_context=True) 落盘保存
    """
    try:
        data = request.json or {}
        context_id = data.get("context_id")

        if not context_id:
            return json(BaseResponse(
                code=ErrorCode.BAD_REQUEST,
                message="context_id is required",
                data=None
            ).model_dump(), status=400)

        auth_info = request.ctx.auth_info

        # 获取 connector
        from models.connectors import PlatformType
        from services.sniper.connectors.xiaohongshu import XiaohongshuConnector
        from services.sniper.connectors.douyin import DouyinConnector

        try:
            platform_type = PlatformType(platform)
        except ValueError:
            return json(BaseResponse(
                code=ErrorCode.BAD_REQUEST,
                message=f"Unsupported platform: {platform}",
                data=None
            ).model_dump(), status=400)

        # 创建 connector 实例
        if platform_type == PlatformType.XIAOHONGSHU:
            connector = XiaohongshuConnector(playwright=request.app.ctx.playwright)
        elif platform_type == PlatformType.DOUYIN:
            connector = DouyinConnector(playwright=request.app.ctx.playwright)
        else:
            return json(BaseResponse(
                code=ErrorCode.BAD_REQUEST,
                message=f"Platform {platform} not supported yet",
                data=None
            ).model_dump(), status=400)

        # 从 _login_tasks 获取 session 和 browser
        if context_id not in connector._login_tasks:
            return json(BaseResponse(
                code=ErrorCode.NOT_FOUND,
                message=f"Login task not found for context: {context_id}",
                data=None
            ).model_dump(), status=404)

        login_task = connector._login_tasks[context_id]
        session = login_task.get("session")
        browser = login_task.get("browser")

        if not session:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message="Session not found in login task",
                data=None
            ).model_dump(), status=500)

        # 清理资源并保存 context
        logger.info(f"[Auth] User confirmed login for {platform}, saving context: {context_id}")

        try:
            # 调用 connector 的 _cleanup_resources 方法
            await connector._cleanup_resources(session, browser)

            # 保存 context（sync_context=True 落盘）
            await connector.agent_bay.delete(session, sync_context=True)

            logger.info(f"[Auth] Context saved successfully: {context_id}")

        except Exception as e:
            logger.error(f"[Auth] Error saving context: {e}")
            # 即使出错也继续，因为 context 可能已经保存

        # 清理 _login_tasks
        del connector._login_tasks[context_id]

        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message="Login context saved successfully",
            data={
                "context_id": context_id,
                "platform": platform,
                "source": auth_info.source.value,
                "source_id": auth_info.source_id
            }
        ).model_dump())

    except Exception as e:
        logger.error(f"确认登录失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            data={"error": str(e)}
        ).model_dump(), status=500)


@connectors_bp.get("/platforms")
async def list_platforms(request: Request):
    """获取支持的平台列表 - 展示多平台连接能力"""
    platforms = [
        {
            "name": PlatformType.XIAOHONGSHU.value,
            "display_name": "小红书",
            "icon": "📕",
            "category": "社交内容",
            "features": {
                "extract": {
                    "enabled": True,
                    "description": "AI 驱动的内容摘要提取",
                    "modes": ["stream", "batch"]
                },
                "get_note_detail": {
                    "enabled": True,
                    "description": "快速获取笔记详情（CDP 直连）",
                    "performance": "~2-5秒/篇"
                },
                "harvest": {
                    "enabled": True,
                    "description": "批量采收用户主页内容",
                    "max_limit": 100
                },
                "search": {
                    "enabled": True,
                    "description": "关键词搜索并提取"
                },
                "publish": {
                    "enabled": True,
                    "description": "发布内容到平台",
                    "supported_types": ["text", "image", "video"]
                },
                "login": {
                    "enabled": True,
                    "methods": ["cookie", "qrcode"],
                    "description": "支持 Cookie 和二维码登录"
                }
            },
            "rate_limits": {
                "get_note_detail": "10次/60秒",
                "harvest": "5次/60秒",
                "search": "10次/60秒",
                "publish": "2次/60秒"
            },
            "domain_patterns": ["xiaohongshu.com", "xhslink.com"]
        },
        {
            "name": PlatformType.WECHAT.value,
            "display_name": "微信公众号",
            "icon": "💬",
            "category": "内容平台",
            "features": {
                "extract": {
                    "enabled": True,
                    "description": "AI 驱动的文章摘要提取",
                    "modes": ["stream", "batch"]
                },
                "get_note_detail": {
                    "enabled": True,
                    "description": "快速获取文章详情（CDP 直连）",
                    "performance": "~2-5秒/篇"
                },
                "harvest": {
                    "enabled": True,
                    "description": "批量采收公众号文章",
                    "max_limit": 100
                },
                "search": {
                    "enabled": False,
                    "description": "暂不支持"
                },
                "publish": {
                    "enabled": False,
                    "description": "暂不支持"
                },
                "login": {
                    "enabled": False,
                    "description": "无需登录（公开文章）"
                }
            },
            "rate_limits": {
                "get_note_detail": "10次/60秒",
                "harvest": "5次/60秒"
            },
            "domain_patterns": ["mp.weixin.qq.com"]
        },
        {
            "name": PlatformType.GENERIC.value,
            "display_name": "通用网站",
            "icon": "🌐",
            "category": "通用工具",
            "features": {
                "extract": {
                    "enabled": True,
                    "description": "AI 驱动的通用内容提取",
                    "modes": ["stream", "batch"]
                },
                "get_note_detail": {
                    "enabled": False,
                    "description": "暂不支持"
                },
                "harvest": {
                    "enabled": False,
                    "description": "暂不支持"
                },
                "search": {
                    "enabled": False,
                    "description": "暂不支持"
                },
                "publish": {
                    "enabled": False,
                    "description": "暂不支持"
                },
                "login": {
                    "enabled": False,
                    "description": "暂不支持"
                }
            },
            "rate_limits": {
                "extract": "10次/60秒"
            },
            "domain_patterns": ["*"]
        }
    ]

    return json(BaseResponse(
        code=ErrorCode.SUCCESS,
        message="获取平台列表成功",
        data={
            "platforms": platforms,
            "total": len(platforms),
            "summary": {
                "supported_platforms": len(platforms),
                "content_extraction": sum(1 for p in platforms if p["features"]["extract"]["enabled"]),
                "detail_fetching": sum(1 for p in platforms if p["features"]["get_note_detail"]["enabled"]),
                "harvest": sum(1 for p in platforms if p["features"]["harvest"]["enabled"]),
                "publish": sum(1 for p in platforms if p["features"]["publish"]["enabled"]),
                "search": sum(1 for p in platforms if p["features"]["search"]["enabled"])
            }
        }
    ).model_dump())


@connectors_bp.post("/get-note-detail")
async def get_note_detail(request: Request):
    """获取笔记/文章详情（快速提取，不使用Agent）

    适合场景：
    - 批量获取文章内容和图片
    - 快速抓取文章基本信息
    - 不需要深度AI分析的场景

    性能特点：
    - 速度快，通常2-5秒完成单篇文章
    - 资源消耗少
    - 直接提取，不依赖AI
    """
    try:
        data = ExtractRequest(**request.json)
        logger.info(f"收到快速提取请求: {len(data.urls)} 个URL, platform={data.platform}")

        # 获取认证上下文
        auth_info = request.ctx.auth_info

        # 创建并启动任务
        task = await Task.create(
            source=auth_info.source.value,
            source_id=auth_info.source_id,
            task_type="get_note_detail"
        )
        await task.start()

        async with ConnectorService(request.app.ctx.playwright, auth_info.source.value, auth_info.source_id, task=task) as connector_service:
            # 获取笔记详情
            results = await connector_service.get_note_details(
                urls=data.urls,
                platform=data.platform
            )

            # 统计结果
            success_count = sum(1 for r in results if r.get("success"))

            # 完成任务
            await task.complete({
                "total": len(results),
                "success_count": success_count
            })

            return json(BaseResponse(
                code=ErrorCode.SUCCESS,
                message=f"快速提取完成：{success_count}/{len(results)} 成功",
                data={
                    "task_id": str(task.id),
                    "results": results,
                    "summary": {
                        "total": len(results),
                        "success_count": success_count,
                        "failed_count": len(results) - success_count,
                        "method": "fast_extraction"
                    }
                }
            ).model_dump())

    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message=ErrorMessage.VALIDATION_ERROR,
            data={"detail": str(e)}
        ).model_dump(), status=400)
    except ValueError as e:
        logger.error(f"参数错误: {e}")
        return json(BaseResponse(
            code=ErrorCode.BAD_REQUEST,
            message=str(e),
            data={"error": str(e)}
        ).model_dump(), status=400)
    except Exception as e:
        logger.error(f"获取笔记详情失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=ErrorMessage.INTERNAL_ERROR,
            data={"error": str(e)}
        ).model_dump(), status=500)


@connectors_bp.post("/search-and-extract")
async def search_and_extract(request: Request):
    """搜索并提取内容"""
    try:
        data = SearchRequest.model_validate(request.json)
        logger.info(f"搜索并提取内容: platform={data.platform}, keywords={data.keywords}")

        # 获取认证上下文
        auth_info = request.ctx.auth_info

        # 创建并启动任务
        task = await Task.create(
            source=auth_info.source.value,
            source_id=auth_info.source_id,
            task_type="search_and_extract"
        )
        await task.start()

        async with ConnectorService(request.app.ctx.playwright, auth_info.source.value, auth_info.source_id, task=task) as connector_service:
            results = await connector_service.search_and_extract(
                platform=data.platform,
                keywords=data.keywords,
                limit=data.limit
            )

            # 重组结果：按 keyword 分组
            results_by_keyword = {}
            successful_keywords = 0
            failed_keywords = 0
            total_results = 0

            for result in results:
                keyword = result.get("keyword")
                if keyword:
                    if result.get("success"):
                        items = result.get("data", [])
                        results_by_keyword[keyword] = {
                            "success": True,
                            "result_count": len(items),
                            "results": items
                        }
                        successful_keywords += 1
                        total_results += len(items)
                    else:
                        results_by_keyword[keyword] = {
                            "success": False,
                            "error": result.get("error"),
                            "result_count": 0,
                            "results": []
                        }
                        failed_keywords += 1

            # 完成任务
            await task.complete({
                "total_keywords": len(data.keywords),
                "successful_keywords": successful_keywords,
                "total_results": total_results
            })

            return json(BaseResponse(
                code=ErrorCode.SUCCESS,
                message=f"搜索完成：{successful_keywords}/{len(data.keywords)} 个关键词成功，共 {total_results} 条结果",
                data={
                    "task_id": str(task.id),
                    "total_keywords": len(data.keywords),
                    "successful_keywords": successful_keywords,
                    "failed_keywords": failed_keywords,
                    "total_results": total_results,
                    "results": results_by_keyword
                }
            ).model_dump())

    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message=ErrorMessage.VALIDATION_ERROR,
            data={"detail": str(e)}
        ).model_dump(), status=400)
    except ValueError as e:
        logger.error(f"参数错误: {e}")
        return json(BaseResponse(
            code=ErrorCode.BAD_REQUEST,
            message=str(e),
            data={"error": str(e)}
        ).model_dump(), status=400)
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=ErrorMessage.INTERNAL_ERROR,
            data={"error": str(e)}
        ).model_dump(), status=500)
