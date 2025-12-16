# -*- coding: utf-8 -*-
"""连接器API路由"""
from pydantic import BaseModel, Field, ValidationError, field_validator
from typing import List, Optional, Dict, Any, Union
from models.connectors import PlatformType, LoginMethod


# ==================== 请求模型 ====================

class ExtractRequest(BaseModel):
    """提取请求"""
    urls: List[str] = Field(..., description="要提取的URL列表")
    platform: PlatformType = Field(None, description="平台名称（xiaohongshu/wechat/generic），不指定则自动检测")
    concurrency: int = Field(10, description="并发数量，默认10（并行）", ge=1, le=10)
    context_id: Optional[str] = Field(None, description="上下文ID，用于保持登录态")


class HarvestRequest(BaseModel):
    """采收请求"""
    platform: PlatformType = Field(..., description="平台名称（xiaohongshu/wechat）")
    user_id: str = Field(..., description="用户ID或账号标识")
    limit: Optional[int] = Field(50, description="限制数量")
    context_id: Optional[str] = Field(None, description="上下文ID，用于保持登录态")

class SearchRequest(BaseModel):
    """搜索请求"""
    platform: PlatformType = Field(..., description="平台名称（xiaohongshu/wechat）")
    keyword: str = Field(..., description="搜索关键字")
    limit: Optional[int] = Field(50, description="限制数量")
    context_id: Optional[str] = Field(None, description="上下文ID，用于保持登录态")
    extract_details: bool = Field(True, description="是否提取详情（True会访问每个笔记页面获取完整数据，False只返回列表信息）")


class ExtractByCreatorRequest(BaseModel):
    """提取创作者内容请求"""
    platform: PlatformType = Field(..., description="平台名称（xiaohongshu）")
    creator_id: str = Field(..., description="创作者ID")
    limit: Optional[int] = Field(50, description="限制数量")
    extract_details: bool = Field(False, description="是否提取详情（True会访问每个笔记页面，False只返回列表信息）")
    context_id: Optional[str] = Field(None, description="上下文ID，用于保持登录态")


class PublishRequest(BaseModel):
    """发布请求"""
    platform: PlatformType = Field(..., description="平台名称（xiaohongshu）")
    content: str = Field(..., description="内容文本")
    content_type: str = Field("text", description="内容类型（text/image/video）")
    images: Optional[List[str]] = Field(None, description="图片URL列表")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    context_id: Optional[str] = Field(None, description="上下文ID，用于保持登录态")


class LoginRequest(BaseModel):
    """登录请求"""
    platform: PlatformType = Field(..., description="平台名称（xiaohongshu）")
    method: Optional[LoginMethod] = Field(LoginMethod.COOKIE, description="登录方法（目前仅支持 cookie）")
    cookies: Optional[Union[Dict[str, str], str]] = Field(None, description="Cookie 数据（字典或字符串格式）")

    @field_validator('cookies', mode='before')
    @classmethod
    def parse_cookies(cls, v):
        """解析 cookies，支持字符串和字典格式"""
        if v is None:
            return None
        
        if isinstance(v, str):
            # 解析 cookie 字符串为字典
            cookies = {}
            for item in v.split(';'):
                if '=' in item:
                    key, value = item.strip().split('=', 1)
                    cookies[key] = value
            return cookies
        
        return v