"""监控配置相关数据模型"""
from enum import Enum
from tortoise.models import Model
from tortoise.fields import (
    CharField, IntField, BooleanField, DatetimeField, 
    TextField, UUIDField, JSONField
)
import uuid
from datetime import datetime
from utils.logger import logger


class MonitorConfig(Model):
    """监控配置模型 - 每个source_id的监控策略"""
    id = UUIDField(pk=True, default=uuid.uuid4)
    source_id = CharField(100, description="关联的源ID")
    name = CharField(200, description="配置名称")
    
    # 监控配置
    platform = CharField(50, description="监控平台：xiaohongshu/wechat/generic")
    is_active = BooleanField(default=True, description="是否启用")
    
    # 监控目标（JSON格式存储具体配置）
    targets = JSONField(description="监控目标配置", default=dict)
    """
    targets 示例:
    {
        "users": ["user_id_1", "user_id_2"],  # 监控的用户ID列表
        "urls": ["https://example.com/item1"], # 监控的URL列表
        "keywords": ["AI", "创业"],           # 关键词列表
        "hashtags": ["#科技", "#AI"],         # 标签列表
    }
    """
    
    # 触发条件
    triggers = JSONField(description="触发条件", default=list)
    """
    triggers 示例:
    [
        {
            "type": "like_threshold",
            "value": 1000,
            "time_window": 3600  # 1小时内
        },
        {
            "type": "price_change",
            "drop_threshold": 0.1  # 降价10%报警
        }
    ]
    """
    
    # 执行配置
    check_interval = IntField(default=300, description="检查间隔（秒）")
    webhook_url = CharField(500, null=True, description="报警回调URL")
    
    # 统计信息
    total_checks = IntField(default=0, description="总检查次数")
    total_triggers = IntField(default=0, description="总触发次数")
    last_check_at = DatetimeField(null=True, description="最后检查时间")
    last_trigger_at = DatetimeField(null=True, description="最后触发时间")
    
    # 时间戳
    created_at = DatetimeField(auto_now_add=True)
    updated_at = DatetimeField(auto_now=True)
    
    class Meta:
        table = "monitor_configs"
        indexes = [
            ("source_id", "is_active"),
            ("source_id", "platform"),
            ("platform", "is_active"),
            ("last_check_at",),
        ]
        unique_together = [("source_id", "name")]
    
    async def update_stats(self, triggered: bool = False):
        """更新统计信息"""
        self.total_checks += 1
        self.last_check_at = datetime.now()
        if triggered:
            self.total_triggers += 1
            self.last_trigger_at = datetime.now()
        await self.save()


class UserSession(Model):
    """用户会话管理 - 用于持久化登录态"""
    id = UUIDField(pk=True, default=uuid.uuid4)
    source_id = CharField(100, description="源ID")
    platform = CharField(50, description="平台")
    user_id = CharField(200, description="平台用户ID")
    
    # 会话信息
    context_id = CharField(200, description="AgentBay上下文ID")
    cookies = JSONField(description="登录Cookie信息", default=dict)
    
    # 状态
    is_active = BooleanField(default=True, description="是否活跃")
    last_used_at = DatetimeField(null=True, description="最后使用时间")
    expires_at = DatetimeField(null=True, description="过期时间")
    
    # 时间戳
    created_at = DatetimeField(auto_now_add=True)
    updated_at = DatetimeField(auto_now=True)
    
    class Meta:
        table = "user_sessions"
        indexes = [
            ("source_id", "platform"),
            ("context_id",),
            ("is_active", "expires_at"),
        ]
        unique_together = [("source_id", "platform", "user_id")]
    
    async def update_last_used(self):
        """更新最后使用时间"""
        self.last_used_at = datetime.now()
        await self.save()