"""图片生成路由"""
from sanic import Blueprint, Request
from sanic.response import json, HTTPResponse
from sanic_ext import openapi
from services.image_service import ImageService
from utils.logger import logger
from api.schema.image import CreateImageRequest, EditImageRequest, BatchCreateRequest
from api.schema.response import BaseResponse, ErrorCode, ErrorMessage

from pydantic import ValidationError

# 创建蓝图
bp = Blueprint("image", url_prefix="/image")

# 创建服务实例
image_service = ImageService()


@bp.post("/generate")
async def generate_image(request: Request):
    """生成图片"""
    try:
        data = CreateImageRequest(**request.json)
        logger.info(f"收到图片生成请求: {data.prompt[:50]}")
        
        result = await image_service.create_image(
            prompt=data.prompt,
            model=data.model,
            n=data.n,
            size=data.size
        )
        
        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message=ErrorMessage.IMAGE_GENERATE_SUCCESS if result["success"] else ErrorMessage.IMAGE_GENERATE_FAILED,
            data=result
        ).model_dump())
            
    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message=ErrorMessage.VALIDATION_ERROR,
            data={"detail": str(e)}
        ).model_dump(), status=400)
    except Exception as e:
        logger.error(f"生成图片失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=ErrorMessage.INTERNAL_ERROR
        ).model_dump(), status=500)


@bp.post("/edit")
async def edit_image(request: Request):
    """编辑图片"""
    try:
        # 检查是否有上传的图片文件
        if not request.files or not request.files.getlist('image'):
            return json(BaseResponse(
                code=ErrorCode.BAD_REQUEST,
                message=ErrorMessage.PLEASE_SELECT_IMAGE
            ).model_dump(), status=400)
        
        # 获取上传的图片文件
        files = request.files.getlist('image')

        # 使用EditImageRequest验证参数
        data = EditImageRequest(
            prompt=request.form.get('prompt'),
            model=request.form.get('model'),
            n=int(request.form.get('n', 1)),
            size=request.form.get('size')
        )

        result = await image_service.edit_image(
            prompt=data.prompt,
            files=files,  # 直接传递files对象
            model=data.model,
            n=data.n
        )
        
        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message=ErrorMessage.IMAGE_EDIT_SUCCESS if result["success"] else ErrorMessage.IMAGE_EDIT_FAILED,
            data=result
        ).model_dump())
            
    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message=ErrorMessage.VALIDATION_ERROR,
            data={"detail": str(e)}
        ).model_dump(), status=400)
    except (ValueError, IndexError) as e:
        logger.error(f"参数错误: {e}")
        return json(BaseResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message=ErrorMessage.VALIDATION_ERROR,
            data={"detail": "参数格式错误"}
        ).model_dump(), status=400)
    except Exception as e:
        logger.error(f"编辑图片失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=ErrorMessage.INTERNAL_ERROR
        ).model_dump(), status=500)


@bp.post("/batch-generate")
async def batch_generate(request: Request):
    """批量生成图片"""
    try:
        data = BatchCreateRequest(**request.json)
        logger.info(f"收到批量图片生成请求，数量: {len(data.prompts)}")
        
        results = await image_service.batch_create_images(
            prompts=data.prompts,
            model=data.model,
            n=data.n,
            size=data.size
        )
        
        # 统计成功/失败数量
        success_count = sum(1 for r in results if r["success"])
        failed_count = len(results) - success_count
        
        return json(BaseResponse(
            code=ErrorCode.SUCCESS,
            message=ErrorMessage.BATCH_PROCESS_COMPLETE,
            data={
                "total": len(results),
                "success": success_count,
                "failed": failed_count,
                "results": results
            }
        ).model_dump())
        
    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message=ErrorMessage.VALIDATION_ERROR,
            data={"detail": str(e)}
        ).model_dump(), status=400)
    except Exception as e:
        logger.error(f"批量生成图片失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=ErrorMessage.INTERNAL_ERROR
        ).model_dump(), status=500)


@bp.get("/models")
async def list_models(request: Request):
    """获取支持的模型列表"""
    models = [
        {
            "id": "gemini-2.5-flash-image-preview",
            "name": "Gemini 2.5 Flash Image Preview",
            "description": "Nano Banana 1.0 图片生成模型 (¥0.1/张)",
        },
        {
            "id": "gemini-3-pro-image-preview",
            "name": "Gemini 3 Pro Image Preview",
            "description": "Nano Banana 2.0 图片生成模型 (¥0.2/张)",
            "max_n": 10
        }
    ]
    
    return json(BaseResponse(
        code=ErrorCode.SUCCESS,
        message=ErrorMessage.SUCCESS,
        data={
            "models": models
        }
    ).dict())


@bp.post("/upload")
async def upload_image(request: Request):
    """上传图片（图床功能）"""
    try:
        # 检查是否有上传的文件
        if not request.files:
            return json(BaseResponse(
                code=ErrorCode.BAD_REQUEST,
                message=ErrorMessage.PLEASE_SELECT_IMAGE
            ).dict(), status=400)
        
        # 获取上传的文件
        files = request.files.get('image')
        if not files:
            return json(BaseResponse(
                code=ErrorCode.BAD_REQUEST,
                message=ErrorMessage.PLEASE_SELECT_IMAGE
            ).dict(), status=400)
        
        # Sanic的files可能是列表或单个文件
        if isinstance(files, list):
            file = files[0]
        else:
            file = files
        
        filename = file.name
        image_data = file.body
        
        # 调用服务上传
        result = await image_service.upload_image(image_data, filename)
        
        if result["success"]:
            return json(BaseResponse(
                code=ErrorCode.SUCCESS,
                message=ErrorMessage.IMAGE_UPLOAD_SUCCESS,
                data=result
            ).dict())
        else:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message=result.get("error", ErrorMessage.IMAGE_UPLOAD_FAILED),
                data=None
            ).dict(), status=500)
            
    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message=ErrorMessage.VALIDATION_ERROR,
            data={"detail": str(e)}
        ).dict(), status=400)
    except Exception as e:
        logger.error(f"上传图片失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=ErrorMessage.INTERNAL_ERROR
        ).dict(), status=500)


@bp.post("/upload-url")
async def upload_from_url(request: Request):
    """从URL上传图片到图床"""
    try:
        data = request.json
        image_url = data.get("image_url")
        
        if not image_url:
            return json(BaseResponse(
                code=ErrorCode.BAD_REQUEST,
                message=ErrorMessage.PROVIDE_IMAGE_URL
            ).dict(), status=400)
        
        # 调用服务上传
        result = await image_service.upload_from_url(image_url)
        
        if result["success"]:
            return json(BaseResponse(
                code=ErrorCode.SUCCESS,
                message=ErrorMessage.IMAGE_UPLOAD_SUCCESS,
                data=result
            ).dict())
        else:
            return json(BaseResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message=result.get("error", ErrorMessage.IMAGE_UPLOAD_FAILED),
                data=None
            ).dict(), status=500)
            
    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message=ErrorMessage.VALIDATION_ERROR,
            data={"detail": str(e)}
        ).dict(), status=400)
    except Exception as e:
        logger.error(f"从URL上传图片失败: {e}")
        return json(BaseResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=ErrorMessage.INTERNAL_ERROR
        ).dict(), status=500)


@bp.get("/usage")
async def get_usage_info(request: Request):
    """获取使用说明"""
    usage_info = {
        "generate": {
            "endpoint": "/api/v1/image/generate",
            "method": "POST",
            "description": "生成图片",
            "parameters": {
                "prompt": "图片描述（必填）",
                "model": "模型名称（可选）",
                "n": "生成图片数量（可选，默认1）",
                "size": "图片尺寸（可选，默认1024x1024）"
            },
            "example": {
                "prompt": "一只可爱的猫在花园里玩耍",
                "n": 2,
                "size": "1024x1024"
            }
        },
        "edit": {
            "endpoint": "/api/v1/image/edit",
            "method": "POST",
            "content-type": "multipart/form-data",
            "description": "编辑图片",
            "parameters": {
                "image": "图片文件（必填）",
                "prompt": "编辑描述（必填）",
                "model": "模型名称（可选，默认gemini-2.5-flash-image-preview）",
                "n": "生成图片数量（可选，默认1）"
            },
            "example_form": {
                "image": "file",
                "prompt": "给这只猫戴上一顶帽子",
                "model": "gemini-2.5-flash-image-preview",
                "n": 1
            }
        }
    }
    
    return json(BaseResponse(
        code=ErrorCode.SUCCESS,
        message=ErrorMessage.SUCCESS,
        data=usage_info
    ).dict())