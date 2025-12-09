"""身份验证服务"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
import uuid
from tortoise.exceptions import IntegrityError, DoesNotExist
from models.identity import ApiKey
from utils.logger import logger
from utils.exceptions import BusinessException
from api.schema.response import ErrorCode
from api.schema.identity import ApiKeyCreate, ApiKeyInfo


class IdentityService:
    """身份验证服务"""
    
    async def create_api_key(self, key_data: ApiKeyCreate) -> ApiKeyInfo:
        """
        创建API密钥
        
        Returns:
            ApiKeyInfo: API密钥信息
            
        Raises:
            BusinessException: 业务异常
        """
        try:
            # 生成密钥ID和API密钥
            key_id = str(uuid.uuid4())[:8]
            api_key = f"ak-{str(uuid.uuid4()).replace('-', '')}"
            
            # 创建记录
            api_key_obj = await ApiKey.create(
                key_id=key_id,
                api_key=api_key,
                name=key_data.name,
                expires_at=key_data.expires_at,
                usage_limit=key_data.usage_limit
            )
            
            # 转换为响应对象
            result = ApiKeyInfo(
                id=str(api_key_obj.id),
                key_id=api_key_obj.key_id,
                name=api_key_obj.name,
                expires_at=api_key_obj.expires_at,
                usage_limit=api_key_obj.usage_limit,
                usage_count=api_key_obj.usage_count,
                is_active=api_key_obj.is_active,
                created_at=api_key_obj.created_at,
                updated_at=api_key_obj.updated_at
            )
            
            logger.info(f"创建API密钥成功: {key_id} for user {key_data.user_id}")
            return result
            
        except IntegrityError as e:
            logger.error(f"创建API密钥失败，数据冲突: {e}")
            raise BusinessException(
                message="数据冲突，可能是重复的key_id或api_key",
                code=ErrorCode.CREATE_FAILED
            )
        except Exception as e:
            logger.error(f"创建API密钥失败: {e}")
            raise BusinessException(
                message=f"创建失败: {str(e)}",
                code=ErrorCode.INTERNAL_ERROR
            )

    @staticmethod
    async def validate_auth(api_key: str) -> ApiKeyInfo:
        """
        验证API密钥
        
        Args:
            api_key: API密钥
            
        Returns:
            ApiKeyInfo: API密钥信息
            
        Raises:
            ValueError: API密钥相关错误
            Exception: 系统错误
        """
        if not api_key:
            raise ValueError("API密钥不能为空")
        
        if not api_key.startswith("ak-"):
            raise ValueError("API密钥格式错误，应以 'ak-' 开头")
        
        # 查找API密钥
        api_key_obj = await ApiKey.get_or_none(api_key=api_key, is_active=True).prefetch_related()
        
        if not api_key_obj:
            # 检查是否存在但被禁用
            disabled_key = await ApiKey.get_or_none(api_key=api_key, is_active=False)
            if disabled_key:
                raise ValueError(f"API密钥已被禁用: {disabled_key.key_id}")
            raise ValueError("API密钥不存在或已失效")
        
        # 检查过期时间
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.now(timezone.utc):
            raise ValueError(f"API密钥已于 {api_key_obj.expires_at.strftime('%Y-%m-%d %H:%M:%S')} 过期")
        
        # 检查使用次数限制
        if api_key_obj.usage_limit and api_key_obj.usage_count >= api_key_obj.usage_limit:
            raise ValueError(f"API密钥使用次数已达上限 ({api_key_obj.usage_count}/{api_key_obj.usage_limit})")
        
        # 更新使用次数
        api_key_obj.usage_count += 1
        await api_key_obj.save()
        
        # 转换为响应对象
        result = ApiKeyInfo(
            id=str(api_key_obj.id),
            key_id=api_key_obj.key_id,
            name=api_key_obj.name,
            expires_at=api_key_obj.expires_at,
            usage_limit=api_key_obj.usage_limit,
            usage_count=api_key_obj.usage_count,
            is_active=api_key_obj.is_active,
            created_at=api_key_obj.created_at,
            updated_at=api_key_obj.updated_at
        )
        
        logger.info(f"API密钥验证成功: {api_key_obj.key_id} for resource {api_key_obj.resource_id}")
        return result
    
    async def get_user_api_keys(self, user_id: str, resource_id: Optional[str] = None) -> List[ApiKeyInfo]:
        """获取用户的API密钥列表"""
        try:
            query = ApiKey.filter(user_id=user_id, is_active=True)
            
            if resource_id:
                query = query.filter(resource_id=resource_id)
            
            api_keys = await query.order_by('-created_at')
            
            result = []
            for api_key_obj in api_keys:
                result.append(ApiKeyInfo(
                    id=str(api_key_obj.id),
                    key_id=api_key_obj.key_id,
                    name=api_key_obj.name,
                    expires_at=api_key_obj.expires_at,
                    usage_limit=api_key_obj.usage_limit,
                    usage_count=api_key_obj.usage_count,
                    is_active=api_key_obj.is_active,
                    created_at=api_key_obj.created_at,
                    updated_at=api_key_obj.updated_at
                ))
            
            return result
            
        except Exception as e:
            logger.error(f"获取用户API密钥列表失败: {e}")
            return []
    
    async def update_api_key(self, key_id: str, user_id: str, **kwargs) -> Tuple[bool, Optional[str]]:
        """更新API密钥"""
        try:
            api_key_obj = await ApiKey.get_or_none(key_id=key_id, user_id=user_id)
            
            if not api_key_obj:
                return False, "API密钥不存在"
            
            # 更新字段
            for field, value in kwargs.items():
                if hasattr(api_key_obj, field) and value is not None:
                    setattr(api_key_obj, field, value)
            
            await api_key_obj.save()
            logger.info(f"更新API密钥成功: {key_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"更新API密钥失败: {e}")
            return False, f"更新失败: {str(e)}"
    
    async def revoke_api_key(self, key_id: str, user_id: str) -> Tuple[bool, Optional[str]]:
        """撤销API密钥"""
        try:
            api_key_obj = await ApiKey.get_or_none(key_id=key_id, user_id=user_id)
            
            if not api_key_obj:
                return False, "API密钥不存在"
            
            api_key_obj.is_active = False
            await api_key_obj.save()
            
            logger.info(f"撤销API密钥成功: {key_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"撤销API密钥失败: {e}")
            return False, f"撤销失败: {str(e)}"


# 创建全局服务实例
identity_service = IdentityService()