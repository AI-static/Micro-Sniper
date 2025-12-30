# Connectors - 统一的网站内容提取与发布系统

## 架构说明

### 核心组件

```
services/connectors/
├── base.py              # BaseConnector - 基类，提供公共功能
├── xiaohongshu.py       # 小红书连接器
├── wechat.py            # 微信公众号连接器
├── generic.py           # 通用网站连接器
├── scene_service.py     # ConnectorService - 服务层，统一调度
├── example.py           # 使用示例
└── __init__.py          # 模块导出
```

### 设计原则

1. **继承基类**：所有连接器继承 `BaseConnector`，复用会话管理、浏览器初始化等逻辑
2. **统一接口**：所有连接器实现相同的接口（extract、monitor、harvest、publish）
3. **自动检测**：服务层自动检测URL所属平台，无需手动指定
4. **错误处理**：完善的错误处理和日志记录
5. **资源清理**：自动清理浏览器会话资源

## 四大核心功能

### 1. 提取 (Extract)
一次性获取指定URL的内容

```python
from services.connectors import connector_service

# 自动检测平台
results = await connector_service.extract_urls([
    "https://www.xiaohongshu.com/explore/xxx",
    "https://mp.weixin.qq.com/s/xxx"
])

# 使用自定义指令
results = await connector_service.extract_urls(
    urls=["https://www.xiaohongshu.com/explore/xxx"],
    instruction="只提取标题、作者和点赞数"
)

# 使用结构化 Schema
schema = {
    "title": "string",
    "author": "string",
    "like_count": "number"
}
results = await connector_service.extract_urls(
    urls=["https://www.xiaohongshu.com/explore/xxx"],
    schema=schema
)
```

### 2. 监控 (Monitor)
持续追踪URL变化，实时推送更新

```python
# 监控URL变化（每60秒检查一次）
async for change in connector_service.monitor_urls(
    urls=["https://www.xiaohongshu.com/explore/xxx"],
    check_interval=60
):
    print(f"检测到变化: {change}")
    # change 包含: url, type, changes, timestamp
```

### 3. 采收 (Harvest)
批量获取用户/账号的所有内容

```python
# 采收小红书用户笔记
notes = await connector_service.harvest_user_content(
    platform="xiaohongshu",
    user_id="5e8d7c9b000000000100000a",
    limit=10
)

# 采收微信公众号文章
articles = await connector_service.harvest_user_content(
    platform="wechat",
    user_id="MzI1MTUxMDY0MA==",  # __biz 参数
    limit=20
)
```

### 4. 发布 (Publish)
发布内容到平台（需要先登录）

```python
# 登录
await connector_service.login(
    platform="xiaohongshu",
    method="cookie",
    cookies={"web_session": "xxx", "webId": "xxx"}
)

# 发布文字笔记
result = await connector_service.publish_content(
    platform="xiaohongshu",
    content="测试内容",
    tags=["测试"]
)

# 发布图文笔记
result = await connector_service.publish_content(
    platform="xiaohongshu",
    content="分享美图",
    content_type="image",
    images=["https://example.com/image.jpg"],
    tags=["摄影"]
)
```

## 支持的平台

| 平台 | 提取 | 监控 | 采收 | 发布 | 登录 |
|-----|------|------|------|------|------|
| 小红书 (xiaohongshu) | ✅ | ✅ | ✅ | ✅ | ✅ (Cookie) |
| 微信公众号 (wechat) | ✅ | ✅ | ✅ | ❌ | ❌ |
| 通用网站 (generic) | ✅ | ✅ | ❌ | ❌ | ❌ |

## 扩展新平台

要添加新平台的支持，只需：

1. 创建新的连接器类，继承 `BaseConnector`
2. 实现 `extract_content` 方法（必需）
3. 根据需要实现其他方法（可选）

```python
from .base import BaseConnector

class NewPlatformConnector(BaseConnector):
    def __init__(self):
        super().__init__(platform_name="new_platform")

    async def extract_content(self, urls, instruction=None, schema=None):
        # 实现提取逻辑
        pass

    async def harvest_user_content(self, user_id, limit=None):
        # 可选：实现采收逻辑
        pass

    async def publish_content(self, content, content_type="text", images=None, tags=None):
        # 可选：实现发布逻辑
        pass
```

然后在 `scene_service.py` 中注册新平台：

```python
class ConnectorService:
    PLATFORM_IDENTIFIERS = {
        "xiaohongshu": ["xiaohongshu.com", "xhslink.com"],
        "wechat": ["mp.weixin.qq.com"],
        "new_platform": ["newplatform.com"],  # 添加识别标识
    }

    def _get_connector(self, platform: str):
        if platform == "new_platform":
            self._connectors[platform] = NewPlatformConnector()
        # ...
```

## 代码优化成果

重构前后对比：

| 文件 | 重构前 | 重构后 | 减少 |
|------|--------|--------|------|
| xiaohongshu.py | 378 行 | 262 行 | -31% |
| wechat.py | 211 行 | 150 行 | -29% |
| generic.py | 172 行 | 62 行 | -64% |
| scene_service.py | 149 行 | 320 行 | +115% (增加文档和错误处理) |

**总体改进：**
- ✅ 消除了大量重复代码（会话管理、浏览器初始化）
- ✅ 统一了接口和错误处理
- ✅ 添加了完善的日志记录
- ✅ 提供了清晰的使用示例
- ✅ 便于扩展新平台

## 依赖

- `playwright`: 浏览器自动化
- `agentbay`: AI Agent 服务
- `app.core.base`: 基础管理类
- `app.config.settings`: 配置管理
- `utils.logger`: 日志工具

## 注意事项

1. 需要配置 `AGENTBAY_API_KEY` 环境变量
2. 发布功能需要先通过 `login()` 方法登录
3. 监控功能会持续运行，需要在后台任务中使用
4. 使用完成后会自动清理资源，也可以手动调用 `cleanup()`
