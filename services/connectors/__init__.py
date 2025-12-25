"""
连接器模块 - 统一的网站内容提取与发布系统

架构说明：
- BaseConnector: 所有连接器的基类，提供会话管理、浏览器初始化等公共功能
- XiaohongshuConnector: 小红书连接器，支持登录、提取、发布、监控、采收
- WechatConnector: 微信公众号连接器，支持提取、监控、采收
- GenericConnector: 通用网站连接器，支持任何网站的内容提取
- ConnectorService: 连接器服务层，提供统一的调度和管理

使用方式：
```python
from services.connectors import connector_service

# 提取内容
results = await connector_service.extract_urls([
    "https://www.xiaohongshu.com/explore/xxx",
    "https://mp.weixin.qq.com/s/xxx"
])

# 采收用户内容
notes = await connector_service.harvest_user_content(
    platform="xiaohongshu",
    user_id="user123",
    limit=10
)

# 发布内容
result = await connector_service.publish_content(
    platform="xiaohongshu",
    content="测试内容",
    tags=["测试"]
)
```
"""

from .base import BaseConnector
from .xiaohongshu import XiaohongshuConnector
from .wechat import WechatConnector

__all__ = [
    # 基类
    "BaseConnector",

    # 平台连接器
    "XiaohongshuConnector",
    "WechatConnector"
]

__version__ = "2.0.0"
