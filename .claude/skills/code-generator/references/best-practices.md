# Code Generation Best Practices

## General Principles

### 1. Separation of Concerns

**Do**:
- Keep routes thin (HTTP handling only)
- Business logic in services
- Data access in repositories
- Models for data structures only

**Don't**:
- Put database queries in routes
- Mix business logic with HTTP handling
- Add validation to models

### 2. Error Handling

**Best Practices**:
- Use appropriate HTTP status codes
- Provide meaningful error messages
- Log errors with context
- Don't expose sensitive info
- Handle exceptions at appropriate layers

**Status Code Guide**:
```python
200 OK              # Success (GET, PUT, PATCH)
201 Created         # Success (POST)
204 No Content      # Success (DELETE)
400 Bad Request     # Client error
401 Unauthorized    # Not authenticated
403 Forbidden       # Not authorized
404 Not Found       # Resource not found
409 Conflict        # Resource exists
422 Unprocessable  # Validation error
500 Server Error    # Unexpected error
```

### 3. Validation

**Always Validate**:
- At input (route/controller)
- Use schema validation (Pydantic/Joi)
- Sanitize user input
- Validate business rules in services

**Example**:
```python
# Route layer - structural validation
@router.post("/users")
async def create_user(data: UserCreate):
    return await service.create(data)

# Service layer - business validation
class UserService:
    async def create(self, data: UserCreate):
        existing = await self.repo.find_by_email(data.email)
        if existing:
            raise ValueError("Email already exists")
        # Business logic here
```

### 4. Security

**Critical Security Practices**:

✅ **Always Do**:
- Validate and sanitize input
- Use parameterized queries
- Hash sensitive data (passwords, tokens)
- Implement rate limiting
- Use HTTPS only
- Keep dependencies updated
- Implement CORS correctly

❌ **Never Do**:
- Trust client input
- Concatenate SQL queries
- Store passwords in plain text
- Expose stack traces to clients
- Hardcode secrets
- Ignore security warnings

**SQL Injection Prevention**:
```python
# ❌ BAD - SQL injection vulnerable
query = f"SELECT * FROM users WHERE id = {user_id}"

# ✅ GOOD - parameterized query
query = "SELECT * FROM users WHERE id = :user_id"
result = db.execute(query, {"user_id": user_id})
```

**XSS Prevention**:
```python
# ❌ BAD - renders raw HTML
return HTML(content)

# ✅ GOOD - escapes HTML
from html import escape
return HTML(escape(content))
```

### 5. Performance

**Optimization Techniques**:

1. **Database**:
   - Add indexes on foreign keys
   - Use select().load_only() for partial queries
   - Implement pagination
   - Use connection pooling

2. **API**:
   - Use async/await for I/O
   - Cache expensive operations
   - Compress responses (gzip)
   - Implement rate limiting

3. **Code**:
   - Profile before optimizing
   - Use built-in functions
   - Avoid premature optimization

### 6. Testing

**Testing Pyramid**:
```
     /\
    /E2E\       # Few (critical paths only)
   /------\
  /Integration\  # Some (API flows)
 /------------\
/  Unit Tests   \ # Many (business logic)
------------------
```

**Best Practices**:
- Test business logic, not implementation
- Mock external dependencies
- Test error cases
- Aim for >80% coverage
- Use descriptive test names

**Example**:
```python
def test_create_user_with_duplicate_email():
    """Test creating user with duplicate email raises error."""
    existing_data = {"email": "test@example.com", "username": "test"}
    await service.create(UserCreate(**existing_data))

    duplicate_data = {"email": "test@example.com", "username": "test2"}

    with pytest.raises(ValueError, match="Email already exists"):
        await service.create(UserCreate(**duplicate_data))
```

### 7. Code Organization

**Feature-Based Structure** (Recommended):
```
features/
├── users/
│   ├── routes.py       # User endpoints
│   ├── service.py      # User business logic
│   ├── repository.py   # User data access
│   └── models.py       # User models
└── posts/
    ├── routes.py
    ├── service.py
    ├── repository.py
    └── models.py

shared/
├── middleware/
├── utils/
└── config/
```

**Benefits**:
- Related code stays together
- Easier to find feature code
- Supports microservices extraction
- Clear feature boundaries

### 8. API Design

**RESTful Conventions**:
- Use nouns for resources (/users, not /getUsers)
- Use plural form (/api/users, not /api/user)
- Use HTTP methods correctly (GET, POST, PUT, DELETE)
- Return appropriate status codes
- Implement pagination for list endpoints
- Provide filtering and sorting
- Version your API

**URL Design**:
```
✅ Good:
GET    /api/users
GET    /api/users/123
POST   /api/users
PUT    /api/users/123
DELETE /api/users/123
GET    /api/users/123/posts

❌ Bad:
GET    /api/getUsers
POST   /api/createUser
GET    /api/user/1
```

### 9. Documentation

**Code Documentation**:
- Use docstrings for functions/classes
- Comment complex algorithms
- Document API endpoints
- Include usage examples

**Docstring Example (Google Style)**:
```python
def create_user(email: str, username: str, password: str) -> User:
    """Create a new user account.

    Args:
        email: User's email address (must be unique)
        username: Username (must be unique)
        password: Password (will be hashed)

    Returns:
        Created user object

    Raises:
        ValueError: If email or username already exists
    """
    existing = find_by_email(email)
    if existing:
        raise ValueError("Email already exists")
    # ... implementation
```

**API Documentation**:
- Use OpenAPI/Swagger (FastAPI has this built-in)
- Document all endpoints
- Include request/response examples
- Document error responses
- Provide usage examples

### 10. Version Control

**Commit Messages**:
```
✅ Good:
feat: add user authentication
fix: resolve password hash bug
docs: update API documentation
refactor: extract user service

❌ Bad:
update
fix stuff
changes
```

**Git Workflow**:
- Use feature branches
- Write meaningful commit messages
- Pull request for code review
- Keep commits atomic
- Never commit secrets

## Framework-Specific Best Practices

### FastAPI

- Use dependency injection
- Leverage Pydantic for validation
- Use async/await throughout
- Implement proper exception handlers
- Use APIRouter for organizing routes

### Express.js

- Use middleware for cross-cutting concerns
- Implement proper error handling middleware
- Use async/await for database operations
- Separate routes, controllers, services
- Use Joi/express-validator for validation

### SQLAlchemy

- Use sessions properly
- Commit/rollback in service layer
- Use relationships efficiently
- Index foreign keys
- Query with joins when needed

### Prisma

- Use generated client
- Leverage type safety
- Use transactions for multi-step operations
- Optimize includes/selects
- Use Prisma Migrate for schema changes

## Common Pitfalls to Avoid

1. **N+1 Query Problem**: Fetch related data in one query
2. **Over-fetching**: Only select needed fields
3. **Not Indexing**: Add indexes to frequently queried fields
4. **Ignoring Errors**: Always handle exceptions
5. **Hardcoding**: Use environment variables
6. **Blocking I/O**: Use async for I/O operations
7. **Large Transactions**: Keep transactions short
8. **Testing Implementation**: Test behavior, not code
9. **Premature Optimization**: Profile first
10. **Ignoring Security**: Never trust input

## Quick Checklist

Before deploying:
- [ ] All inputs validated
- [ ] SQL injection prevented
- [ ] XSS prevented
- [ ] Authentication implemented
- [ ] Rate limiting configured
- [ ] HTTPS only
- [ ] Secrets not hardcoded
- [ ] Error handling comprehensive
- [ ] Logging implemented
- [ ] Tests written
- [ ] API documented
- [ ] Dependencies updated
- [ ] Performance tested