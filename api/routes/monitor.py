"""监控相关API路由"""
from sanic import Blueprint
from sanic.response import json
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from services.config_service import ConfigService
from services.monitor_service import monitor_service
from utils.logger import logger

# 创建蓝图
monitor_bp = Blueprint("monitor", url_prefix="/monitor")

# 配置服务
config_service = ConfigService()


class CreateMonitorConfigRequest(BaseModel):
    """创建监控配置请求"""
    name: str = Field(..., description="配置名称")
    platform: str = Field(..., description="平台")
    targets: Dict[str, Any] = Field(..., description="监控目标")
    triggers: List[Dict[str, Any]] = Field(default_factory=list, description="触发条件")
    check_interval: int = Field(default=300, description="检查间隔（秒）")
    webhook_url: Optional[str] = Field(None, description="报警回调URL")


class UpdateMonitorConfigRequest(BaseModel):
    """更新监控配置请求"""
    name: Optional[str] = Field(None, description="配置名称")
    targets: Optional[Dict[str, Any]] = Field(None, description="监控目标")
    triggers: Optional[List[Dict[str, Any]]] = Field(None, description="触发条件")
    check_interval: Optional[int] = Field(None, description="检查间隔（秒）")
    webhook_url: Optional[str] = Field(None, description="报警回调URL")
    is_active: Optional[bool] = Field(None, description="是否启用")


@monitor_bp.post("/configs")
async def create_monitor_config(request):
    """创建监控配置"""
    try:
        # 从认证信息中获取source_id
        source_id = request.ctx.auth_info.source_id
        
        # 解析请求体
        data = request.json
        req_data = CreateMonitorConfigRequest(**data)
        
        # 创建配置
        config = await config_service.create_monitor_config(
            source_id=source_id,
            name=req_data.name,
            platform=req_data.platform,
            targets=req_data.targets,
            triggers=req_data.triggers,
            check_interval=req_data.check_interval,
            webhook_url=req_data.webhook_url
        )
        
        # 如果监控服务已启动，添加监控任务
        if monitor_service.is_running:
            await monitor_service.add_monitor(source_id, str(config.id))
        
        return json({
            "success": True,
            "data": {
                "id": str(config.id),
                "name": config.name,
                "platform": config.platform,
                "is_active": config.is_active,
                "check_interval": config.check_interval,
                "created_at": config.created_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"创建监控配置失败: {e}")
        return json({
            "success": False,
            "error": str(e)
        }, status=400)


@monitor_bp.get("/configs")
async def get_monitor_configs(request):
    """获取监控配置列表"""
    try:
        # 获取认证信息
        auth_info = request.ctx.auth_info
        
        # 获取查询参数
        platform = request.args.get("platform")
        is_active = request.args.get("is_active", "true").lower() == "true"
        
        # 系统用户可以查看所有配置，普通用户只能查看自己的
        if auth_info.source == "system":
            # 系统用户可以指定source_id过滤，不指定则返回所有
            source_id = request.args.get("source_id")
            configs = await config_service.get_monitor_configs(
                source_id=source_id,
                platform=platform,
                is_active=is_active
            )
        else:
            # 普通用户只能查看自己的配置
            configs = await config_service.get_monitor_configs(
                source_id=auth_info.id,
                platform=platform,
                is_active=is_active
            )
        
        # 转换为字典格式
        result = []
        for config in configs:
            result.append({
                "id": str(config.id),
                "name": config.name,
                "platform": config.platform,
                "is_active": config.is_active,
                "targets": config.targets,
                "triggers": config.triggers,
                "check_interval": config.check_interval,
                "webhook_url": config.webhook_url,
                "total_checks": config.total_checks,
                "total_triggers": config.total_triggers,
                "last_check_at": config.last_check_at.isoformat() if config.last_check_at else None,
                "last_trigger_at": config.last_trigger_at.isoformat() if config.last_trigger_at else None,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat()
            })
        
        return json({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取监控配置失败: {e}")
        return json({
            "success": False,
            "error": str(e)
        }, status=400)


@monitor_bp.get("/configs/<config_id:str>")
async def get_monitor_config(request, config_id: str):
    """获取单个监控配置"""
    try:
        # 获取认证信息
        auth_info = request.ctx.auth_info
        
        # 系统用户可以查看任何配置，普通用户只能查看自己的
        if auth_info.source == "system":
            # 系统用户可以查看任何配置
            config = await config_service.get_monitor_config(config_id, None)
        else:
            # 普通用户只能查看自己的配置
            config = await config_service.get_monitor_config(config_id, auth_info.id)
        
        if not config:
            return json({
                "success": False,
                "error": "配置不存在"
            }, status=404)
        
        return json({
            "success": True,
            "data": {
                "id": str(config.id),
                "name": config.name,
                "platform": config.platform,
                "is_active": config.is_active,
                "targets": config.targets,
                "triggers": config.triggers,
                "check_interval": config.check_interval,
                "webhook_url": config.webhook_url,
                "total_checks": config.total_checks,
                "total_triggers": config.total_triggers,
                "last_check_at": config.last_check_at.isoformat() if config.last_check_at else None,
                "last_trigger_at": config.last_trigger_at.isoformat() if config.last_trigger_at else None,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"获取监控配置失败: {e}")
        return json({
            "success": False,
            "error": str(e)
        }, status=400)


@monitor_bp.put("/configs/<config_id:str>")
async def update_monitor_config(request, config_id: str):
    """更新监控配置"""
    try:
        # 获取认证信息
        auth_info = request.ctx.auth_info
        
        # 解析请求体
        data = request.json
        req_data = UpdateMonitorConfigRequest(**data)
        
        # 更新配置
        update_data = {}
        for field, value in req_data.model_dump(exclude_unset=True).items():
            update_data[field] = value
        
        # 系统用户可以更新任何配置，普通用户只能更新自己的
        if auth_info.source == "system":
            config = await config_service.get_monitor_config(config_id, None)
        else:
            config = await config_service.get_monitor_config(config_id, auth_info.id)
        
        if not config:
            return json({
                "success": False,
                "error": "配置不存在"
            }, status=404)
        
        # 更新字段
        for key, value in update_data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        await config.save()
        logger.info(f"更新监控配置成功: {config_id}")
        
        # 重新加载监控任务
        if monitor_service.is_running:
            await monitor_service.reload_monitor(config.source_id, config_id)
        
        return json({
            "success": True,
            "data": {
                "id": str(config.id),
                "updated_at": config.updated_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"更新监控配置失败: {e}")
        return json({
            "success": False,
            "error": str(e)
        }, status=400)


@monitor_bp.delete("/configs/<config_id:str>")
async def delete_monitor_config(request, config_id: str):
    """删除监控配置"""
    try:
        # 获取认证信息
        auth_info = request.ctx.auth_info
        
        # 系统用户可以删除任何配置，普通用户只能删除自己的
        if auth_info.source == "system":
            config = await config_service.get_monitor_config(config_id, None)
        else:
            config = await config_service.get_monitor_config(config_id, auth_info.id)
        
        if not config:
            return json({
                "success": False,
                "error": "配置不存在"
            }, status=404)
        
        # 软删除
        config.is_active = False
        await config.save()
        logger.info(f"删除监控配置成功: {config_id}")
        
        # 停止监控任务
        if monitor_service.is_running:
            await monitor_service.remove_monitor(config.source_id, config_id)
        
        return json({
            "success": True,
            "message": "配置已删除"
        })
        
    except Exception as e:
        logger.error(f"删除监控配置失败: {e}")
        return json({
            "success": False,
            "error": str(e)
        }, status=400)


@monitor_bp.post("/start")
async def start_monitor_service(request):
    """启动监控服务"""
    try:
        await monitor_service.start()
        return json({
            "success": True,
            "message": "监控服务已启动"
        })
    except Exception as e:
        logger.error(f"启动监控服务失败: {e}")
        return json({
            "success": False,
            "error": str(e)
        }, status=500)


@monitor_bp.post("/stop")
async def stop_monitor_service(request):
    """停止监控服务"""
    try:
        await monitor_service.stop()
        return json({
            "success": True,
            "message": "监控服务已停止"
        })
    except Exception as e:
        logger.error(f"停止监控服务失败: {e}")
        return json({
            "success": False,
            "error": str(e)
        }, status=500)


@monitor_bp.get("/status")
async def get_monitor_status(request):
    """获取监控服务状态"""
    try:
        return json({
            "success": True,
            "data": {
                "is_running": monitor_service.is_running,
                "active_tasks": len(monitor_service.running_tasks),
                "tasks": list(monitor_service.running_tasks.keys())
            }
        })
    except Exception as e:
        logger.error(f"获取监控状态失败: {e}")
        return json({
            "success": False,
            "error": str(e)
        }, status=500)