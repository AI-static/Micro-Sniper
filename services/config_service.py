"""配置管理服务"""
from typing import List, Optional, Dict, Any
from tortoise.exceptions import IntegrityError
from models.config import MonitorConfig, UserSession
from utils.logger import logger
from datetime import datetime, timedelta


class ConfigService:
    """配置管理服务"""
    
    async def create_monitor_config(
        self,
        source_id: str,
        name: str,
        platform: str,
        targets: Dict[str, Any],
        triggers: List[Dict[str, Any]],
        check_interval: int = 300,
        webhook_url: Optional[str] = None
    ) -> MonitorConfig:
        """创建监控配置"""
        try:
            config = await MonitorConfig.create(
                source_id=source_id,
                name=name,
                platform=platform,
                targets=targets,
                triggers=triggers,
                check_interval=check_interval,
                webhook_url=webhook_url
            )
            logger.info(f"创建监控配置成功: {config.id}")
            return config
        except IntegrityError:
            logger.error(f"配置名称已存在: source_id={source_id}, name={name}")
            raise ValueError("配置名称已存在")
        except Exception as e:
            logger.error(f"创建监控配置失败: {e}")
            raise
    
    async def get_monitor_configs(
        self,
        source_id: Optional[str] = None,
        platform: Optional[str] = None,
        is_active: bool = True
    ) -> List[MonitorConfig]:
        """获取监控配置列表"""
        # 如果source_id为None（系统管理员），则返回所有配置
        if source_id is None:
            query = MonitorConfig.filter(is_active=is_active)
        else:
            query = MonitorConfig.filter(source_id=source_id, is_active=is_active)
        
        if platform:
            query = query.filter(platform=platform)
        
        configs = await query.order_by("-created_at")
        return configs
    
    async def get_monitor_config(
        self,
        config_id: str,
        source_id: Optional[str] = None
    ) -> Optional[MonitorConfig]:
        """获取单个监控配置"""
        query = MonitorConfig.filter(id=config_id)
        
        # 如果提供了source_id，则进行过滤
        # 如果source_id为None（系统管理员），则不过滤
        if source_id is not None:
            query = query.filter(source_id=source_id)
        
        config = await query.first()
        return config
    
    async def update_monitor_config(
        self,
        config_id: str,
        source_id: str,
        **kwargs
    ) -> Optional[MonitorConfig]:
        """更新监控配置"""
        config = await self.get_monitor_config(config_id, source_id)
        if not config:
            return None
        
        # 更新字段
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        await config.save()
        logger.info(f"更新监控配置成功: {config_id}")
        return config
    
    async def delete_monitor_config(
        self,
        config_id: str,
        source_id: str
    ) -> bool:
        """删除监控配置（软删除）"""
        config = await self.get_monitor_config(config_id, source_id)
        if not config:
            return False
        
        config.is_active = False
        await config.save()
        logger.info(f"删除监控配置成功: {config_id}")
        return True
    
    async def get_active_configs_for_monitor(self) -> List[MonitorConfig]:
        """获取所有需要监控的活跃配置"""
        configs = await MonitorConfig.filter(is_active=True).prefetch_related()
        return configs
    
    # UserSession 管理
    async def create_or_update_session(
        self,
        source_id: str,
        platform: str,
        user_id: str,
        context_id: str,
        cookies: Dict[str, Any],
        expires_in_hours: int = 24
    ) -> UserSession:
        """创建或更新用户会话"""
        # 查找现有会话
        session = await UserSession.filter(
            source_id=source_id,
            platform=platform,
            user_id=user_id
        ).first()
        
        expires_at = datetime.now() + timedelta(hours=expires_in_hours)
        
        if session:
            # 更新现有会话
            session.context_id = context_id
            session.cookies = cookies
            session.expires_at = expires_at
            session.is_active = True
            session.last_used_at = datetime.now()
            await session.save()
            logger.info(f"更新用户会话: {session.id}")
        else:
            # 创建新会话
            session = await UserSession.create(
                source_id=source_id,
                platform=platform,
                user_id=user_id,
                context_id=context_id,
                cookies=cookies,
                expires_at=expires_at
            )
            logger.info(f"创建用户会话: {session.id}")
        
        return session
    
    async def get_session(
        self,
        source_id: str,
        platform: str,
        user_id: Optional[str] = None
    ) -> Optional[UserSession]:
        """获取用户会话"""
        query = UserSession.filter(
            source_id=source_id,
            platform=platform,
            is_active=True
        )
        
        if user_id:
            query = query.filter(user_id=user_id)
        
        session = await query.first()
        
        # 检查是否过期
        if session and session.is_expired():
            session.is_active = False
            await session.save()
            return None
        
        return session
    
    async def get_session_by_context(
        self,
        context_id: str
    ) -> Optional[UserSession]:
        """通过context_id获取会话"""
        session = await UserSession.filter(
            context_id=context_id,
            is_active=True
        ).first()
        
        if session and session.is_expired():
            session.is_active = False
            await session.save()
            return None
        
        return session
    
    async def invalidate_session(
        self,
        source_id: str,
        platform: str,
        user_id: str
    ) -> bool:
        """使用户会话失效"""
        session = await UserSession.filter(
            source_id=source_id,
            platform=platform,
            user_id=user_id,
            is_active=True
        ).first()
        
        if session:
            session.is_active = False
            await session.save()
            logger.info(f"使用户会话失效: {session.id}")
            return True
        
        return False