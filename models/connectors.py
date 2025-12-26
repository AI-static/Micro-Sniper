"""连接器和身份验证相关数据模型"""
from enum import Enum
from tortoise.models import Model
from tortoise.fields import (
    CharField, IntField, BooleanField, DatetimeField, 
    TextField, UUIDField
)
import uuid
from utils.encryption import encrypt_api_key, decrypt_api_key, verify_api_key, generate_api_key
from utils.logger import logger


class PlatformType(str, Enum):
    """连接器平台类型枚举"""
    XIAOHONGSHU = "xiaohongshu"
    WECHAT = "wechat"
    GENERIC = "generic"


class LoginMethod(str, Enum):
    """登录方法枚举"""
    COOKIE = "cookie"
    QRCODE = "qrcode"

