# Micro-Sniper

> 基于云浏览器 + RPA 的多平台内容提取与监控系统

## 🎯 项目简介

Micro-Sniper 是一个统一的内容提取与监控平台，支持多个主流平台（小红书、微信公众号等）的内容采集、分析和监控。

**核心能力：**
- 多平台内容提取（支持小红书、微信公众号、通用网站）
- Cookie 登录态管理（持久化 Context）
- 混合模式：CDP 直连 + Agent 自动化
- 流式处理 + 并发控制

## 🏗️ 技术架构

### 核心技术栈

```
Web框架:
  - Sanic (异步 Web 框架)
  - Tortoise-ORM (异步数据库)

浏览器自动化:
  - AgentBay SDK (云浏览器服务)
  - Playwright (CDP 协议连接)

数据存储:
  - PostgreSQL
  - Redis
```

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                            │
│                    (Sanic REST API)                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                  Connector Service                          │
│          (统一的连接器管理和调度中心)                         │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐        │
│  │ 小红书连接器 │  │  微信连接器   │  │ 通用连接器   │        │
│  └─────────────┘  └──────────────┘  └─────────────┘        │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Base Connector                            │
│              (连接器基类 - 公共逻辑)                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  agent_bay          playwright  _get_browser_session  │  │
│  │  (AgentBay SDK)     (CDP连接)     (会话管理)          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    AgentBay Cloud                            │
│                    (云浏览器服务)                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Session 管理     Context 持久化    Browser 实例     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
Micro-Sniper/
├── api/                        # API 接口层
│   ├── routes/                
│   │   ├── connectors.py      # 连接器相关 API
│   │   ├── identity.py        # 身份认证 API
│   │   └── image.py           # 图片处理 API
│   └── schema/                # Pydantic 数据模型
│
├── services/                  # 核心业务服务
│   ├── connectors/            # 连接器服务（核心）
│   │   ├── base.py           # 连接器基类
│   │   ├── connector_service.py # 连接器管理
│   │   ├── xiaohongshu.py    # 小红书连接器
│   │   ├── wechat.py         # 微信公众号连接器
│   │   └── generic.py        # 通用网站连接器
│   ├── identity_service.py    # 身份认证服务
│   └── image_service.py       # 图像处理服务
│
├── models/                     # ORM 数据模型
├── middleware/                 # Sanic 中间件
│   ├── auth.py                # 认证中间件
│   └── exception_handler.py   # 异常处理
│
├── utils/                      # 工具函数
├── config/                     # 配置管理
│   └── settings.py            # Pydantic 配置
│
├── adapters/                   # 第三方服务适配器
└── app.py                      # 应用入口
```

## 🚀 快速开始

### 环境要求
- Python 3.12+
- PostgreSQL 14+
- AgentBay API Key

### 安装部署

1. **克隆项目**
```bash
git clone https://github.com/your-org/Micro-Sniper.git
cd Micro-Sniper
```

2. **安装依赖**
```bash
# 使用 poetry
poetry install

# 或使用 pip
pip install -r requirements.txt
```

3. **环境配置**
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置
vim .env
```

必要的环境变量：
```bash
# AgentBay 配置
AGENTBAY_API_KEY=your-agentbay-api-key

# 数据库配置
DATABASE_URL=postgresql://user:password@localhost/microsniper

# 应用配置
SECRET_KEY=your-secret-key
```

4. **启动服务**
```bash
python -m app
```

5. **验证安装**
```bash
curl http://localhost:8000/health
```

## 🔌 核心模块使用

### 1. 连接器服务

连接器是系统的核心，提供统一的接口来操作不同平台：

```python
from services.connector_service import connector_service
from models.connectors import PlatformType

# 提取内容摘要
async def extract_content():
    results = await connector_service.extract_summary_stream(
        urls=["https://www.xiaohongshu.com/explore/xxxx"],
        platform=PlatformType.XIAOHONGSHU,
        source="default",
        source_id="default",
        concurrency=3
    )
    async for result in results:
        print(result)

# 获取笔记详情（快速模式）
async def get_note_details():
    details = await connector_service.get_note_details(
        urls=["https://www.xiaohongshu.com/explore/xxxx"],
        platform=PlatformType.XIAOHONGSHU,
        concurrency=3
    )
    return details

# 批量采收用户内容
async def harvest_user():
    content = await connector_service.harvest_user_content(
        platform=PlatformType.XIAOHONGSHU,
        user_id="5f3c4e2d000000000100003c",
        limit=100
    )
    return content

# 通过创作者 ID 提取
async def extract_by_creator():
    results = await connector_service.extract_by_creator_id(
        platform=PlatformType.XIAOHONGSHU,
        creator_id="5f3c4e2d000000000100003c",
        limit=50,
        extract_details=True
    )
    return results

# 搜索并提取
async def search_and_extract():
    results = await connector_service.search_and_extract(
        platform=PlatformType.XIAOHONGSHU,
        keyword="美食",
        limit=20,
        extract_details=True
    )
    return results
```

### 2. Cookie 登录

使用 Cookie 登录并持久化 Context：

```python
# 登录小红书
async def login_xiaohongshu():
    cookies = {
        "web_session": "xxxx",
        "a1": "yyyy",
        # ... 其他 cookies
    }
    
    context_id = await connector_service.login(
        platform=PlatformType.XIAOHONGSHU,
        method=LoginMethod.COOKIE,
        cookies=cookies,
        source="my_app",
        source_id="user_123"
    )
    
    print(f"登录成功，Context ID: {context_id}")
    return context_id
```

**Context ID 格式：** `{platform}-context:{source}:{source_id}`
- 例如：`xiaohongshu-context:my_app:user_123`

### 3. 发布内容（待实现）

```python
# 发布内容到小红书
async def publish_content():
    result = await connector_service.publish_content(
        platform=PlatformType.XIAOHONGSHU,
        content="这是一篇测试笔记",
        content_type="text",
        tags=["测试", "API"]
    )
    return result
```

## 🔧 核心概念

### 混合模式架构

系统采用"混合模式"来平衡性能和灵活性：

```
┌─────────────────────────────────────────────────────────────┐
│                      你的代码                                │
└────────────┬──────────────────────────────────┬─────────────┘
             │                                  │
    快速模式（CDP 直连）                Agent 模式（自动化）
             │                                  │
    page.evaluate()                    agent.act_async()
             │                                  │
    ┌────────▼──────────┐         ┌──────────▼──────────┐
    │  Playwright CDP   │         │   AgentBay Agent    │
    │  直接发 JS 命令    │         │   AI 分析 + 执行     │
    └────────┬──────────┘         └──────────┬──────────┘
             │                                  │
             └────────────┬─────────────────────┘
                          │
                ┌─────────▼──────────┐
                │  AgentBay Browser  │
                │  (远程 Chrome)     │
                └────────────────────┘
```

**两种模式对比：**

| 特性 | CDP 直连模式 | Agent 模式 |
|------|-------------|-----------|
| 速度 | ⚡️ 快 (~50ms) | 🐢 慢 (~1-3s) |
| 用途 | 数据提取、简单操作 | 复杂交互、弹窗处理 |
| 实现 | `page.evaluate()` | `agent.act_async()` |
| 成本 | 低 | 高（AI 消耗） |

**使用原则：**
- 简单操作（提取数据、点击）→ CDP 直连
- 复杂操作（关闭弹窗、滚动、智能交互）→ Agent

### Session vs Context

```
Session（会话）：
  - 临时的浏览器实例
  - 每次任务创建，用完即删
  - 通过 agent_bay.create() 创建
  - 生命周期：创建 → 使用 → 删除

Context（上下文）：
  - 持久化的浏览器状态（cookies、localStorage）
  - 可以被多个 Session 共享
  - 通过 context_id 标识
  - 生命周期：登录创建 → 长期保存 → 手动删除
```

**工作流程：**
```
1. 登录时创建 Context
   └──> 保存 cookies 等登录态
   
2. 每次任务创建 Session
   └──> 关联到已存在的 Context
   └──> 继承登录态
   
3. 任务完成删除 Session
   └──> Context 保持不变
   
4. 下次任务继续使用同一 Context
```

### 并发模型

**每个请求都是独立的：**
```
请求 1: agent_bay.create() → session1 → CDP 连接 1 → 执行 → 删除
请求 2: agent_bay.create() → session2 → CDP 连接 2 → 执行 → 删除
请求 3: agent_bay.create() → session3 → CDP 连接 3 → 执行 → 删除
```

- 每个 session 有独立的远程 browser
- 每个 CDP 连接是独立的 WebSocket
- 无全局瓶颈，支持高并发

## 📊 API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/connectors/extract` | POST | 提取内容摘要 |
| `/connectors/notes/details` | POST | 获取笔记详情 |
| `/connectors/harvest` | POST | 批量采收用户内容 |
| `/connectors/search` | POST | 搜索并提取 |
| `/connectors/creator/:id` | POST | 通过创作者 ID 提取 |
| `/connectors/login` | POST | Cookie 登录 |
| `/identity/api-keys` | POST | 创建 API Key |

## 🔐 身份认证

系统使用 Bearer Token 认证：

```bash
# 请求示例
curl -X POST http://localhost:8000/connectors/extract \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://www.xiaohongshu.com/explore/xxxx"],
    "platform": "xiaohongshu"
  }'
```

## 🛠️ 扩展开发

### 添加新平台连接器

1. **继承 BaseConnector**

```python
from services.connectors.base import BaseConnector
from models.connectors import PlatformType

class TikTokConnector(BaseConnector):
    def __init__(self):
        super().__init__(platform_name=PlatformType.TIKTOK)
    
    def _build_context_id(self, source: str, source_id: str) -> str:
        return f"{self.platform_name.value}-context:{source}:{source_id}"
    
    async def extract_summary_stream(self, urls, **kwargs):
        """实现提取逻辑"""
        session = await self._get_browser_session(source, source_id)
        # ... CDP 直连提取
        await self.agent_bay.delete(session, sync_context=False)
    
    async def get_note_detail(self, urls, **kwargs):
        """实现详情提取"""
        ...
```

2. **注册连接器**

```python
# 在 connector_service.py 中添加
elif platform == PlatformType.TIKTOK:
    self._connectors[platform] = TikTokConnector()
```

## 🔧 配置说明

### 环境变量

```bash
# 应用配置
APP_NAME=Aether
DEBUG=false
HOST=0.0.0.0
PORT=8000

# 数据库
DATABASE_URL=postgresql://user:password@localhost/microsniper

# AgentBay
AGENTBAY_API_KEY=your-agentbay-key

# 安全
SECRET_KEY=your-secret-key
ENCRYPTION_KEY=your-aes-key
```

## 📈 性能考虑

### 当前架构优势
- ✅ 无全局瓶颈，每个请求独立
- ✅ CDP 连接开销小（~50ms）
- ✅ 混合模式，简单操作不走 Agent

### 性能参数
- `concurrency`: 并发数控制（建议 3-10）
- Session 用完即删，无状态管理开销
- Context 复用，避免重复登录

## 📄 许可证

本项目采用 MIT 许可证

## 🙋‍♂️ 支持

- 技术支持：yancyyu@lazymind.vip

---

**核心价值**：统一的多平台内容提取能力，简单易用，性能高效