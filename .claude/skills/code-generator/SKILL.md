---
name: code-generator
description: Generate production-ready code organized by functional modules. Includes API development, database operations, configuration, middleware, and project scaffolding with dependency management (Poetry, npm, pip) and code quality tools (black, ruff, mypy, eslint, prettier). Use this skill when starting new projects, adding features, or setting up development tools.
---

# Code Generator - Module-Based Development

## Overview

Generate clean, maintainable code following functional module organization. Each module contains all necessary components for a specific feature area, making it easier to develop, test, and maintain features independently.

This skill provides:
- **5 Functional Modules**: Organized by development task
- **Utility Scripts**: Dependency management and code quality tools
- **Code Templates**: Quick-start templates for common patterns
- **Best Practices**: Security, performance, and maintainability guidelines

## When to Use This Skill

Activate this skill when:
- Starting a new project (FastAPI, Express, Sanic, etc.)
- Adding API endpoints or features
- Setting up database models and migrations
- Configuring application settings
- Implementing authentication, logging, or validation
- Setting up code quality tools (black, ruff, mypy, eslint)
- Managing dependencies (Poetry, npm, pip)

## Functional Modules

### 1. API Development Module

**Location**: `/modules/api-development/`

**Purpose**: Generate API endpoints, routes, and controllers

**When to use**:
- Creating RESTful endpoints
- Building GraphQL resolvers
- Implementing request validation
- Formatting API responses

**Frameworks**: FastAPI, Express.js, Sanic, Go Gin, Spring Boot

**Examples**:
- `/modules/api-development/examples/fastapi-routes.md`
- `/modules/api-development/examples/express-controllers.md`
- `/modules/api-development/examples/sanic-handlers.md`

### 2. Database Operations Module

**Location**: `/modules/database-operations/`

**Purpose**: Generate database models, repositories, and migrations

**When to use**:
- Defining data models
- Creating database queries
- Writing migrations
- Managing relationships
- Transaction management

**ORMs**: SQLAlchemy, Tortoise-ORM, Prisma, GORM, TypeORM

**Examples**:
- `/modules/database-operations/examples/sqlalchemy-models.md`
- `/modules/database-operations/examples/prisma-models.md`
- `/modules/database-operations/examples/tortoise-models.md`

**Templates**:
- `/assets/templates/python/model.py.template`
- `/assets/templates/python/repository.py.template`

### 3. Configuration Management Module

**Location**: `/modules/configuration-management/`

**Purpose**: Generate application configuration and settings

**When to use**:
- Loading environment variables
- Validating configuration
- Type-safe settings
- Environment-specific configs
- Secret management

**Tools**: Pydantic Settings, dotenv, Spring Properties

**Examples**:
- `/modules/configuration-management/examples/pydantic-settings.md`
- `/modules/configuration-management/examples/dotenv-config.md`

**Templates**:
- `/assets/templates/python/config.py.template`
- `/assets/configs/pyproject.toml.template`

### 4. Middleware & Utilities Module

**Location**: `/modules/middleware-utilities/`

**Purpose**: Generate cross-cutting concerns

**When to use**:
- Authentication and authorization
- Logging and monitoring
- Input validation
- Error handling
- Rate limiting
- CORS configuration

**Frameworks**: FastAPI Middleware, Express.js Middleware, Sanic Middleware

**Examples**:
- `/modules/middleware-utilities/examples/auth-middleware.md`
- `/modules/middleware-utilities/examples/logging.md`
- `/modules/middleware-utilities/examples/validation.md`

**Templates**:
- `/assets/templates/python/middleware.py.template`

### 5. Project Scaffolding Module

**Location**: `/modules/project-scaffolding/`

**Purpose**: Generate complete project boilerplate

**When to use**:
- Starting a new project
- Setting up project structure
- Initializing dependencies
- Configuring development tools

**Supported Frameworks**:
- Sanic (async Python) - Micro-Sniper 的选择
- Express.js (Node.js)
- FastAPI (modern Python async)

**Scripts**:
- `/scripts/scaffolding/create_sanic_project.sh` ⭐ Sanic 项目生成
- `/scripts/scaffolding/create_fastapi_project.sh`
- `/scripts/scaffolding/create_express_project.sh`

**Examples**:
- `/modules/project-scaffolding/examples/sanic-starter.md`

## Scripts & Tools

### Dependency Management

**Poetry Helper** (Python)
```bash
# Show all Poetry commands
./scripts/setup_dependencies/poetry_helper.sh

# Common commands:
poetry init                    # Initialize new project
poetry add fastapi             # Add dependency
poetry install                 # Install dependencies
poetry shell                   # Activate virtual environment
poetry run python main.py      # Run script
poetry export -f requirements.txt  # Export to pip
```

**npm Helper** (JavaScript/Node.js)
```bash
# Show all npm commands
./scripts/setup_dependencies/npm_helper.sh

# Common commands:
npm init -y                    # Create package.json
npm install express            # Add dependency
npm run dev                    # Run development script
npm audit                      # Security audit
```

**pip Helper** (Python)
```bash
# Show all pip commands
./scripts/setup_dependencies/pip_helper.sh

# Common commands:
pip install fastapi            # Install package
pip freeze > requirements.txt  # Export dependencies
python -m venv .venv           # Create venv
source .venv/bin/activate      # Activate venv
```

### Code Quality Tools

**Python Tools Setup**
```bash
# Setup black, ruff, mypy, pre-commit
./scripts/code_quality/setup_python_tools.sh

# Usage:
black .                        # Format code
ruff check .                   # Lint code
ruff check . --fix             # Fix lint issues
mypy .                         # Type check
pre-commit run --all-files     # Run all checks
```

**JavaScript Tools Setup**
```bash
# Setup eslint, prettier
./scripts/code_quality/setup_js_tools.sh

# Usage:
npm run lint                   # Lint code
npm run format                 # Format code
npm run check                  # Run all checks
```

**Pre-commit Hooks**
```bash
# Setup pre-commit for Python and JS
./scripts/code_quality/setup_precommit.sh

# Hooks run automatically on:
# - black (Python formatting)
# - ruff (Python linting)
# - mypy (Python type checking)
# - eslint (JS linting)
# - prettier (JS formatting)
```

### Project Scaffolding

**Sanic Project** ⭐
```bash
./scripts/scaffolding/create_sanic_project.sh myapi

# Creates:
# - Project structure (api/, services/, models/, tests/)
# - pyproject.toml with dependencies
# - app.py with Sanic application
# - Tortoise-ORM configuration
# - Redis integration
# - Aerich migrations setup
# - Example routes
# - Configuration files
# - .env.example
# - README.md
```

**FastAPI Project**
```bash
./scripts/scaffolding/create_fastapi_project.sh myapi

# Creates:
# - Project structure (api/, services/, models/, tests/)
# - pyproject.toml with dependencies
# - main.py with FastAPI app
# - Example routes
# - Configuration files
# - .env.example
# - README.md
```

**Express.js Project**
```bash
./scripts/scaffolding/create_express_project.sh myapp

# Creates:
# - Project structure (routes/, controllers/, middleware/)
# - package.json with dependencies
# - app.js with Express setup
# - Example controllers
# - Configuration files
```

## Code Templates

Quick-start templates are available in `/assets/templates/`:

**Python Templates**:
- `route.py.template` - FastAPI route template
- `service.py.template` - Service layer template
- `model.py.template` - SQLAlchemy model template
- `repository.py.template` - Repository pattern template
- `config.py.template` - Pydantic settings template

**JavaScript Templates**:
- `controller.js.template` - Express controller template
- `service.js.template` - Service layer template
- `middleware.js.template` - Express middleware template

**Go Templates**:
- `handler.go.template` - Gin handler template

**Configuration Templates**:
- `pyproject.toml.template` - Poetry project template
- `package.json.template` - npm project template
- `.eslintrc.json.template` - ESLint configuration
- `.prettierrc.template` - Prettier configuration

## Quality Checklists

Use these checklists to ensure code quality:

**API Development**: `/assets/checklists/api_checklist.md`
- Design (RESTful conventions, versioning)
- Security (auth, validation, rate limiting)
- Documentation (OpenAPI, examples)
- Testing (unit, integration)

**Database Operations**: `/assets/checklists/database_checklist.md`
- Design (normalization, indexes)
- Performance (query optimization)
- Migrations (versioning, rollback)
- Security (SQL injection prevention)

**General**: `/assets/checklists/security_checklist.md`
- Input validation
- Authentication/authorization
- Secrets management
- Dependency vulnerabilities

## Workflow

### Starting a New Project

1. **Choose Framework**: Sanic (推荐), Express, FastAPI
2. **Generate Scaffold**: Use scaffolding scripts
3. **Setup Dependencies**: Install with Poetry/npm
4. **Configure Code Quality**: Run setup scripts
5. **Start Developing**: Use module-specific patterns

### Adding a Feature

1. **Identify Module**: API, Database, Config, or Middleware?
2. **Read Module Guide**: Check `modules/<module>/skill.md`
3. **Review Examples**: Look at `modules/<module>/examples/`
4. **Use Templates**: Adapt templates from `assets/templates/`
5. **Follow Checklist**: Ensure quality with checklists

### Setting Up Code Quality

1. **Python**: Run `setup_python_tools.sh`
2. **JavaScript**: Run `setup_js_tools.sh`
3. **Both**: Run `setup_precommit.sh`
4. **Commit**: Hooks will check code automatically

## Best Practices

### Code Organization
- **Feature Modules**: Group related code (routes, services, models)
- **Shared Code**: Keep common utilities in shared/
- **Clear Boundaries**: Each module has single responsibility

### Security
- **Never Trust Input**: Validate at entry points
- **Parameterized Queries**: Prevent SQL injection
- **Hash Sensitive Data**: Passwords, tokens
- **Use HTTPS**: Never HTTP
- **Rate Limiting**: Protect against abuse

### Performance
- **Database Indexes**: Add indexes on foreign keys
- **Async I/O**: Use async/await for I/O operations
- **Caching**: Cache expensive operations
- **Batch Operations**: Reduce database round trips
- **Monitor**: Track performance metrics

### Testing
- **Unit Tests**: Test business logic
- **Integration Tests**: Test component interactions
- **Mock External Dependencies**: Make tests reliable
- **High Coverage**: Aim for >80%

## When to Ask for Clarification

Ask the user when:
- The target module is not specified
- Framework or language is unclear
- Dependencies between modules are complex
- Business rules are ambiguous
- Data structures are not defined
- Security requirements are unclear

## Reference Documentation

Detailed reference materials available in `/references/`:

- **frameworks.md**: Framework-specific patterns and examples
- **best-practices.md**: General coding best practices
- **patterns.md**: Design patterns with code examples
- **migrations/layer-to-module.md**: Migrating from layer to module organization

## Quick Examples

### FastAPI Route
```python
from fastapi import APIRouter, Depends
from schemas.user import UserCreate, UserResponse
from services.user_service import UserService

router = APIRouter(prefix="/api/users", tags=["users"])

@router.post("/", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    service: UserService = Depends()
):
    return await service.create(data)
```

### SQLAlchemy Model
```python
from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
```

### Pydantic Settings
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    DEBUG: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
```

## Module Organization Pattern

Instead of organizing by layers (routes/, services/, models/), organize by features:

```
features/
├── users/              # Complete user feature
│   ├── routes.py       # API endpoints
│   ├── service.py      # Business logic
│   ├── repository.py   # Data access
│   └── models.py       # Data models
└── posts/              # Complete post feature
    ├── routes.py
    ├── service.py
    ├── repository.py
    └── models.py

shared/
├── middleware/         # Reusable middleware
├── utils/              # Common utilities
└── config/             # Shared configuration
```

This approach:
- **Improves Cohesion**: Related code stays together
- **Eases Navigation**: Find all feature code in one place
- **Supports Scaling**: Extract features to microservices later
- **Clarifies Boundaries**: Feature dependencies are explicit
