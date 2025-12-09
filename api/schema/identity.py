from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# 自定义 Pydantic 模型用于API请求/响应
class ApiKeyCreate(BaseModel):
    """创建API密钥请求"""
    name: Optional[str] = Field(None, description="密钥名称")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    usage_limit: Optional[int] = Field(None, description="使用次数限制")


class ApiKeyResponse(BaseModel):
    """API密钥响应"""
    id: str
    key_id: str
    resource_id: str
    api_key: str  # 只在创建时返回完整密钥
    user_id: str
    name: Optional[str]
    expires_at: Optional[datetime]
    usage_limit: Optional[int]
    usage_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApiKeyInfo(BaseModel):
    """API密钥信息（不包含完整密钥）"""
    id: str
    key_id: str
    resource_id: str
    user_id: str
    name: Optional[str]
    expires_at: Optional[datetime]
    usage_limit: Optional[int]
    usage_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApiKeyUpdate(BaseModel):
    """更新API密钥请求"""
    name: Optional[str] = None
    expires_at: Optional[datetime] = None
    usage_limit: Optional[int] = None
    is_active: Optional[bool] = None
