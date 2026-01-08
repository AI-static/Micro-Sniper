# Configuration Management Module

## Purpose

Generate application configuration and settings management code.

## When to Use This Module

- Loading environment variables
- Validating configuration
- Type-safe settings
- Environment-specific configs
- Secret management

## Tools & Frameworks

### Pydantic Settings (Python)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "My API"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str

    # Security
    SECRET_KEY: str

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

### dotenv (Node.js)

```javascript
require('dotenv').config();

const config = {
  app: {
    name: process.env.APP_NAME || 'My API',
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

## Best Practices

1. **Never commit secrets** to version control
2. **Use .env.example** to document required env vars
3. **Validate configuration** on startup
4. **Use type-safe config** (Pydantic, TypeScript)
5. **Separate configs by environment** (dev, staging, prod)
6. **Provide default values** for non-sensitive settings

## Environment Files

**.env.example**:
```
APP_NAME=My API
DEBUG=false
DATABASE_URL=postgresql://user:pass@localhost/db
SECRET_KEY=your-secret-key
```

## Examples

- `/modules/configuration-management/examples/pydantic-settings.md`
- `/modules/configuration-management/examples/dotenv-config.md`

## Templates

- `/assets/templates/python/config.py.template`
- `/assets/configs/pyproject.toml.template`