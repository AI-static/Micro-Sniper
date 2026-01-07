# Framework Patterns by Layer

Detailed implementation patterns for each framework organized by architectural layer.

## Table of Contents
1. [Route/Controller Layer](#1-routecontroller-layer)
2. [Service Layer](#2-service-layer)
3. [Data Access Layer](#3-data-access-layer)
4. [Model/Schema Layer](#4-modelschema-layer)
5. [Configuration Layer](#5-configuration-layer)
6. [Middleware Layer](#6-middleware-layer)

---

## 1. Route/Controller Layer

### FastAPI

**Basic Route Pattern:**
```python
from fastapi import APIRouter, HTTPException, Depends, status
from schemas.user import UserCreate, UserResponse
from services.user_service import UserService

router = APIRouter(prefix="/api/users", tags=["users"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create(
    data: UserCreate,
    service: UserService = Depends()
):
    return await service.create(data)

@router.get("/{id}", response_model=UserResponse)
async def get_one(id: int, service: UserService = Depends()):
    result = await service.get_one(id)
    if not result:
        raise HTTPException(status_code=404)
    return result

@router.get("/", response_model=list[UserResponse])
async def list(
    skip: int = 0,
    limit: int = 100,
    service: UserService = Depends()
):
    return await service.list(skip, limit)
```

**Dependency Injection:**
```python
from fastapi import Depends
from services.user_service import UserService
from repositories.user_repository import UserRepository
from db import get_db

def get_user_service(db = Depends(get_db)) -> UserService:
    repo = UserRepository(db)
    return UserService(repo)

# Usage in route
@router.post("/")
async def create_user(
    data: UserCreate,
    service: UserService = Depends(get_user_service)
):
    return await service.create_user(data)
```

### Flask (with Blueprint)

**Route Pattern:**
```python
from flask import Blueprint, request, jsonify
from services.user_service import UserService

bp = Blueprint('users', __name__, url_prefix='/api/users')

@bp.route('/', methods=['POST'])
def create():
    data = request.get_json()
    service = UserService()
    try:
        result = service.create(data)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/<int:id>', methods=['GET'])
def get_one(id):
    service = UserService()
    result = service.get_one(id)
    if not result:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(result)
```

### Express.js

**Controller Pattern:**
```javascript
// controllers/userController.js
const userService = require('../services/userService');

exports.create = async (req, res, next) => {
  try {
    const result = await userService.create(req.body);
    res.status(201).json({ success: true, data: result });
  } catch (error) {
    next(error);
  }
};

exports.getOne = async (req, res, next) => {
  try {
    const { id } = req.params;
    const result = await userService.getOne(Number(id));
    if (!result) {
      return res.status(404).json({ success: false, message: 'Not found' });
    }
    res.status(200).json({ success: true, data: result });
  } catch (error) {
    next(error);
  }
};

exports.list = async (req, res, next) => {
  try {
    const { skip = 0, limit = 100 } = req.query;
    const results = await userService.list(Number(skip), Number(limit));
    res.status(200).json({ success: true, data: results });
  } catch (error) {
    next(error);
  }
};
```

**Route Registration:**
```javascript
// routes/userRoutes.js
const express = require('express');
const router = express.Router();
const userController = require('../controllers/userController');
const { authenticate } = require('../middleware/auth');

router.post('/', userController.create);
router.get('/:id', userController.getOne);
router.get('/', userController.list);

module.exports = router;

// app.js
const userRoutes = require('./routes/userRoutes');
app.use('/api/users', userRoutes);
```

### Go Gin

**Handler Pattern:**
```go
// handlers/user_handler.go
package handlers

import (
    "net/http"
    "github.com/gin-gonic/gin"
    "github.com/yourproject/services"
)

type UserHandler struct {
    service *services.UserService
}

func NewUserHandler(service *services.UserService) *UserHandler {
    return &UserHandler{service: service}
}

func (h *UserHandler) Create(c *gin.Context) {
    var req services.UserCreateRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }

    user, err := h.service.Create(req)
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }

    c.JSON(http.StatusCreated, user)
}

func (h *UserHandler) GetOne(c *gin.Context) {
    id, _ := strconv.Atoi(c.Param("id"))
    user, err := h.service.GetOne(id)
    if err != nil {
        c.JSON(http.StatusNotFound, gin.H{"error": "Not found"})
        return
    }

    c.JSON(http.StatusOK, user)
}
```

### Spring Boot (Java)

**Controller Pattern:**
```java
@RestController
@RequestMapping("/api/users")
public class UserController {

    private final UserService userService;

    @Autowired
    public UserController(UserService userService) {
        this.userService = userService;
    }

    @PostMapping
    public ResponseEntity<User> create(@RequestBody UserCreateRequest request) {
        User user = userService.create(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(user);
    }

    @GetMapping("/{id}")
    public ResponseEntity<User> getOne(@PathVariable Long id) {
        return userService.getOne(id)
            .map(user -> ResponseEntity.ok().body(user))
            .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping
    public ResponseEntity<List<User>> list(
        @RequestParam(defaultValue = "0") int skip,
        @RequestParam(defaultValue = "100") int limit
    ) {
        List<User> users = userService.list(skip, limit);
        return ResponseEntity.ok().body(users);
    }
}
```

---

## 2. Service Layer

### FastAPI/Python

**Service Pattern:**
```python
# services/user_service.py
from typing import Optional
from models.user import User
from schemas.user import UserCreate, UserUpdate
from repositories.user_repository import UserRepository

class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create(self, data: UserCreate) -> User:
        # Business rules
        existing = await self.user_repo.find_by_email(data.email)
        if existing:
            raise ValueError("Email exists")

        # Process data
        user_dict = data.dict()
        # Add business logic transformations

        return await self.user_repo.create(user_dict)

    async def get_one(self, id: int) -> Optional[User]:
        return await self.user_repo.find_by_id(id)

    async def update(self, id: int, data: UserUpdate) -> User:
        # Validation
        current = await self.user_repo.find_by_id(id)
        if not current:
            raise ValueError("Not found")

        # Business rules for update
        return await self.user_repo.update(id, data.dict(exclude_unset=True))

    async def delete(self, id: int) -> bool:
        return await self.user_repo.delete(id)

    async def list(self, skip: int, limit: int) -> list[User]:
        return await self.user_repo.list_all(skip, limit)
```

### Node.js/TypeScript

**Service Pattern:**
```typescript
// services/userService.ts
import { UserRepository } from '../repositories/userRepository';
import { UserCreate, UserUpdate } from '../types/user';

export class UserService {
  constructor(private userRepo: UserRepository) {}

  async create(data: UserCreate) {
    // Business rule: Check email uniqueness
    const existing = await this.userRepo.findByEmail(data.email);
    if (existing) {
      throw new Error('Email already exists');
    }

    // Business logic transformations
    const processedData = {
      ...data,
      // Add transformations
    };

    return await this.userRepo.create(processedData);
  }

  async getOne(id: number) {
    return await this.userRepo.findById(id);
  }

  async update(id: number, data: UserUpdate) {
    const current = await this.userRepo.findById(id);
    if (!current) {
      throw new Error('User not found');
    }

    // Business rule: Email uniqueness
    if (data.email && data.email !== current.email) {
      const existing = await this.userRepo.findByEmail(data.email);
      if (existing) {
        throw new Error('Email already exists');
      }
    }

    return await this.userRepo.update(id, data);
  }

  async delete(id: number) {
    return await this.userRepo.delete(id);
  }

  async list(skip: number, limit: number) {
    return await this.userRepo.list(skip, limit);
  }
}
```

### Go

**Service Pattern:**
```go
package services

type UserService struct {
    repo *repositories.UserRepository
}

func NewUserService(repo *repositories.UserRepository) *UserService {
    return &UserService{repo: repo}
}

func (s *UserService) Create(req UserCreateRequest) (*User, error) {
    // Business rules
    existing, _ := s.repo.FindByEmail(req.Email)
    if existing != nil {
        return nil, errors.New("email exists")
    }

    user := &User{
        Email:    req.Email,
        Username: req.Username,
    }

    return s.repo.Create(user)
}

func (s *UserService) GetOne(id int) (*User, error) {
    return s.repo.FindByID(id)
}
```

---

## 3. Data Access Layer

### SQLAlchemy (Async)

**Repository Pattern:**
```python
# repositories/user_repository.py
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_id(self, id: int) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.id == id)
        )
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> User:
        user = User(**data)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, id: int, data: dict) -> User:
        user = await this.find_by_id(id)
        for key, value in data.items():
            setattr(user, key, value)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete(self, id: int) -> bool:
        user = await this.find_by_id(id)
        await self.db.delete(user)
        await self.db.commit()
        return True

    async def list_all(self, skip: int, limit: int) -> List[User]:
        result = await self.db.execute(
            select(User).offset(skip).limit(limit)
        )
        return result.scalars().all()
```

### Prisma (Node.js)

**Repository Pattern:**
```javascript
// repositories/userRepository.js
const prisma = require('../lib/prisma');

class UserRepository {
  async findById(id) {
    return await prisma.user.findUnique({ where: { id } });
  }

  async findByEmail(email) {
    return await prisma.user.findUnique({ where: { email } });
  }

  async create(data) {
    return await prisma.user.create({ data });
  }

  async update(id, data) {
    return await prisma.user.update({
      where: { id },
      data
    });
  }

  async delete(id) {
    return await prisma.user.delete({ where: { id } });
  }

  async list(skip, take) {
    return await prisma.user.findMany({ skip, take });
  }

  async count() {
    return await prisma.user.count();
  }
}

module.exports = new UserRepository();
```

### GORM (Go)

**Repository Pattern:**
```go
package repositories

import (
    "gorm.io/gorm"
)

type UserRepository struct {
    db *gorm.DB
}

func NewUserRepository(db *gorm.DB) *UserRepository {
    return &UserRepository{db: db}
}

func (r *UserRepository) FindByID(id int) (*User, error) {
    var user User
    err := r.db.First(&user, id).Error
    if err != nil {
        return nil, err
    }
    return &user, nil
}

func (r *UserRepository) FindByEmail(email string) (*User, error) {
    var user User
    err := r.db.Where("email = ?", email).First(&user).Error
    if err != nil {
        return nil, err
    }
    return &user, nil
}

func (r *UserRepository) Create(user *User) (*User, error) {
    err := r.db.Create(user).Error
    return user, err
}

func (r *UserRepository) Update(user *User) (*User, error) {
    err := r.db.Save(user).Error
    return user, err
}

func (r *UserRepository) Delete(id int) error {
    return r.db.Delete(&User{}, id).Error
}

func (r *UserRepository) List(skip, limit int) ([]User, error) {
    var users []User
    err := r.db.Offset(skip).Limit(limit).Find(&users).Error
    return users, err
}
```

### Spring Data JPA

**Repository Pattern:**
```java
@Repository
public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByEmail(String email);

    boolean existsByEmail(String email);

    @Query("SELECT u FROM User u WHERE u.email = :email")
    Optional<User> findByEmailWithQuery(@Param("email") String email);

    List<User> findByIdIn(List<Long> ids);
}
```

---

## 4. Model/Schema Layer

### Pydantic Schemas

**Request/Response Schemas:**
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
            raise ValueError('Password too short')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
```

### SQLAlchemy Models

**Database Model:**
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
```

### TypeScript Interfaces

**Type Definitions:**
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

export interface UserResponse {
  success: boolean;
  data?: User;
  message?: string;
}
```

---

## 5. Configuration Layer

### Python (Pydantic Settings)

```python
# core/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "MyApp"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str

    # Security
    SECRET_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()
```

### Node.js

```javascript
// config/index.js
require('dotenv').config();

const config = {
  app: {
    name: process.env.APP_NAME || 'MyApp',
    port: parseInt(process.env.PORT || '3000'),
    env: process.env.NODE_ENV || 'development'
  },

  database: {
    url: process.env.DATABASE_URL
  },

  security: {
    secretKey: process.env.SECRET_KEY
  }
};

module.exports = config;
```

---

## 6. Middleware Layer

### FastAPI Middleware

```python
# middleware/auth.py
from fastapi import Request, HTTPException

async def auth_middleware(request: Request, call_next):
    if request.url.path in ["/api/docs", "/api/health"]:
        return await call_next(request)

    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=401)

    # Validate token
    payload = verify_token(token)
    request.state.user = payload

    return await call_next(request)
```

### Express.js Middleware

```javascript
// middleware/auth.js
exports.authenticate = (req, res, next) => {
  const token = req.headers.authorization;

  if (!token) {
    return res.status(401).json({ message: 'Unauthorized' });
  }

  try {
    const decoded = jwt.verify(token, process.env.SECRET_KEY);
    req.user = decoded;
    next();
  } catch (error) {
    res.status(401).json({ message: 'Invalid token' });
  }
};
```

### Go Gin Middleware

```go
func AuthMiddleware() gin.HandlerFunc {
    return func(c *gin.Context) {
        token := c.GetHeader("Authorization")

        if token == "" {
            c.JSON(401, gin.H{"error": "unauthorized"})
            c.Abort()
            return
        }

        // Validate token
        claims, err := validateToken(token)
        if err != nil {
            c.JSON(401, gin.H{"error": "invalid token"})
            c.Abort()
            return
        }

        c.Set("user", claims)
        c.Next()
    }
}
```