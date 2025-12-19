# Micro-Sniper

> **One Bot, One Job** - 基于RPA + Agent + IM的矩阵式监控解决方案

## 🎯 商业模式

Micro-Sniper是一个矩阵式智能监控平台，第一期聚焦三个高价值场景：

- **Media-Sniper**: 爆款内容实时监控
- **Shop-Sniper**: 电商竞品价格追踪
- **Gig-Sniper**: 外包优质订单秒杀

底层技术统一，仅需更换监控源和Agent Prompt。

## 🏗️ 技术架构

### 核心技术栈

```yaml
Web框架:
  - Sanic 25.3.0 (高性能异步Web框架)
  - Gunicorn + Uvicorn (ASGI服务器)

数据存储:
  - PostgreSQL + Tortoise-ORM (异步数据库)
  - Redis (会话管理 & 缓存)

AI/自动化:
  - Agno 2.3.10 (AI Agent框架)
  - AgentBay SDK (云浏览器自动化)
  - OpenAI兼容接口

安全工具:
  - AES-256-GCM加密
  - Pydantic v2数据验证
  - Bearer Token认证

```

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                         │
│                    (REST API / WebSocket)                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      API Gateway                            │
│                 (Authentication & Rate Limit)               │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                 Business Logic Layer                        │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐         │
│  │ Media-Sniper│  │ Shop-Sniper  │  │ Gig-Sniper  │         │
│  │   Agent     │  │    Agent     │  │    Agent    │         │
│  └─────────────┘  └──────────────┘  └─────────────┘         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                 Connector Service Layer                     │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐         │
│  │ 小红书连接器 │  │  微信连接器   │  │ 通用连接器   │         │
│  └─────────────┘  └──────────────┘  └─────────────┘         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    Infrastructure                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐         │
│  │ AgentBay    │  │   Redis      │  │ PostgreSQL  │         │
│  │ 云浏览器     │  │   缓存       │  │   数据库     │         │
│  └─────────────┘  └──────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
Micro-Sniper/
├── api/                        # API接口层
│   ├── routes/                # REST API路由
│   │   ├── connectors.py      # 连接器相关API
│   │   ├── agent.py           # Agent API
│   │   └── identity.py        # 身份认证API
│   └── schema/                # Pydantic数据模型
│
├── services/                  # 核心业务服务
│   ├── connectors/            # 连接器服务（核心）
│   │   ├── base.py           # 连接器基类
│   │   ├── connector_service.py # 连接器管理
│   │   ├── xiaohongshu.py    # 小红书连接器
│   │   ├── wechat.py         # 微信连接器
│   │   └── generic.py        # 通用连接器
│   ├── agent_service.py       # AI Agent服务
│   ├── identity_service.py    # 身份认证服务
│   └── image_service.py       # 图像处理服务
│
├── models/                     # ORM数据模型
├── adapters/                   # 第三方服务适配器
├── middleware/                 # Sanic中间件
│   ├── auth.py                # 认证中间件
│   └── cors.py                # CORS中间件
│
├── utils/                      # 工具函数
├── config/                     # 配置管理
│   └── settings.py            # Pydantic配置
│
└── examples/                   # 示例代码
    └── monitor_example.py     # 监控示例
```

## 🚀 快速开始

### 环境要求
- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- Go 1.21+ (可选，仅MCP服务)
- Docker & Docker Compose

### 安装部署

1. **克隆项目**
```bash
git clone https://github.com/your-org/Micro-Sniper.git
cd Micro-Sniper
```

2. **环境配置**
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置
vim .env
```

3. **Docker部署（推荐）**
```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f micro-sniper
```

4. **本地开发**
```bash
# 安装Python依赖
pip install -r requirements.txt

# 启动PostgreSQL & Redis
docker-compose up -d postgres redis

# 运行数据库迁移
python -m db.init

# 启动服务
python -m app.main
```

### 验证安装

```bash
# 健康检查
curl http://localhost:8000/health

# API文档
open http://localhost:8000/docs
```

## 🔌 核心模块使用

### 1. 连接器服务

连接器是系统的核心，提供统一的接口来操作不同平台：

```python
from services.connectors.connector_service import ConnectorService

# 初始化服务
service = ConnectorService()

# 监控URL变化（Media-Sniper核心）
async def monitor_viral_content():
    result = await service.monitor(
        url="https://www.xiaohongshu.com/explore",
        platform="xiaohongshu",
        context_id="user_session_123",
        check_interval=300,  # 5分钟检查一次
        webhook_url="https://your-domain.com/webhook/viral-alert"
    )
    return result

# 提取内容摘要
async def extract_content():
    result = await service.extract(
        url="https://www.xiaohongshu.com/explore/xxxx",
        platform="xiaohongshu",
        extract_type="summary"
    )
    return result

# 批量采收用户内容
async def harvest_user_content():
    result = await service.harvest(
        user_id="target_user_123",
        platform="xiaohongshu",
        content_types=["note", "video"],
        limit=100
    )
    return result
```

### 2. Agent智能分析

Agent负责内容分析和决策：

```python
from services.agent_service import AgentService

# 初始化Agent
agent = AgentService()

# 分析爆款特征
async def analyze_viral_content(content):
    prompt = """
    分析这篇内容为什么可能成为爆款：
    1. 提取文案逻辑
    2. 识别情感触点
    3. 分析视觉元素
    4. 生成模仿建议
    """
    analysis = await agent.analyze(
        content=content,
        prompt=prompt,
        agent_type="media_analyzer"
    )
    return analysis

# 生成竞标话术（Gig-Sniper）
async def generate_proposal(job_description, user_profile):
    prompt = f"""
    基于以下信息生成高转化率的竞标话术：
    - 工作描述: {job_description}
    - 用户简历: {user_profile}
    - 要求: 突出技术优势，控制在200字内
    """
    proposal = await agent.generate(
        prompt=prompt,
        output_format="cover_letter"
    )
    return proposal
```

### 3. 价格监控（Shop-Sniper）

```python
# 监控竞品价格
async def monitor_price_change():
    service = ConnectorService()
    
    # 设置价格监控
    result = await service.monitor(
        url="https://product-page.com/item-123",
        platform="generic",
        check_interval=1800,  # 30分钟
        triggers={
            "price_change": True,
            "price_drop_threshold": 0.1  # 降价10%报警
        }
    )
    
    return result
```

## 📊 数据流设计

### 监控数据流

```
1. 定时任务触发 → 2. 连接器获取数据 → 3. 数据清洗 → 4. Agent分析 → 5. 规则引擎判断 → 6. 推送报警
```

### 实时数据流（WebSocket）

```python
# SSE流式返回
@app.route("/stream/monitor")
async def stream_monitor(request):
    async def event_stream():
        while True:
            data = await get_monitoring_data()
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(1)
    
    return stream(event_stream, content_type="text/event-stream")
```

## 🔐 身份认证

### API Key管理

```python
from services.identity_service import IdentityService

# 创建API Key
identity = IdentityService()
api_key = await identity.create_api_key(
    user_id="user_123",
    usage_limit=1000,
    expires_at=datetime.now() + timedelta(days=30)
)

# 验证请求
@app.middleware("request")
async def authenticate(request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not await identity.verify_api_key(token):
        return json({"error": "Unauthorized"}, status=401)
```

## 🛠️ 扩展开发

### 添加新平台连接器

1. **继承BaseConnector**

```python
from services.connectors.base import BaseConnector

class TikTokConnector(BaseConnector):
    platform = "tiktok"
    
    async def extract_content(self, url: str, **kwargs):
        # 实现TikTok特定逻辑
        await self.page.goto(url)
        # ...
        return structured_data
    
    async def monitor_changes(self, url: str, **kwargs):
        # 实现监控逻辑
        pass
```

2. **注册连接器**

```python
# 在connector_service.py中注册
CONNECTORS = {
    "xiaohongshu": XiaohongshuConnector,
    "wechat": WechatConnector,
    "tiktok": TikTokConnector,  # 新增
}
```

### 自定义Agent

```python
from agno import Agent

class CustomAgent(Agent):
    def __init__(self, **kwargs):
        super().__init__(
            name="custom_analyzer",
            instructions="自定义指令",
            tools=[custom_tool_1, custom_tool_2],
            **kwargs
        )
    
    async def analyze(self, input_data):
        # 自定义分析逻辑
        pass
```

## 📈 性能优化

### 1. 并发控制

```python
# 使用信号量控制并发
semaphore = asyncio.Semaphore(10)

async def limited_fetch(url):
    async with semaphore:
        return await fetch(url)
```

### 2. 缓存策略

```python
# Redis缓存
from aioredis import Redis

redis = Redis()

@cached(ttl=300)  # 5分钟缓存
async def get_user_profile(user_id):
    profile = await redis.get(f"profile:{user_id}")
    if not profile:
        profile = await fetch_profile(user_id)
        await redis.setex(f"profile:{user_id}", 300, profile)
    return profile
```

### 3. 数据库优化

```python
# 使用连接池
from tortoise import Tortoise

await Tortoise.init(
    db_url="postgresql://user:pass@localhost/db",
    modules={"models": ["models"]},
    # 连接池配置
    minsize=10,
    maxsize=20
)
```

## 🔧 配置说明

### 环境变量

```bash
# 应用配置
APP_NAME=Micro-Sniper
APP_VERSION=1.0.0
DEBUG=false
HOST=0.0.0.0
PORT=8000

# 数据库
DATABASE_URL=postgresql://user:password@localhost/microsniper

# Redis
REDIS_URL=redis://localhost:6379/0

# AgentBay
AGENTBAY_API_KEY=your-agentbay-key
AGENTBAY_ENDPOINT=https://api.agentbay.com

# OpenAI
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4-turbo

# 安全
SECRET_KEY=your-secret-key
ENCRYPTION_KEY=your-aes-key
```

## 🧪 测试

### 运行测试

```bash
# 单元测试
pytest tests/unit/

# 集成测试
pytest tests/integration/

# 性能测试
pytest tests/performance/
```

### 测试示例

```python
import pytest
from services.connectors.xiaohongshu import XiaohongshuConnector

@pytest.mark.asyncio
async def test_extract_content():
    connector = XiaohongshuConnector()
    result = await connector.extract_content(
        "https://www.xiaohongshu.com/explore/test"
    )
    
    assert result["title"] is not None
    assert result["content"] is not None
    assert "likes" in result["metrics"]
```

## 📜 API文档

完整的API文档请访问：`http://localhost:8000/docs`

### 主要端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/connectors/monitor` | POST | 启动监控任务 |
| `/connectors/extract` | POST | 提取内容 |
| `/connectors/harvest` | POST | 批量采收 |
| `/agent/analyze` | POST | Agent分析 |
| `/identity/api-keys` | POST | 创建API Key |

## 🤝 贡献指南

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙋‍♂️ 支持

- 技术支持：yancyyu@lazymind.vip
- Bug报告：yancyyu@lazymind.vip

---

**核心价值**：让每个业务场景都有专属的智能监控机器人