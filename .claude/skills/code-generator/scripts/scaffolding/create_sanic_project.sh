#!/bin/bash
# Sanic 项目脚手架生成器
# 快速创建符合最佳实践的 Sanic 项目

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 显示使用说明
show_usage() {
    cat << EOF

${BLUE}Sanic 项目脚手架生成器${NC}

用法: $0 <project_name>

示例: $0 my-api

${GREEN}这将创建:${NC}
  - 完整的 Sanic 项目目录结构
  - pyproject.toml (Poetry 配置)
  - app.py (Sanic 应用入口)
  - 示例路由和蓝图
  - Tortoise-ORM 配置
  - Redis 集成配置
  - 配置文件
  - .env.example
  - README.md

EOF
}

# 检查参数
if [ -z "$1" ]; then
    show_usage
    exit 1
fi

PROJECT_NAME=$1

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}    创建 Sanic 项目: $PROJECT_NAME${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# 检查项目名是否已存在
if [ -d "$PROJECT_NAME" ]; then
    echo -e "${RED}错误: 目录 '$PROJECT_NAME' 已存在${NC}"
    exit 1
fi

# 创建目录结构
echo -e "\n${GREEN}创建目录结构...${NC}"
mkdir -p "$PROJECT_NAME"/{api/{routes,schemas},services,models,middleware,config,utils,tests}

# 生成 pyproject.toml
echo -e "${GREEN}生成 pyproject.toml...${NC}"
cat > "$PROJECT_NAME/pyproject.toml" << EOF
[tool.poetry]
name = "$PROJECT_NAME"
version = "0.1.0"
description = "Sanic async application"
authors = ["Your Name <you@example.com>"]
readme = "README.md"

[tool.poetry.dependencies]
python = "^3.11"
sanic = "^23.6.0"
sanic-ext = "^23.6.0"
sanic-cors = "^2.2.0"
tortoise-orm = "^0.20.0"
asyncpg = "^0.29.0"
aioredis = "^2.0.1"
pydantic = "^2.5.3"
pydantic-settings = "^2.1.0"
python-dotenv = "^1.0.0"
aerich = "^0.7.2"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.4"
pytest-asyncio = "^0.23.3"
httpx = "^0.26.0"
black = "^23.12.1"
ruff = "^0.1.9"
mypy = "^1.8.0"
pre-commit = "^3.6.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.black]
line-length = 120
target-version = ['py311']

[tool.ruff]
target-version = "py311"
line-length = 120
select = ["E", "W", "F", "I", "B", "C4", "UP"]

[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
asyncio_mode = "auto"
EOF

# 生成 app.py（主应用）
echo -e "${GREEN}生成 app.py...${NC}"
cat > "$PROJECT_NAME/app.py" << 'EOF'
from sanic import Sanic, response
from sanic_ext import render, openapi
from sanic_cors import CORS
from config.settings import settings
from api.routes.health import bp as health_bp
from api.routes.users import bp as users_bp
from middleware.error_handlers import add_exception_handlers

# Create Sanic app
app = Sanic("MyAPI")
app.extend(config=settings)

# Setup CORS
CORS(app, resources={r"*": {"origins": settings.CORS_ORIGINS}}, automatic_options=True)

# Setup OpenAPI
openapi.url = "/docs"
openapi.version = "0.1.0"
app.ext.openapi.describe(
    title="My API",
    version="0.1.0",
    description="Sanic async API application"
)

# Register blueprints
app.blueprint(health_bp)
app.blueprint(users_bp)

# Exception handlers
add_exception_handlers(app)

@app.get("/")
async def root(request):
    """Root endpoint"""
    return response.json({
        "message": "Welcome to the API",
        "version": "0.1.0",
        "docs": "/docs"
    })

@app.listener("before_server_start")
async def setup_db(app, loop):
    """Initialize database connections"""
    from models.database import init_db
    await init_db(app)

@app.listener("before_server_stop")
async def close_db(app, loop):
    """Close database connections"""
    from models.database import close_db
    await close_db(app)

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=settings.DEBUG,
        workers=1 if settings.DEBUG else 4,
        access_log=settings.DEBUG
    )
EOF

# 生成健康检查路由
echo -e "${GREEN}生成示例路由...${NC}"
cat > "$PROJECT_NAME/api/routes/__init__.py" << 'EOF'
EOF

cat > "$PROJECT_NAME/api/routes/health.py" << 'EOF'
from sanic import Blueprint, response

bp = Blueprint("health", url_prefix="/health")

@bp.get("/")
async def health_check(request):
    """Health check endpoint"""
    return response.json({
        "status": "healthy",
        "service": "api"
    })
EOF

# 生成用户路由示例
cat > "$PROJECT_NAME/api/routes/users.py" << 'EOF'
from sanic import Blueprint, response
from sanic_ext import validate, openapi
from schemas.user import UserCreate, UserResponse
from services.user_service import UserService

bp = Blueprint("users", url_prefix="/api/users")

user_service = UserService()

@bp.post("/")
@validate(json=UserCreate)
@openapi.tag("users")
async def create_user(request, body: UserCreate):
    """Create a new user"""
    try:
        user = await user_service.create(body)
        return response.json(user, status=201)
    except ValueError as e:
        return response.json({"error": str(e)}, status=400)

@bp.get("/<user_id:int>")
@openapi.tag("users")
async def get_user(request, user_id: int):
    """Get user by ID"""
    user = await user_service.get_one(user_id)
    if not user:
        return response.json({"error": "Not found"}, status=404)
    return response.json(user)

@bp.get("/")
@openapi.tag("users")
async def list_users(request):
    """List all users"""
    skip = int(request.args.get("skip", 0))
    limit = int(request.args.get("limit", 100))
    users = await user_service.list(skip, limit)
    return response.json(users)
EOF

# 生成配置
echo -e "${GREEN}生成配置文件...${NC}"
cat > "$PROJECT_NAME/config/settings.py" << 'EOF'
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "My API"
    DEBUG: bool = False
    VERSION: str = "0.1.0"

    # Database (PostgreSQL with asyncpg)
    DATABASE_URL: str = "postgres://user:password@localhost/dbname"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings"""
    return Settings()

settings = get_settings()
EOF

cat > "$PROJECT_NAME/config/__init__.py" << 'EOF'
EOF

# 生成数据库配置
echo -e "${GREEN}生成数据库配置...${NC}"
cat > "$PROJECT_NAME/models/database.py" << 'EOF'
from tortoise import Tortoise
from config.settings import settings

TORTOISE_ORM = {
    "connections": {
        "default": settings.DATABASE_URL
    },
    "apps": {
        "models": {
            "models": ["models.user", "aerich.models"],
            "default_connection": "default",
        }
    }
}

async def init_db(app):
    """Initialize database connection"""
    await Tortoise.init(
        config=TORTOISE_ORM,
        generate_schemas=True
    )
    print("Database initialized")

async def close_db(app):
    """Close database connection"""
    await Tortoise.close_connections()
    print("Database connection closed")
EOF

# 生成用户模型
echo -e "${GREEN}生成模型...${NC}"
cat > "$PROJECT_NAME/models/__init__.py" << 'EOF'
from .user import User
__all__ = ["User"]
EOF

cat > "$PROJECT_NAME/models/user.py" << 'EOF'
from tortoise import fields
from models.database import Tortoise

class User(Tortoise):
    """User model"""

    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True)
    username = fields.CharField(max_length=100, unique=True)
    password_hash = fields.CharField(max_length=255)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"

    def __str__(self):
        return self.username
EOF

# 生成 Schema
echo -e "${GREEN}生成 Schema...${NC}"
cat > "$PROJECT_NAME/api/schemas/__init__.py" << 'EOF'
EOF

cat > "$PROJECT_NAME/api/schemas/user.py" << 'EOF'
from pydantic import BaseModel, EmailStr, Field

class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserResponse(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True
EOF

# 生成服务层
echo -e "${GREEN}生成服务层...${NC}"
cat > "$PROJECT_NAME/services/__init__.py" << 'EOF'
EOF

cat > "$PROJECT_NAME/services/user_service.py" << 'EOF'
from models.user import User
from api.schemas.user import UserCreate

class UserService:
    """User business logic"""

    async def create(self, data: UserCreate) -> dict:
        """Create a new user"""
        # Check if email exists
        existing = await User.filter(email=data.email).first()
        if existing:
            raise ValueError("Email already exists")

        # Check if username exists
        existing = await User.filter(username=data.username).first()
        if existing:
            raise ValueError("Username already exists")

        # Create user (password hashing should be done here)
        user = await User.create(
            email=data.email,
            username=data.username,
            password_hash=data.password  # TODO: Hash password
        )

        return {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat()
        }

    async def get_one(self, user_id: int) -> dict | None:
        """Get user by ID"""
        user = await User.get_or_none(id=user_id)
        if not user:
            return None

        return {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat()
        }

    async def list(self, skip: int = 0, limit: int = 100) -> list:
        """List all users"""
        users = await User.all().offset(skip).limit(limit)
        return [
            {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat()
            }
            for u in users
        ]
EOF

# 生成错误处理
echo -e "${GREEN}生成错误处理...${NC}"
cat > "$PROJECT_NAME/middleware/error_handlers.py" << 'EOF'
from sanic import response
from sanic.exceptions import SanicException

def add_exception_handlers(app):
    """Add all exception handlers to the app"""

    @app.exception(SanicException)
    async def sanic_exception(request, exception):
        """Handle Sanic exceptions"""
        return response.json(
            {"error": exception.message},
            status=exception.status_code
        )

    @app.exception(Exception)
    async def catch_all(request, exception):
        """Handle all other exceptions"""
        return response.json(
            {"error": "Internal server error"},
            status=500
        )
EOF

cat > "$PROJECT_NAME/middleware/__init__.py" << 'EOF'
EOF

# 生成测试
echo -e "${GREEN}生成测试文件...${NC}"
cat > "$PROJECT_NAME/tests/test_health.py" << 'EOF'
import pytest
from app import app

@pytest.fixture
def test_client():
    return app.test_client

def test_health_check(test_client):
    """Test health check endpoint"""
    request, response = test_client.get("/health")
    assert response.status == 200
    data = response.json
    assert data["status"] == "healthy"

def test_root(test_client):
    """Test root endpoint"""
    request, response = test_client.get("/")
    assert response.status == 200
    data = response.json
    assert "message" in data
    assert "version" in data
EOF

cat > "$PROJECT_NAME/tests/__init__.py" << 'EOF'
EOF

# 生成 Aerich 配置
echo -e "${GREEN}生成 Aerich 配置...${NC}"
cat > "$PROJECT_NAME/pyproject.toml.patch" << 'EOF'
# Add to your pyproject.toml:

[tool.aerich]
tortoise_orm = "models.database.TORTOISE_ORM"
location = "./migrations"
src_folder = "./"
EOF

cat > "$PROJECT_NAME/aerich.ini" << 'EOF'
[aerich]
tortoise_orm = "models.database.TORTOISE_ORM"
location = ./migrations
src_folder = ./
EOF

# 生成 .env.example
echo -e "${GREEN}生成 .env.example...${NC}"
cat > "$PROJECT_NAME/.env.example" << 'EOF'
# Application
APP_NAME=My API
DEBUG=true
VERSION=0.1.0

# Database (PostgreSQL)
DATABASE_URL=postgres://user:password@localhost:5432/dbname

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
EOF

# 生成 .gitignore
echo -e "${GREEN}生成 .gitignore...${NC}"
cat > "$PROJECT_NAME/.gitignore" << 'EOF'
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/
.venv/

# Testing
.pytest_cache/
.coverage
htmlcov/

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# ruff
.ruff_cache/

# Environment
.env
.env.local
.env.*.local

# IDEs
.idea/
.vscode/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Database
*.db
*.sqlite
*.sqlite3

# Migrations
!migrations/.gitkeep
EOF

# 生成 README.md
echo -e "${GREEN}生成 README.md...${NC}"
cat > "$PROJECT_NAME/README.md" << EOF
# $PROJECT_NAME

Sanic async application with best practices.

## Features

- ✅ Sanic with async support
- ✅ Tortoise-ORM for database
- ✅ Redis for caching
- ✅ Pydantic for validation
- ✅ Poetry for dependency management
- ✅ Black, Ruff, MyPy for code quality
- ✅ Pytest for testing
- ✅ Pre-commit hooks
- ✅ Environment configuration

## Quick Start

\`\`\`bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
cd $PROJECT_NAME
poetry install

# Copy environment file
cp .env.example .env

# Edit .env to configure PostgreSQL and Redis

# Initialize database migrations
aerich init -t models.database.TORTOISE_ORM
aerich init-db

# Run development server
poetry run python app.py
\`\`\`

## Development

\`\`\`bash
# Format code
poetry run black .

# Lint code
poetry run ruff check .

# Type check
poetry run mypy .

# Run tests
poetry run pytest

# Create migration
aerich migrate

# Upgrade database
aerich upgrade

# Install pre-commit hooks
poetry run pre-commit install
\`\`\`

## Project Structure

\`\`\`
$PROJECT_NAME/
├── api/
│   ├── routes/          # Sanic blueprints
│   └── schemas/         # Pydantic schemas
├── services/            # Business logic
├── models/              # Tortoise-ORM models
├── middleware/          # Custom middleware
├── config/              # Configuration
├── migrations/          # Database migrations (Aerich)
├── tests/               # Tests
├── app.py               # Application entry
├── aerich.ini           # Aerich configuration
├── pyproject.toml       # Dependencies
└── .env.example         # Environment template
\`\`\`

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- Redoc: http://localhost:8000/docs/redoc

## Database Setup

\`\`\`bash
# Install PostgreSQL
brew install postgresql  # macOS
sudo apt install postgresql  # Ubuntu

# Create database
createdb $PROJECT_NAME

# Run migrations
aerich init -t models.database.TORTOISE_ORM
aerich init-db
\`\`\`

## Redis Setup

\`\`\`bash
# Install Redis
brew install redis  # macOS
sudo apt install redis-server  # Ubuntu

# Start Redis
redis-server

# Test connection
redis-cli ping
\`\`\`

## Production Deployment

\`\`\`bash
# Run with multiple workers
poetry run python app.py --workers 4

# Or use gunicorn
poetry run gunicorn app:app --workers 4 --worker-class sanic.worker.GunicornWorker
\`\`\`

## Next Steps

1. Configure PostgreSQL in \`.env\`
2. Configure Redis in \`.env\`
3. Create your models in \`models/\`
4. Create blueprints in \`api/routes/\`
5. Implement services in \`services/\`
6. Write tests in \`tests/\`
7. Create migrations with Aerich

Happy coding! 🚀
EOF

# 完成
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}          项目创建成功！${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

cat << EOF

${GREEN}项目位置:${NC} $(pwd)/$PROJECT_NAME

${GREEN}下一步:${NC}
  1. cd $PROJECT_NAME
  2. poetry install
  3. cp .env.example .env
  4. 编辑 .env 配置 PostgreSQL 和 Redis
  5. 初始化数据库:
     aerich init -t models.database.TORTOISE_ORM
     aerich init-db
  6. poetry run python app.py
  7. 访问 http://localhost:8000/docs

${GREEN}开发命令:${NC}
  poetry run python app.py              # 运行服务器
  poetry run black .                    # 格式化代码
  poetry run ruff check .               # 检查代码
  poetry run mypy .                     # 类型检查
  poetry run pytest                     # 运行测试
  aerich migrate                        # 创建迁移
  aerich upgrade                        # 升级数据库

${YELLOW}提示:${NC}
  - Sanic 使用异步编程模式
  - Tortoise-ORM 类似 SQLAlchemy 但专为 async 设计
  - Aerich 用于数据库迁移（类似 Alembic）
  - 使用 Sanic Extensions 的 openapi 集成

EOF