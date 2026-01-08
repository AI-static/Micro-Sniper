# Middleware & Utilities Module

## Purpose

Generate cross-cutting concerns: authentication, logging, validation, error handling.

## When to Use This Module

- Authentication and authorization
- Logging and monitoring
- Input validation
- Error handling
- Rate limiting
- CORS configuration

## Framework Support

### FastAPI Middleware

**Authentication Middleware**:
```python
from fastapi import Request, HTTPException
from core.security import verify_token

async def auth_middleware(request: Request, call_next):
    # Skip auth for public routes
    if request.url.path in ["/api/docs", "/health"]:
        return await call_next(request)

    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    payload = verify_token(token)
    request.state.user = payload

    return await call_next(request)
```

**Logging Middleware**:
```python
import logging

logger = logging.getLogger(__name__)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Status: {response.status_code}")
    return response
```

### Express.js Middleware

```javascript
// Auth middleware
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

// Error handling middleware
exports.errorHandler = (err, req, res, next) => {
  const status = err.status || 500;
  res.status(status).json({
    error: err.message,
    details: process.env.NODE_ENV === 'development' ? err.stack : undefined
  });
};
```

## Common Middleware Types

### Authentication
- JWT verification
- OAuth2 integration
- API key validation

### Logging
- Request/response logging
- Error logging
- Performance monitoring

### Security
- CORS configuration
- Rate limiting
- CSRF protection
- XSS prevention

### Validation
- Request body validation
- Query parameter validation
- Header validation

## Best Practices

1. **Keep middleware focused** - one responsibility per middleware
2. **Order matters** - auth before logic, logging before response
3. **Handle errors gracefully**
4. **Use async correctly**
5. **Document middleware behavior**

## Examples

- `/modules/middleware-utilities/examples/auth-middleware.md`
- `/modules/middleware-utilities/examples/logging.md`
- `/modules/middleware-utilities/examples/validation.md`

## Templates

- `/assets/templates/python/middleware.py.template`
- `/assets/templates/javascript/middleware.js.template`