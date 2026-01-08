"""API基础响应模型"""
from pydantic import BaseModel
from typing import Any, Optional


class BaseResponse(BaseModel):
    """基础响应"""
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


class PageResponse(BaseModel):
    """分页响应"""
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int


class SuccessResponse(BaseResponse):
    """成功响应"""

    def __init__(self, data: Any = None, message: str = "success"):
        super().__init__(code=0, message=message, data=data)


class ErrorResponse(BaseResponse):
    """错误响应"""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(code=code, message=message, data=data)


# 错误码定义
class ErrorCode:
    """错误码常量"""
    # 成功
    SUCCESS = 0

    # 客户端错误 (400-499)
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    VALIDATION_ERROR = 422

    # 服务器错误 (500-599)
    INTERNAL_ERROR = 500
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504

    # 业务错误 (600+)
    CREATE_FAILED = 600
    IMAGE_GENERATE_FAILED = 601
    IMAGE_EDIT_FAILED = 602
    IMAGE_UPLOAD_FAILED = 603
    NOT_LOGGED_IN = 604  # 平台未登录


# 错误消息定义
class ErrorMessage:
    """错误消息常量"""
    # 通用消息
    SUCCESS = "success"
    BAD_REQUEST = "参数错误"
    UNAUTHORIZED = "未授权"
    FORBIDDEN = "禁止访问"
    NOT_FOUND = "资源不存在"
    INTERNAL_ERROR = "服务器错误"
    SERVICE_UNAVAILABLE = "服务不可用"
    VALIDATION_ERROR = "参数验证失败"

    # 业务相关消息
    # 图片服务
    IMAGE_GENERATE_SUCCESS = "图片生成成功"
    IMAGE_GENERATE_FAILED = "图片生成失败"
    IMAGE_EDIT_SUCCESS = "图片编辑成功"
    IMAGE_EDIT_FAILED = "图片编辑失败"
    IMAGE_UPLOAD_SUCCESS = "图片上传成功"
    IMAGE_UPLOAD_FAILED = "图片上传失败"
    BATCH_PROCESS_COMPLETE = "批量处理完成"
    PLEASE_SELECT_IMAGE = "请选择要上传的图片"
    PROVIDE_IMAGE_URL = "请提供图片URL"

    # 身份验证服务
    API_KEY_CREATE_SUCCESS = "API密钥创建成功"
    API_KEY_CREATE_FAILED = "API密钥创建失败"
    API_KEY_UPDATE_SUCCESS = "API密钥更新成功"
    API_KEY_REVOKE_SUCCESS = "API密钥撤销成功"
    AUTH_SUCCESS = "认证成功"

    # 配置服务
    CONFIG_TYPE_CREATED = "配置类型创建成功"
    CONFIG_CREATED = "配置创建成功"
    CONFIG_UPDATED = "配置更新成功"
    CONFIG_DELETED = "删除成功"