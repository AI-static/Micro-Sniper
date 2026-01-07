---
name: code-generator
description: Generate clean, production-ready code organized by architectural layers. Use this skill when users need to generate code for specific layers such as routes/controllers, services, data access, models/schemas, configuration, or middleware. This skill provides focused patterns for each layer without mixing concerns.
---

# Code Generator - Layer by Layer

## Overview

Generate clean, maintainable code following layered architecture principles. Each layer has a single responsibility and clear boundaries. This skill focuses on generating code for specific layers without mixing concerns.

## When to Use This Skill

Activate this skill when:
- Creating routes, controllers, or API endpoints
- Implementing business logic in service layer
- Writing database queries or data access code
- Defining models, schemas, or DTOs
- Setting up configuration files
- Creating middleware or interceptors
- Building validators or formatters

## Layered Architecture

```
┌─────────────────────────────────────┐
│   Route/Controller Layer (API)      │  ← Handle HTTP requests/responses
├─────────────────────────────────────┤
│   Service Layer (Business Logic)    │  ← Implement business rules
├─────────────────────────────────────┤
│   Data Access Layer (Repository)    │  ← Database operations
├─────────────────────────────────────┤
│   Model/Schema Layer (Data Model)   │  ← Data structures
├─────────────────────────────────────┤
│   Configuration Layer               │  ← App configuration
├─────────────────────────────────────┤
│   Middleware Layer                  │  ← Cross-cutting concerns
└─────────────────────────────────────┘
```

## 1. Route/Controller Layer

### Responsibility
- Handle HTTP requests and responses
- Validate request data
- Call service layer
- Return appropriate status codes
- Format responses

### FastAPI Route Example
```python
# routers/users.py
from fastapi import APIRouter, HTTPException, status, Depends
from schemas.user import UserCreate, UserResponse
from services.user_service import UserService
from core.deps import get_db

router = APIRouter(prefix="/api/users", tags=["users"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    user_service: UserService = Depends(UserService)
):
    """Create a new user."""
    try:
        user = await user_service.create_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    user_service: UserService = Depends(UserService)
):
    """Get user by ID."""
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    user_service: UserService = Depends(UserService)
):
    """List all users with pagination."""
    return await user_service.list_users(skip, limit)
```

### Express.js Controller Example
```javascript
// controllers/userController.js
const userService = require('../services/userService');

exports.createUser = async (req, res, next) => {
  try {
    const { email, username, password } = req.body;

    const user = await userService.createUser({ email, username, password });

    return res.status(201).json({
      success: true,
      data: user
    });
  } catch (error) {
    if (error.message === 'Email already exists') {
      return res.status(400).json({ success: false, message: error.message });
    }
    next(error);
  }
};

exports.getUser = async (req, res, next) => {
  try {
    const { id } = req.params;
    const user = await userService.getUser(Number(id));

    if (!user) {
      return res.status(404).json({ success: false, message: 'User not found' });
    }

    return res.status(200).json({ success: true, data: user });
  } catch (error) {
    next(error);
  }
};
```

### Route Pattern Principles
- **Thin controllers** - Only handle HTTP concerns
- **No business logic** - Delegate to services
- **Validate input** - Use schema validation
- **Handle errors** - Return appropriate status codes
- **Format responses** - Consistent response structure

## 2. Service Layer

### Responsibility
- Implement business logic
- Coordinate between multiple repositories
- Apply business rules and validations
- Handle transactions
- No HTTP or database specifics

### UserService Example
```python
# services/user_service.py
from typing import List, Optional
from models.user import User
from schemas.user import UserCreate, UserUpdate
from repositories.user_repository import UserRepository
from core.security import hash_password

class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create_user(self, user_data: UserCreate) -> User:
        """Create user with business logic validations."""
        # Business rule: Check if email exists
        existing = await self.user_repo.find_by_email(user_data.email)
        if existing:
            raise ValueError("Email already exists")

        # Business rule: Hash password
        hashed_password = hash_password(user_data.password)

        # Create user
        user = await self.user_repo.create({
            "email": user_data.email,
            "username": user_data.username,
            "password": hashed_password
        })

        return user

    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return await self.user_repo.find_by_id(user_id)

    async def update_user(self, user_id: int, user_data: UserUpdate) -> User:
        """Update user with business validations."""
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        # Business rule: Email uniqueness check
        if user_data.email and user_data.email != user.email:
            existing = await self.user_repo.find_by_email(user_data.email)
            if existing:
                raise ValueError("Email already exists")

        return await self.user_repo.update(user_id, user_data.dict())

    async def delete_user(self, user_id: int) -> bool:
        """Delete user with business validations."""
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        return await self.user_repo.delete(user_id)
```

### Service Layer Principles
- **Business logic only** - No HTTP or database concerns
- **Reusable** - Can be called from multiple controllers
- **Testable** - Easy to unit test
- **Transaction management** - Coordinate multiple operations
- **Domain-focused** - Use domain language

## 3. Data Access Layer (Repository)

### Responsibility
- Execute database queries
- Handle connection management
- Map database records to models
- No business logic
- Database-agnostic interface

### Repository Example (SQLAlchemy)
```python
# repositories/user_repository.py
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_id(self, user_id: int) -> Optional[User]:
        """Find user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create(self, user_data: dict) -> User:
        """Create new user."""
        user = User(**user_data)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user_id: int, user_data: dict) -> User:
        """Update user."""
        user = await self.find_by_id(user_id)
        for key, value in user_data.items():
            setattr(user, key, value)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete(self, user_id: int) -> bool:
        """Delete user."""
        user = await self.find_by_id(user_id)
        await self.db.delete(user)
        await self.db.commit()
        return True

    async def list_all(self, skip: int = 0, limit: int = 100) -> List[User]:
        """List all users with pagination."""
        result = await self.db.execute(
            select(User).offset(skip).limit(limit)
        )
        return result.scalars().all()
```

### Repository with Prisma (Node.js)
```javascript
// repositories/userRepository.js
const prisma = require('../lib/prisma');

class UserRepository {
  async findById(id) {
    return await prisma.user.findUnique({
      where: { id }
    });
  }

  async findByEmail(email) {
    return await prisma.user.findUnique({
      where: { email }
    });
  }

  async create(data) {
    return await prisma.user.create({
      data
    });
  }

  async update(id, data) {
    return await prisma.user.update({
      where: { id },
      data
    });
  }

  async delete(id) {
    return await prisma.user.delete({
      where: { id }
    });
  }

  async list(skip = 0, take = 100) {
    return await prisma.user.findMany({
      skip,
      take
    });
  }
}

module.exports = new UserRepository();
```

### Repository Principles
- **Single responsibility** - Only data access
- **Interface-based** - Abstract database implementation
- **No business logic** - Pure CRUD operations
- **Connection management** - Handle sessions/connections
- **Transaction support** - Begin/commit/rollback

## 4. Model/Schema Layer

### Responsibility
- Define data structures
- Validate data formats
- Provide type safety
- Document data shapes
- No business logic

### Pydantic Schema Example
```python
# schemas/user.py
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str
```

### SQLAlchemy Model Example
```python
# models/user.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"
```

### TypeScript Interface Example
```typescript
// types/user.ts
export interface User {
  id: number;
  email: string;
  username: string;
  created_at: Date;
  updated_at: Date;
}

export interface UserCreate {
  email: string;
  username: string;
  password: string;
}

export interface UserUpdate {
  email?: string;
  username?: string;
  password?: string;
}

export interface UserLogin {
  email: string;
  password: string;
}
```

### Schema Principles
- **Validation only** - No business logic
- **Type safety** - Enforce data types
- **Documentation** - Self-documenting structure
- **Immutable** - Use immutability where possible
- **Separate concerns** - Input vs Output schemas

## 5. Configuration Layer

### Responsibility
- Load and validate configuration
- Provide configuration to application
- Handle environment-specific settings
- No application logic

### Config Example (Python)
```python
# core/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Micro-Sniper"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 10

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # External Services
    REDIS_URL: Optional[str] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

### Config Example (Node.js)
```javascript
// config/index.js
require('dotenv').config();

const config = {
  app: {
    name: process.env.APP_NAME || 'Micro-Sniper',
    version: process.env.APP_VERSION || '1.0.0',
    port: parseInt(process.env.PORT || '3000'),
    env: process.env.NODE_ENV || 'development'
  },

  database: {
    url: process.env.DATABASE_URL,
    poolSize: parseInt(process.env.DB_POOL_SIZE || '10')
  },

  security: {
    secretKey: process.env.SECRET_KEY,
    algorithm: 'HS256',
    tokenExpiration: parseInt(process.env.TOKEN_EXPIRATION || '3600')
  },

  redis: {
    url: process.env.REDIS_URL
  }
};

// Validate required config
const requiredEnvVars = ['DATABASE_URL', 'SECRET_KEY'];
const missing = requiredEnvVars.filter(key => !process.env[key]);

if (missing.length > 0) {
  throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
}

module.exports = config;
```

### Config Principles
- **Centralized** - Single source of truth
- **Validated** - Validate on startup
- **Environment-based** - Support multiple environments
- **Type-safe** - Use typed configuration
- **Secret management** - Never hardcode secrets

## 6. Middleware Layer

### Responsibility
- Cross-cutting concerns
- Request/response interception
- Authentication/authorization
- Logging
- Error handling

### FastAPI Middleware Example
```python
# middleware/auth.py
from fastapi import Request, HTTPException, status
from core.security import verify_token

async def auth_middleware(request: Request, call_next):
    """Authentication middleware."""
    # Skip auth for public routes
    if request.url.path in ["/api/docs", "/api/health", "/api/auth/login"]:
        return await call_next(request)

    # Get token from header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = auth_header.split(" ")[1]

    # Verify token
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Add user to request state
    request.state.user_id = payload["user_id"]

    return await call_next(request)
```

### Express.js Middleware Example
```javascript
// middleware/auth.js
const jwt = require('jsonwebtoken');

exports.authenticate = (req, res, next) => {
  // Skip auth for public routes
  if (req.path.startsWith('/api/docs') || req.path === '/api/health') {
    return next();
  }

  // Get token from header
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ message: 'Missing token' });
  }

  const token = authHeader.split(' ')[1];

  try {
    // Verify token
    const decoded = jwt.verify(token, process.env.SECRET_KEY);
    req.user = decoded;
    next();
  } catch (error) {
    return res.status(401).json({ message: 'Invalid token' });
  }
};

exports.requireRole = (role) => {
  return (req, res, next) => {
    if (req.user.role !== role) {
      return res.status(403).json({ message: 'Forbidden' });
    }
    next();
  };
};
```

### Middleware Principles
- **Single purpose** - One middleware does one thing
- **Chainable** - Easy to compose
- **Order matters** - Correct execution order
- **No side effects** - Unless intentional
- **Error handling** - Handle errors gracefully

## Code Generation Workflow

1. **Identify the Layer**
   - Which layer needs code?
   - What are the responsibilities?
   - What are the dependencies?

2. **Understand Requirements**
   - Language and framework
   - Data structures needed
   - Business rules (for service layer)

3. **Generate Code**
   - Follow layer-specific patterns
   - Maintain separation of concerns
   - Use appropriate abstractions

4. **Ensure Quality**
   - Single responsibility
   - No mixed concerns
   - Proper error handling
   - Clean interfaces

## When to Ask for Clarification

Ask the user when:
- The target layer is not specified
- Framework or language is unclear
- Dependencies between layers are complex
- Business rules are ambiguous
- Data structures are not defined

## Resources

### references/frameworks.md
Detailed implementation patterns for each framework across all layers:
- FastAPI patterns by layer
- Flask patterns by layer
- Express.js patterns by layer
- React patterns by layer
- Go/Gin patterns by layer
- Spring Boot patterns by layer

Load this reference when framework-specific implementation details are needed.