# Database Operations Module

## Purpose

Generate database models, repositories, and migrations.

## When to Use This Module

- Defining data models and schemas
- Creating database queries
- Writing migrations
- Managing relationships
- Transaction management

## Framework Support

### SQLAlchemy (FastAPI/Flask)

**Model Example**:
```python
from sqlalchemy import Column, Integer, String, DateTime
from models.base import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Repository Pattern**:
```python
class UserRepository:
    def __init__(self, db):
        self.db = db

    async def find_by_id(self, user_id: int):
        return self.db.query(User).filter(User.id == user_id).first()

    async def find_by_email(self, email: str):
        return self.db.query(User).filter(User.email == email).first()

    async def create(self, user_data: dict):
        user = User(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
```

### Tortoise-ORM (Sanic)

```python
from tortoise import fields
from tortoise.models import Model

class User(Model):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True)
    username = fields.CharField(max_length=100, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"
```

### Prisma (Node.js)

```prisma
model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  username  String   @unique
  createdAt DateTime @default(now())
  posts     Post[]
}
```

## Best Practices

1. **Always use indexes** on foreign keys and frequently queried fields
2. **Use parameterized queries** to prevent SQL injection
3. **Implement transactions** for multi-step operations
4. **Use repository pattern** to abstract database access
5. **Add created_at/updated_at** timestamps
6. **Use relationships** (foreign keys) efficiently
7. **Normalize your schema** (3NF typically)

## Migration Tools

- **Alembic** (SQLAlchemy)
- **Aerich** (Tortoise-ORM)
- **Prisma Migrate** (Prisma)

## Examples

- `/modules/database-operations/examples/sqlalchemy-models.md`
- `/modules/database-operations/examples/prisma-models.md`

## Templates

- `/assets/templates/python/model.py.template`
- `/assets/templates/python/repository.py.template`