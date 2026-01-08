# Micro-Sniper

> **AI Native 多平台内容监控与分析系统** - 基于云浏览器 + Agent 智能体架构

## 核心优势

✅ **Agent 直接阅读自然语言，无需解析**

✅ **日志包含：为什么做、做什么、结果如何、下一步**

✅ **结果以自然语言报告呈现，AI 可直接理解**

✅ **任务上下文完整可追溯**

## 技术栈

**Web 框架**
- Sanic (异步 Web 框架)

**数据库**
- Tortoise-ORM (异步 ORM)
- PostgreSQL
- Redis

**AI Agent**
- DashScope (通义千问)
- AgentBay (云浏览器 Agent)

**浏览器自动化**
- Playwright (CDP 直连)

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                            │
│                    (Sanic REST API)                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                  Task Service Layer                         │
│              (任务管理 - AI Native 核心)                     │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐        │
│  │趋势分析Agent │  │创作者监控Agent │  │  任务生命周期 │        │
│  └─────────────┘  └──────────────┘  └─────────────┘        │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                  Connector Service                          │
│          (统一的连接器管理和调度中心)                         │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐        │
│  │ 小红书连接器 │  │  微信连接器   │  │ 通用连接器   │        │
│  └─────────────┘  └──────────────┘  └─────────────┘        │
│                  分布式锁 + 频率限制                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   AgentBay Cloud                            │
│                    (云浏览器 + Agent)                        │
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
│   │   ├── sniper.py          # 狙击手任务 API
│   │   └── identity.py        # 身份认证 API
│   └── schema/                # Pydantic 数据模型
│
├── services/                  # 核心业务服务
│   ├── connectors/            # 连接器服务（核心）
│   │   ├── base.py           # 连接器基类
│   │   ├── connector_service.py # 连接器管理（分布式锁）
│   │   └── xiaohongshu.py    # 小红书连接器
│   │
│   ├── sniper/                # 狙击手服务
│   │   ├── xhs_creator.py    # 创作者监控狙击手
│   │   └── xhs_trend.py      # 趋势分析狙击手
│   │
│   ├── identity_service.py    # 身份认证服务
│   └── image_service.py       # 图像处理服务
│
├── models/                     # ORM 数据模型
│   ├── task.py                # 任务模型（AI Native 设计）
│   ├── identity.py            # 身份认证模型
│   └── connectors.py          # 连接器模型
│
├── middleware/                 # Sanic 中间件
│   ├── auth.py                # 认证中间件
│   └── exception_handler.py   # 异常处理
│
├── utils/                      # 工具函数
│   ├── cache.py               # Redis 分布式锁
│   └── logger.py              # 日志管理
│
├── config/                     # 配置管理
│   └── settings.py            # Pydantic 配置
│
└── app.py                      # 应用入口
```

## 🚀 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL 14+
- AgentBay API Key
- DashScope API Key (阿里云通义千问)

### 安装部署

**1. 克隆项目**

```bash
git clone https://github.com/your-org/Micro-Sniper.git
cd Micro-Sniper
```

**2. 安装依赖**

```bash
# 使用 poetry
poetry install

# 或使用 pip
pip install -r requirements.txt
```

**3. 环境配置**

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置
vim .env
```

**配置必要的环境变量：**

```bash
# AgentBay 配置
AGENTBAY_API_KEY=your-agentbay-api-key

# 数据库配置
DATABASE_URL=postgresql://user:password@localhost/microsniper
REDIS_URL=redis://localhost:6379/0

# AI 模型配置
DASHSCOPE_API_KEY=your-dashscope-api-key

# 应用配置
SECRET_KEY=your-secret-key
```

**4. 启动服务**

```bash
python -m app
```

**5. 验证安装**

```bash
curl http://localhost:8000/health
```

## 🤖 AI Native 功能

### 1. 任务系统 (AI Native 核心)

任务系统采用 **AI Native** 设计，所有日志和结果均为自然语言，结构化是为了存储，自然语言是为了理解。

```python
from models.task import Task

# 创建任务
task = await Task.create(
    source="system",
    source_id="system",
    task_type="creator_monitor"
)

# 记录步骤（自然语言）
await task.log_step(1, "获取创作者笔记列表",
    {"action": "harvest_user_content", "creators_count": 2},
    {"result_summary": "成功获取 2 个创作者的数据..."})

# 完成任务（自然语言报告）
await task.complete({
    "report": """
    监控任务完成
    ============================================================
    任务目标: 监控 2 个创作者近7天的新内容
    执行结果: 成功监控 2 个创作者
    发现内容: 共发现 5 篇近期发布的笔记
    ...
    """
})
```

**AI 可读的日志结构：**

- **为什么做** - `purpose` / `step_purpose`
- **做了什么** - `action` / 具体操作
- **结果如何** - `result_summary` 自然语言描述
- **下一步** - `next_step` / `next_action`

### 2. 核心狙击手服务

#### 创作者监控 (Creator Sniper)

监控指定创作者的最新内容，生成结构化摘要报告。

```python
from services.sniper.xhs_creator import CreatorSniper

# 初始化狙击手
sniper = CreatorSniper(
    source_id="system",
    source="system",
    playwright=playwright
)

# 执行监控
task, report = await sniper.monitor_creators(
    creator_ids=["5c4c5848000000001200de55", "657f31eb000000003d036737"]
)
```

#### 趋势分析 (Trend Sniper)

分析关键词的爆款趋势，生成深度分析报告。

```python
from services.sniper.xhs_trend import XiaohongshuTrendAgent

# 初始化分析器
analyzer = XiaohongshuTrendAgent(
    source_id="system",
    source="system",
    playwright=playwright,
    keywords="agent面试"
)

# 执行分析
task, analysis = await analyzer.analyze_trends()
```

### 3. 连接器服务

统一的平台内容提取能力，支持标准接口：

- **extract_summary_stream**: 流式摘要提取（Agent 分析）
- **get_note_details**: 详情获取（快速模式，CDP 直连）
- **harvest_user_content**: 主页采收（批量获取用户内容）
- **search_and_extract**: 搜索并提取（关键词搜索）
- **publish_content**: 内容发布（支持多平台）

```python
from services.connectors.connector_service import ConnectorService
from models.connectors import PlatformType

# 使用异步上下文管理器，自动管理锁
async with ConnectorService(playwright, source, source_id, task) as connector_service:
    # 获取笔记详情
    details = await connector_service.get_note_details(
        urls=["https://www.xiaohongshu.com/explore/xxxx"],
        platform=PlatformType.XIAOHONGSHU
    )
    return details
```

## 💡 技术亮点 (Technical Deep Dive)

### 1. 分布式锁 + 异步上下文管理器

系统实现了基于 Redis 的分布式锁机制，配合 Python 的 `async context manager`，确保资源安全和高并发控制。

#### 锁的粒度设计：用户级别锁

我们选择 **用户级别锁 (User-Level)** 而非任务级别锁。

**Key 格式**: `lock:{source}:{source_id}:{platform}:{operation}`

**优势**: 确保同一用户在同一平台的操作是串行的，有效防止因并发请求导致的平台风控（封号/限流）。

```python
# 示例：不同的任务会竞争同一个用户级别的锁
lock:system:system:xiaohongshu:get_note_detail
```

#### 自动化锁管理

通过实现 `__aenter__` 和 `__aexit__`，系统自动管理锁的生命周期。同时维护内存映射 `_active_task_locks`，确保即使在异常退出时，也能清理该 Task 持有的所有锁。

```python
class ConnectorService:
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self._task:
            task_id = str(self._task.id)
            # 释放该任务持有的所有锁
            await ConnectorService.release_task_locks(task_id)
            # 从活跃任务集合中移除
            ConnectorService.unregister_task(task_id)
```

#### 防死锁机制

1. **Redis 自动过期**: 所有锁均带有 TTL (默认 120-300 秒)
2. **Lua 脚本**: 保证释放操作的原子性
3. **异常安全**: `finally` 块确保锁释放
4. **内存清理**: 服务重启或 Context 退出时自动清理残留

### 2. 混合模式架构 (Hybrid Mode)

系统平衡了 **性能 (CDP)** 和 **智能 (Agent)**：

| 特性 | CDP 直连模式 | Agent 模式 |
|------|-------------|-----------|
| 速度 | ⚡️ 快 (~50ms) | 🐢 慢 (~1-3s) |
| 用途 | 数据提取、简单操作 | 复杂交互、弹窗处理 |
| 实现 | `page.evaluate()` | `agent.act_async()` |
| 成本 | 低 | 高（AI 消耗） |

**使用原则**: 默认使用 CDP 直连，遇到复杂情况自动降级或切换至 Agent 模式。

```python
# 混合模式示例
async def get_note_detail(self, url):
    # 尝试 CDP 直连（快速）
    try:
        data = await page.evaluate("...")
        return data
    except Exception:
        # 失败时降级到 Agent（智能）
        result = await agent.act_async(f"提取页面内容 {url}")
        return result
```

### 3. 批量处理与并发优化

为了解决批量获取详情时的风控问题，系统实现了 **分批 + 并发控制** 策略：

```python
# 分批获取笔记详情，避免浏览器拨打过快
batch_size = 3
all_details_results = []

for i in range(0, len(urls), batch_size):
    batch_urls = urls[i:i + batch_size]

    batch_results = await connector_service.get_note_details(
        urls=batch_urls,
        platform=PlatformType.XIAOHONGSHU,
        concurrency=2  # 每批内部并发2个
    )

    all_details_results.extend(batch_results)
```

**优化策略**:
- **分批处理**: 将大任务拆解为 `batch_size=3` 的小批次
- **内部并发**: 每个批次内部 `concurrency=2` 并行执行
- **效果**: 将 10 个同时请求的高风险操作，转化为平滑的流式请求，显著降低被封风险

**对比效果**:

| 指标 | 一次性处理 | 分批处理 (batch_size=3) |
|------|-----------|------------------------|
| 并发压力 | 10 个同时请求 | 最多 2 个同时请求 |
| 被封风险 | ⚠️ 高 | ✅ 低 |
| 资源消耗 | 🔥 高峰值 | 📊 平稳 |
| 失败重试 | 全部失败 | 仅失败批次需重试 |

### 4. 频率限制与熔断机制

系统实现了基于滑动窗口的频率限制算法：

```python
# 滑动窗口算法：10次/60秒
RATE_LIMIT_CONFIGS = RateLimitConfigs(
    xiaohongshu=PlatformRateLimits(
        get_note_detail=OperationRateLimit(
            max_requests=10,  # 时间窗口内最大请求数
            window=60,        # 时间窗口（秒）
            lock_timeout=180  # 锁超时时间（秒）
        ),
    )
)
```

**保护机制**:
- 防止同一操作过于频繁
- 避免触发平台风控
- 自动拒绝超限请求并返回友好提示

### 5. Session vs Context 架构

```
Session（会话）：
  - 临时的浏览器实例
  - 每次任务创建，用完即删
  - 生命周期：创建 → 使用 → 删除

Context（上下文）：
  - 持久化的浏览器状态（cookies、localStorage）
  - 可以被多个 Session 共享
  - 生命周期：登录创建 → 长期保存 → 手动删除
```

**工作流程**:
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

## 🔐 身份认证与 API

系统使用 **Bearer Token** 认证。

```bash
# 请求示例
curl -X POST http://localhost:8000/sniper/xhs-trend \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["agent面试"],
    "platform": "xiaohongshu"
  }'
```

### 多平台支持

系统支持 **3 大类平台**，提供统一的内容提取和监控能力：

| 平台 | 类别 | 内容提取 | 详情获取 | 采收 | 搜索 | 发布 | 登录 |
|------|------|---------|---------|------|------|------|------|
| 📕 **小红书** | 社交内容 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 💬 **微信公众号** | 内容平台 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 🌐 **通用网站** | 通用工具 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

**平台特性矩阵**:

```
┌─────────────┬──────────┬──────────┬────────┬────────┬────────┬──────────┐
│   平台      │ 内容提取  │ 详情获取  │ 采收   │ 搜索   │ 发布   │   登录   │
├─────────────┼──────────┼──────────┼────────┼────────┼────────┼──────────┤
│ 小红书      │   ✅     │   ✅     │  ✅   │  ✅   │  ✅   │    ✅    │
│ 微信公众号  │   ✅     │   ✅     │  ✅   │  ❌   │  ❌   │    ❌    │
│ 通用网站    │   ✅     │   ❌     │  ❌   │  ❌   │  ❌   │    ❌    │
└─────────────┴──────────┴──────────┴────────┴────────┴────────┴──────────┘
```

### 主要 API 端点

**任务管理**
- `POST /sniper/xhs-creator` - 创建创作者监控任务
- `POST /sniper/xhs-trend` - 创建趋势分析任务
- `GET /sniper/task/<task_id>` - 获取任务详情
- `GET /sniper/task/<task_id>/logs` - 获取任务日志
- `POST /sniper/tasks` - 查询任务列表

**多平台连接器服务**
- `GET /connectors/platforms` - **获取支持的平台列表及特性**
- `POST /connectors/login` - 扫码/Cookie 登录
- `POST /connectors/extract-summary` - 内容提取（Agent 分析）
- `POST /connectors/get-note-detail` - 获取笔记详情（快速模式）
- `POST /connectors/harvest` - 批量采收用户内容
- `POST /connectors/search-and-extract` - 搜索并提取
- `POST /connectors/publish` - 发布内容到平台

**身份认证**
- `POST /identity/api-keys` - 创建 API Key
- `GET /health` - 健康检查

## 📄 许可证

本项目采用 MIT 许可证

## 🙋‍♂️ 支持

- 技术支持：yancyyu@lazymind.vip

---

**核心价值**: AI Native 设计，让 Agent 像人类一样阅读和理解任务，实现真正的智能化内容监控