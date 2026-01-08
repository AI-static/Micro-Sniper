#!/bin/bash
# FastAPI 项目脚手架生成器
# 快速创建符合最佳实践的 FastAPI 项目

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

${BLUE}FastAPI 项目脚手架生成器${NC}

用法: $0 <project_name>

示例: $0 my-api

${GREEN}这将创建:${NC}
  - 完整的项目目录结构
  - pyproject.toml (Poetry 配置)
  - main.py (FastAPI 应用入口)
  - 示例路由和服务
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
echo -e "${BLUE}    创建 FastAPI 项目: $PROJECT_NAME${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# 检查项目名是否已存在
if [ -d "$PROJECT_NAME" ]; then
    echo -e "${RED}错误: 目录 '$PROJECT_NAME' 已存在${NC}"
    exit 1
fi

# 创建目录结构
echo -e "\n${GREEN}创建目录结构...${NC}"
mkdir -p "$PROJECT_NAME"/{api/{routes,schema},services,models,middleware,config,utils,tests}

# 生成 pyproject.toml
echo -e "${GREEN}生成 pyproject.toml...${NC}"
cat > "$PROJECT_NAME/pyproject.toml" << EOF
[tool.poetry]
name = "$PROJECT_NAME"
version = "0.1.0"
description = "FastAPI application"
authors = ["Your Name <you@example.com>"]
readme = "README.md"

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.109.0"
uvicorn = {extras = ["standard"], version = "^0.27.0"}
sqlalchemy = "^2.0.25"
alembic = "^1.13.1"
pydantic = "^2.5.3"
pydantic-settings = "^2.1.0"
python-dotenv = "^1.0.0"
python-multipart = "^0.0.6"

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
EOF

# 生成 main.py
echo -e "${GREEN}生成 main.py...${NC}"
cat > "$PROJECT_NAME/main.py" << 'EOF'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.health import router as health_router
from config.settings import settings
from middleware.error_handlers import add_exception_handlers

app = FastAPI(
    title="My API",
    description="FastAPI application",
    version="0.1.0",
    debug=settings.DEBUG
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
add_exception_handlers(app)

# Include routers
app.include_router(health_router, tags=["health"])

@app.get("/")
async def root():
    return {
        "message": "Welcome to the API",
        "version": "0.1.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
EOF

# 生成健康检查路由
echo -e "${GREEN}生成示例路由...${NC}"
mkdir -p "$PROJECT_NAME/api/routes"
cat > "$PROJECT_NAME/api/routes/__init__.py" << 'EOF'
EOF

cat > "$PROJECT_NAME/api/routes/health.py" << 'EOF'
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "api"
    }
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

    # Database
    DATABASE_URL: str = "sqlite:///./app.db"

    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

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

# 生成错误处理中间件
echo -e "${GREEN}生成错误处理...${NC}"
cat > "$PROJECT_NAME/middleware/error_handlers.py" << 'EOF'
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation error",
            "details": exc.errors()
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error"}
    )

def add_exception_handlers(app: FastAPI):
    """Add all exception handlers to the app"""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
EOF

cat > "$PROJECT_NAME/middleware/__init__.py" << 'EOF'
EOF

# 生成示例 Schema
echo -e "${GREEN}生成示例 Schema...${NC}"
cat > "$PROJECT_NAME/api/schema/__init__.py" << 'EOF'
EOF

cat > "$PROJECT_NAME/api/schema/common.py" << 'EOF'
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
    service: str

class ErrorResponse(BaseModel):
    error: str
    details: dict = None
EOF

# 生成示例 Service
echo -e "${GREEN}生成示例 Service...${NC}"
cat > "$PROJECT_NAME/services/__init__.py" << 'EOF'
EOF

cat > "$PROJECT_NAME/services/base.py" << 'EOF'
from typing import Generic, TypeVar, Type, Optional, List

ModelType = TypeVar("ModelType")

class BaseService(Generic[ModelType]):
    """Base service with common CRUD operations"""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, id: int) -> Optional[ModelType]:
        """Get one by ID"""
        return await self.model.get(id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Get all with pagination"""
        return await self.model.get_all(skip, limit)

    async def create(self, **kwargs) -> ModelType:
        """Create new"""
        return await self.model.create(**kwargs)

    async def update(self, id: int, **kwargs) -> Optional[ModelType]:
        """Update"""
        return await self.model.update(id, **kwargs)

    async def delete(self, id: int) -> bool:
        """Delete"""
        return await self.model.delete(id)
EOF

# 生成示例 Model
echo -e "${GREEN}生成示例 Model...${NC}"
cat > "$PROJECT_NAME/models/__init__.py" << 'EOF'
EOF

cat > "$PROJECT_NAME/models/base.py" << 'EOF'
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class BaseModel(Base):
    """Base model with common fields"""
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
EOF

# 生成数据库配置
cat > "$PROJECT_NAME/models/database.py" << 'EOF'
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from config.settings import settings

# For async support (PostgreSQL)
# DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
# engine = create_async_engine(DATABASE_URL)
# AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# For SQLite (synchronous)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
EOF

# 生成测试
echo -e "${GREEN}生成测试文件...${NC}"
cat > "$PROJECT_NAME/tests/test_health.py" << 'EOF'
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data

def test_root():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
EOF

cat > "$PROJECT_NAME/tests/__init__.py" << 'EOF'
EOF

# 生成 .env.example
echo -e "${GREEN}生成 .env.example...${NC}"
cat > "$PROJECT_NAME/.env.example" << 'EOF'
# Application
APP_NAME=My API
DEBUG=true
VERSION=0.1.0

# Database
DATABASE_URL=sqlite:///./app.db
# DATABASE_URL=postgresql://user:password@localhost/dbname

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
EOF

# 生成 README.md
echo -e "${GREEN}生成 README.md...${NC}"
cat > "$PROJECT_NAME/README.md" << EOF
# $PROJECT_NAME

FastAPI application with best practices.

## Features

- ✅ FastAPI with async support
- ✅ SQLAlchemy for database
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

# Run development server
poetry run uvicorn main:app --reload
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

# Install pre-commit hooks
poetry run pre-commit install
\`\`\`

## Project Structure

\`\`\`
$PROJECT_NAME/
├── api/
│   ├── routes/          # API routes
│   └── schema/          # Pydantic schemas
├── services/            # Business logic
├── models/              # Database models
├── middleware/          # Custom middleware
├── config/              # Configuration
├── tests/               # Tests
├── main.py              # Application entry
├── pyproject.toml       # Dependencies
└── .env.example         # Environment template
\`\`\`

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Next Steps

1. Configure your database in \`.env\`
2. Add your routes in \`api/routes/\`
3. Create models in \`models/\`
4. Implement services in \`services/\`
5. Write tests in \`tests/\`

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
  4. 编辑 .env 配置数据库
  5. poetry run uvicorn main:app --reload
  6. 访问 http://localhost:8000/docs

${GREEN}开发工具:${NC}
  poetry run black .           # 格式化代码
  poetry run ruff check .      # 检查代码
  poetry run mypy .            # 类型检查
  poetry run pytest            # 运行测试

${YELLOW}提示:${NC} 使用 ../scripts/code_quality/setup_python_tools.sh 设置更多开发工具

EOF