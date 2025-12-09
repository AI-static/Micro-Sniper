"""身份验证API路由"""
from sanic import Blueprint, Request
from sanic.response import json
from services.identity_service import identity_service
from utils.logger import logger
from api.schema.response import BaseResponse, ErrorCode, ErrorMessage
from api.schema.identity import ApiKeyCreate, ApiKeyInfo, ApiKeyUpdate

from pydantic import ValidationError

# 创建蓝图
identity_bp = Blueprint("identity", url_prefix="/identity")


@identity_bp.post("/api-keys")
async def create_api_key(request: Request):
    """创建API密钥"""
    try:
        key_create = ApiKeyCreate(**request.json)
        logger.info(f"创建API密钥请求: {key_create}")
        
        api_key_info = await identity_service.create_api_key(key_create)

        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message=ErrorMessage.API_KEY_CREATE_SUCCESS,
            data=api_key_info.dict()
        ).model_dump())
            
    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message=ErrorMessage.VALIDATION_ERROR,
            data={"detail": str(e)}
        ).model_dump(), status=400)
    except Exception as e:
        logger.error(f"创建API密钥失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=ErrorMessage.INTERNAL_ERROR,
            data={"error": str(e)}
        ).model_dump(), status=500)


@identity_bp.put("/api-keys/<key_id>")
async def update_api_key(request: Request, key_id: str):
    """更新API密钥"""
    try:
        # 从认证中间件获取用户ID
        if not hasattr(request, "ctx") or not hasattr(request.ctx, "auth_info"):
            return json(BaseResponse(
                code=ErrorCode.UNAUTHORIZED,
                message=ErrorMessage.UNAUTHORIZED,
                data={"error": "未认证"}
            ).model_dump(), status=401)
        
        user_id = request.ctx.auth_info.user_id
        
        # 解析更新数据
        update_data = ApiKeyUpdate(**request.json)
        
        # 转换为字典，过滤掉None值
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        
        # 更新API密钥
        success, error = await identity_service.update_api_key(key_id, user_id, **update_dict)
        
        if not success:
            return json(BaseResponse(
                code=ErrorCode.NOT_FOUND,
                message=ErrorMessage.NOT_FOUND,
                data={"error": error or "API密钥不存在"}
            ).model_dump(), status=404)
        
        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message=ErrorMessage.API_KEY_UPDATE_SUCCESS,
            data={"success": True}
        ).model_dump())
        
    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message=ErrorMessage.VALIDATION_ERROR,
            data={"detail": str(e)}
        ).model_dump(), status=400)
    except Exception as e:
        logger.error(f"更新API密钥失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=ErrorMessage.INTERNAL_ERROR,
            data={"error": str(e)}
        ).model_dump(), status=500)


@identity_bp.delete("/api-keys/<key_id>")
async def revoke_api_key(request: Request, key_id: str):
    """撤销API密钥"""
    try:
        # 从认证中间件获取用户ID
        if not hasattr(request, "ctx") or not hasattr(request.ctx, "auth_info"):
            return json(BaseResponse(
                code=ErrorCode.UNAUTHORIZED,
                message=ErrorMessage.UNAUTHORIZED,
                data={"error": "未认证"}
            ).model_dump(), status=401)
        
        user_id = request.ctx.auth_info.user_id
        
        # 撤销API密钥
        success, error = await identity_service.revoke_api_key(key_id, user_id)
        
        if not success:
            return json(BaseResponse(
                code=ErrorCode.NOT_FOUND,
                message=ErrorMessage.NOT_FOUND,
                data={"error": error or "API密钥不存在"}
            ).model_dump(), status=404)
        
        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message=ErrorMessage.API_KEY_REVOKE_SUCCESS,
            data={"success": True}
        ).model_dump())
        
    except Exception as e:
        logger.error(f"撤销API密钥失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=ErrorMessage.INTERNAL_ERROR,
            data={"error": str(e)}
        ).model_dump(), status=500)
