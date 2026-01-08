# API Development Module

## Purpose

Generate API endpoints, routes, and controllers for web applications.

## When to Use This Module

Use this module when:
- Creating RESTful endpoints
- Building GraphQL resolvers
- Implementing request validation
- Formatting API responses
- Setting up API versioning
- Handling errors in APIs

## Core Responsibilities

- **Request Handling**: Parse and validate incoming requests
- **Response Formatting**: Structure consistent responses
- **Status Codes**: Return appropriate HTTP status codes
- **Error Handling**: Handle and format errors properly
- **Validation**: Validate request data
- **Authentication**: Integrate auth middleware

## Framework Support

### FastAPI (Python)

**Quick Example**:
```python
from fastapi import APIRouter, Depends, HTTPException
from schemas.user import UserCreate, UserResponse
from services.user_service import UserService

router = APIRouter(prefix="/api/users", tags=["users"])

@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    service: UserService = Depends()
):
    """Create a new user."""
    try:
        return await service.create(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Key Patterns**:
- Use `APIRouter` for organizing routes
- Leverage dependency injection with `Depends()`
- Return Pydantic models for validation
- Use async/await throughout

### Express.js (Node.js)

**Quick Example**:
```javascript
const express = require('express');
const router = express.Router();
const userService = require('../services/userService');

router.post('/', async (req, res, next) => {
  try {
    const user = await userService.create(req.body);
    res.status(201).json({ success: true, data: user });
  } catch (error) {
    next(error);
  }
});
```

**Key Patterns**:
- Use `express.Router()` for modular routes
- Async/await for database operations
- Error handling with next()
- Separate controllers from routes

### Sanic (Python)

**Quick Example**:
```python
from sanic import response, Blueprint
from services.user_service import UserService

bp = Blueprint('users', url_prefix='/users')

@bp.post('/')
async def create_user(request):
    data = request.json
    user = await UserService.create(data)
    return response.json(user, status=201)
```

**Key Patterns**:
- Use Blueprints for organization
- Request handlers are async by default
- Direct response.json() for JSON responses

## RESTful API Design

### HTTP Methods

| Method | Operation | Example | Idempotent |
|--------|-----------|---------|------------|
| GET | Read | GET /api/users | ✅ |
| POST | Create | POST /api/users | ❌ |
| PUT | Update | PUT /api/users/1 | ✅ |
| PATCH | Partial Update | PATCH /api/users/1 | ❌ |
| DELETE | Delete | DELETE /api/users/1 | ✅ |

### Status Codes

**Success Codes**:
- `200 OK` - Successful GET, PUT, PATCH
- `201 Created` - Successful POST
- `204 No Content` - Successful DELETE

**Client Error Codes**:
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Authenticated but not authorized
- `404 Not Found` - Resource doesn't exist
- `409 Conflict` - Resource already exists
- `422 Unprocessable Entity` - Validation error

**Server Error Codes**:
- `500 Internal Server Error` - Unexpected error
- `503 Service Unavailable` - Service down

### URL Design

**Good URLs**:
```
GET    /api/users              # List users
GET    /api/users/123          # Get specific user
POST   /api/users              # Create user
PUT    /api/users/123          # Update user
DELETE /api/users/123          # Delete user
GET    /api/users/123/posts    # Get user's posts
```

**Bad URLs**:
```
GET    /api/getUsers           # Don't use verbs
GET    /api/user               # Use plural
POST   /api/createUser         # Don't include action
GET    /api/users/1            # Don't mix types
```

## Request Validation

### Pydantic (FastAPI)

```python
from pydantic import BaseModel, EmailStr, validator

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password too short')
        return v

    @validator('username')
    def validate_username(cls, v):
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        return v
```

### Joi (Express.js)

```javascript
const Joi = require('joi');

const userSchema = Joi.object({
  email: Joi.string().email().required(),
  username: Joi.string().alphanum().min(3).max(30).required(),
  password: Joi.string().min(8).required()
});

router.post('/', async (req, res, next) => {
  const { error, value } = userSchema.validate(req.body);
  if (error) {
    return res.status(400).json({ error: error.details });
  }
  // Process validated data
});
```

## Response Formatting

### Consistent Structure

```python
# Success response
{
    "success": true,
    "data": { ... },
    "message": "Operation successful"
}

# Error response
{
    "success": false,
    "error": "Error message",
    "details": { ... }
}
```

### Pagination

```python
@router.get("/users")
async def list_users(
    skip: int = 0,
    limit: int = 100,
    service: UserService = Depends()
):
    total = await service.count()
    users = await service.list(skip, limit)

    return {
        "data": users,
        "pagination": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_next": skip + limit < total
        }
    }
```

## Error Handling

### FastAPI Exception Handlers

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

async def custom_exception_handler(request: Request, exc: CustomException):
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.message,
            "details": exc.details
        }
    )

app.add_exception_handler(CustomException, custom_exception_handler)
```

### Express.js Error Middleware

```javascript
function errorHandler(err, req, res, next) {
  const status = err.status || 500;
  res.status(status).json({
    error: err.message,
    details: process.env.DEBUG ? err.stack : undefined
  });
}

app.use(errorHandler);
```

## API Versioning

### URL Versioning

```
/api/v1/users
/api/v2/users
```

### Header Versioning

```
GET /api/users
Accept: application/vnd.myapi.v2+json
```

## Examples

See detailed examples in:
- `/modules/api-development/examples/fastapi-routes.md`
- `/modules/api-development/examples/express-controllers.md`
- `/modules/api-development/examples/sanic-handlers.md`

## Templates

Quick-start templates:
- `/assets/templates/python/route.py.template`
- `/assets/templates/javascript/controller.js.template`

## Checklist

Before deploying your API, ensure:
- [ ] All endpoints documented (OpenAPI/Swagger)
- [ ] Input validation on all endpoints
- [ ] Proper error handling
- [ ] Authentication implemented
- [ ] Rate limiting configured
- [ ] CORS configured correctly
- [ ] Status codes are appropriate
- [ ] Pagination for list endpoints
- [ ] Tests written for critical paths
- [ ] API versioning strategy defined