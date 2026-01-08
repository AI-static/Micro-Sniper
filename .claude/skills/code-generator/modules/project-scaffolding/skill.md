# Project Scaffolding Module

## Purpose

Generate complete project boilerplate with best practices.

## When to Use This Module

- Starting a new project
- Setting up project structure
- Initializing dependencies
- Configuring development tools

## Supported Frameworks

### Sanic (Python)

**Create Project**:
```bash
./scripts/scaffolding/create_sanic_project.sh my-api
```

**Generates**:
- Project structure (api/, services/, models/, tests/)
- pyproject.toml with dependencies
- app.py with Sanic application
- Tortoise-ORM configuration
- Redis integration
- Aerich migrations setup
- Example routes and services
- Configuration files
- .env.example
- README.md

### Express.js (Node.js)

**Coming Soon**:
```bash
./scripts/scaffolding/create_express_project.sh my-app
```

### FastAPI (Python)

**Available**:
```bash
./scripts/scaffolding/create_fastapi_project.sh my-app
```

## Project Structure

**FastAPI Structure**:
```
project/
├── api/
│   ├── routes/          # API endpoints
│   └── schema/          # Pydantic schemas
├── services/            # Business logic
├── models/              # Database models
├── middleware/          # Custom middleware
├── config/              # Configuration
├── tests/               # Tests
├── main.py              # Application entry
├── pyproject.toml       # Dependencies
└── .env.example         # Environment template
```

**Express Structure**:
```
project/
├── routes/              # API routes
├── controllers/         # Controllers
├── middleware/          # Express middleware
├── models/              # Database models
├── services/            # Business logic
├── config/              # Configuration
├── tests/               # Tests
├── app.js               # App setup
├── package.json         # Dependencies
└── .env.example         # Environment template
```

## Quick Start Commands

### FastAPI
```bash
cd my-api
poetry install
cp .env.example .env
# Edit .env
poetry run uvicorn main:app --reload
```

### Express
```bash
cd my-app
npm install
cp .env.example .env
# Edit .env
npm run dev
```

## Development Setup

After scaffolding:

1. **Install dependencies** (Poetry/npm)
2. **Configure environment** (.env)
3. **Setup code quality tools**
4. **Initialize database** (if needed)
5. **Run development server**

## Examples

- `/modules/project-scaffolding/examples/fastapi-starter.md`
- `/modules/project-scaffolding/examples/express-starter.md`

## Scripts

- `/scripts/scaffolding/create_fastapi_project.sh`
- `/scripts/scaffolding/create_express_project.sh`
- `/scripts/scaffolding/create_sanic_project.sh`