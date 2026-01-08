# 迁移指南：从分层架构到模块化架构

## 概述

本指南帮助你从传统的分层架构（Layer-based）迁移到模块化架构（Module-based/Feature-based）组织。

## 关键区别

### 分层架构（当前）
```
project/
├── routes/          # 所有路由
├── services/        # 所有服务
├── repositories/    # 所有数据访问
├── models/          # 所有模型
└── middleware/      # 中间件
```

### 模块化架构（目标）
```
project/
├── features/        # 功能模块
│   ├── users/       # 用户功能（完整）
│   │   ├── routes.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   └── models.py
│   └── posts/       # 帖子功能（完整）
│       ├── routes.py
│       ├── service.py
│       ├── repository.py
│       └── models.py
└── shared/          # 共享代码
    ├── middleware/
    ├── utils/
    └── config/
```

## 迁移步骤

### 第 1 步：识别功能边界

列出应用中的所有功能，例如：
- 用户管理
- 认证
- 帖子管理
- 评论
- 通知
- ...

### 第 2 步：创建模块结构

```
features/
├── auth/           # 认证功能
├── users/          # 用户管理
├── posts/          # 帖子管理
├── comments/       # 评论功能
└── notifications/  # 通知功能
```

### 第 3 步：移动文件

将相关文件移动到对应模块：

**之前**:
```
routes/user_routes.py
services/user_service.py
repositories/user_repository.py
models/user.py
```

**之后**:
```
features/users/
├── routes.py       # 从 routes/user_routes.py
├── service.py      # 从 services/user_service.py
├── repository.py   # 从 repositories/user_repository.py
└── models.py       # 从 models/user.py
```

### 第 4 步：更新导入

**之前（分层）**:
```python
from routes.user import user_router
from services.user_service import UserService
from models.user import User
```

**之后（模块化）**:
```python
from features.users.routes import user_router
from features.users.service import UserService
from features.users.models import User
```

### 第 5 步：提取共享代码

将跨功能的共享代码移到 `shared/` 目录：

```
shared/
├── middleware/
│   ├── auth.py
│   ├── logging.py
│   └── error_handlers.py
├── utils/
│   ├── validators.py
│   ├── helpers.py
│   └── decorators.py
└── config/
    ├── settings.py
    └── database.py
```

### 第 6 步：更新测试

重新组织测试以匹配模块结构：

```
tests/
├── features/
│   ├── auth/
│   │   ├── test_routes.py
│   │   └── test_service.py
│   └── users/
│       ├── test_routes.py
│       └── test_service.py
└── shared/
    ├── test_middleware.py
    └── test_utils.py
```

## 完整示例

### 迁移前（分层）

```
myapp/
├── main.py
├── routes/
│   ├── __init__.py
│   ├── user_routes.py
│   ├── post_routes.py
│   └── auth_routes.py
├── services/
│   ├── __init__.py
│   ├── user_service.py
│   ├── post_service.py
│   └── auth_service.py
├── repositories/
│   ├── __init__.py
│   ├── user_repository.py
│   ├── post_repository.py
│   └── auth_repository.py
├── models/
│   ├── __init__.py
│   ├── user.py
│   ├── post.py
│   └── auth.py
└── middleware/
    ├── __init__.py
    └── auth.py
```

### 迁移后（模块化）

```
myapp/
├── main.py
├── features/
│   ├── users/
│   │   ├── __init__.py
│   │   ├── routes.py       # 从 routes/user_routes.py
│   │   ├── service.py      # 从 services/user_service.py
│   │   ├── repository.py   # 从 repositories/user_repository.py
│   │   └── models.py       # 从 models/user.py
│   ├── posts/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   └── models.py
│   └── auth/
│       ├── __init__.py
│       ├── routes.py
│       ├── service.py
│       ├── repository.py
│       └── models.py
└── shared/
    ├── middleware/
    │   └── auth.py         # 从 middleware/auth.py
    ├── utils/
    │   ├── validators.py
    │   └── helpers.py
    └── config/
        └── database.py
```

## 更新 main.py

### 之前
```python
from routes.user_routes import user_router
from routes.post_routes import post_router
from routes.auth_routes import auth_router

app.include_router(user_router, prefix="/api/users")
app.include_router(post_router, prefix="/api/posts")
app.include_router(auth_router, prefix="/api/auth")
```

### 之后
```python
from features.users.routes import router as user_router
from features.posts.routes import router as post_router
from features.auth.routes import router as auth_router

app.include_router(user_router, prefix="/api/users")
app.include_router(post_router, prefix="/api/posts")
app.include_router(auth_router, prefix="/api/auth")
```

## 优势

### 模块化的优势

✅ **更好的内聚性**：相关代码在一起
✅ **更容易导航**：在同一个地方找到所有功能代码
✅ **支持微服务**：更容易提取功能到独立服务
✅ **清晰的边界**：功能依赖关系更明确
✅ **团队协作**：不同团队可以拥有不同的模块

### 权衡

⚠️ **可能的代码重复**：需要明确组织共享代码
⚠️ **循环依赖**：需要仔细管理依赖关系
⚠️ **学习曲线**：与传统的分层不同

## 何时使用哪种架构

### 使用分层架构当：
- 小型应用（< 10 个功能）
- 简单的 CRUD 操作
- 单个开发者或小团队
- 清晰的分层分离很重要

### 使用模块化架构当：
- 中大型应用（> 10 个功能）
- 功能团队并行工作
- 领域驱动设计方法
- 计划迁移到微服务

## 迁移策略

### 策略 1：渐进式迁移

1. 保留旧的分层结构
2. 为新功能创建模块
3. 逐步迁移现有功能
4. 删除旧的分层目录

### 策略 2：一次性迁移

1. 创建新的模块结构
2. 移动所有文件
3. 更新所有导入
4. 更新测试
5. 验证功能

### 策略 3：混合模式（过渡期）

```
project/
├── features/        # 新功能使用模块化
│   └── new_feature/
├── routes/          # 旧功能保持分层
├── services/
└── ...
```

## 迁移检查清单

- [ ] 识别所有功能模块
- [ ] 创建 features/ 目录结构
- [ ] 移动功能文件到模块
- [ ] 更新所有导入语句
- [ ] 提取共享代码到 shared/
- [ ] 重组测试目录
- [ ] 更新 main.py / app.js
- [ ] 验证所有功能正常
- [ ] 更新文档
- [ ] 删除旧的分层目录

## 提示

1. **一次迁移一个功能**：不要试图一次迁移所有功能
2. **保持测试通过**：迁移后立即运行测试
3. **使用 IDE 重构**：让 IDE 帮助更新导入
4. **提交到版本控制**：每个功能迁移后提交
5. **文档化**：更新团队文档
6. **耐心**：迁移需要时间，不要急于求成

## 常见问题

**Q: 如果我有一个用户服务被多个模块使用怎么办？**

A: 将通用服务放在 `shared/services/` 或 `shared/utils/` 中。

**Q: 我应该如何处理跨模块的关系？**

A: 在需要的模块中导入其他模块的模型。例如，`Post` 模块可以导入 `User` 模型。

**Q: 这是否意味着我不应该有服务层？**

A: 不，仍然有服务层，只是它在功能模块内，而不是在全局 services/ 目录中。

**Q: 我应该如何处理数据库模型？**

A: 通用模型（如 Base）放在 `shared/models/` 中，特定功能的模型放在功能模块中。