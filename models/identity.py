"""身份验证相关数据模型"""
from tortoise.models import Model
from tortoise.fields import (
    CharField, IntField, BooleanField, DatetimeField, 
    TextField, UUIDField
)
from tortoise.contrib.pydantic import pydantic_model_creator
import uuid


class ApiKey(Model):
    """API密钥模型 - 内部服务身份验证"""
    id = UUIDField(pk=True, default=uuid.uuid4)
    key_id = CharField(100, unique=True, description="密钥ID，格式：resource-uuid")  # 如: image-xxxxx
    api_key = CharField(255, unique=True, description="实际的API密钥")
    name = CharField(200, null=True, description="密钥名称/描述")
    
    # 使用限制
    expires_at = DatetimeField(null=True, description="过期时间")
    usage_limit = IntField(null=True, description="使用次数限制")
    usage_count = IntField(default=0, description="已使用次数")
    
    # 状态
    is_active = BooleanField(default=True, description="是否激活")
    
    # 时间戳
    created_at = DatetimeField(auto_now_add=True)
    updated_at = DatetimeField(auto_now=True)
    
    class Meta:
        table = "api_keys"
        indexes = [
            ("resource_id", "is_active"),
            ("user_id", "is_active"),
            ("key_id",),
        ]


