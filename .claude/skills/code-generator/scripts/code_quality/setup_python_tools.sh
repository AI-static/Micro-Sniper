#!/bin/bash
# Python 代码质量工具设置脚本
# 设置: black, ruff, mypy, pre-commit

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}          Python 代码质量工具设置${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# 检查 Python 版本
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "\n${GREEN}✓ Python 版本: $PYTHON_VERSION${NC}"

# 检查是否使用 Poetry
if [ -f "pyproject.toml" ]; then
    echo -e "${GREEN}✓ 检测到 pyproject.toml（Poetry 项目）${NC}"
    USE_POETRY=true
elif [ -f "requirements.txt" ]; then
    echo -e "${GREEN}✓ 检测到 requirements.txt（pip 项目）${NC}"
    USE_POETRY=false
else
    echo -e "${YELLOW}⚠ 未检测到 pyproject.toml 或 requirements.txt${NC}"
    echo -n "使用 Poetry 安装? [y/N]: "
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        USE_POETRY=true
    else
        USE_POETRY=false
    fi
fi

# 安装工具
echo -e "\n${BLUE}正在安装代码质量工具...${NC}"

if [ "$USE_POETRY" = true ]; then
    if command -v poetry &> /dev/null; then
        echo -e "${GREEN}使用 Poetry 安装...${NC}"
        poetry add -D black ruff mypy pre-commit
    else
        echo -e "${RED}错误: Poetry 未安装${NC}"
        echo "回退到 pip..."
        pip install black ruff mypy pre-commit
    fi
else
    echo -e "${GREEN}使用 pip 安装...${NC}"
    pip install black ruff mypy pre-commit
fi

echo -e "${GREEN}✓ 工具安装完成${NC}"

# 生成 pyproject.toml 配置（如果使用 pip）
if [ "$USE_POETRY" = false ]; then
    echo -e "\n${BLUE}生成 pyproject.toml 配置...${NC}"

    cat > pyproject.toml << 'EOF'
[tool.black]
line-length = 120
target-version = ['py311', 'py310', 'py39']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''

[tool.ruff]
target-version = "py311"
line-length = 120
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # Pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
ignore = [
    "E501",  # line too long (handled by black)
    "B008",  # do not perform function calls in argument defaults
]
exclude = [
    ".bzr",
    ".direnv",
    ".eggs",
    ".git",
    ".hg",
    ".mypy_cache",
    ".nox",
    ".pants.d",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    "__pypackages__",
    "_build",
    "buck-out",
    "build",
    "dist",
    "node_modules",
    "venv",
]

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports in __init__.py

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
follow_imports = "normal"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
EOF

    echo -e "${GREEN}✓ pyproject.toml 已创建${NC}"
else
    echo -e "\n${YELLOW}⚠ 检测到现有 pyproject.toml，请手动添加以下配置:${NC}"
    cat << 'EOF'

[tool.black]
line-length = 120
target-version = ['py311']

[tool.ruff]
target-version = "py311"
line-length = 120
select = ["E", "W", "F", "I", "B", "C4", "UP"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
EOF
fi

# 生成 pre-commit 配置
echo -e "\n${BLUE}生成 .pre-commit-config.yaml...${NC}"

cat > .pre-commit-config.yaml << 'EOF'
repos:
  # Python code formatting
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.11

  # Python linting
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  # Python type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies:
          - types-all
        args: [--ignore-missing-imports]

  # General pre-commit hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
        args: [--unsafe]
      - id: check-added-large-files
        args: [--maxkb=1000]
      - id: check-json
      - id: check-toml
      - id: check-merge-conflict
      - id: debug-statements
EOF

echo -e "${GREEN}✓ .pre-commit-config.yaml 已创建${NC}"

# 生成 .gitignore（如果不存在）
if [ ! -f ".gitignore" ]; then
    echo -e "\n${BLUE}生成 .gitignore...${NC}"

    cat > .gitignore << 'EOF'
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

# PyInstaller
*.manifest
*.spec

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# ruff
.ruff_cache/

# IDEs
.idea/
.vscode/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Environment variables
.env
.env.local
.env.*.local

# Virtual environments
venv/
ENV/
env/
.venv/
EOF

    echo -e "${GREEN}✓ .gitignore 已创建${NC}"
fi

# 安装 pre-commit hooks
echo -e "\n${BLUE}安装 pre-commit hooks...${NC}"
if command -v pre-commit &> /dev/null; then
    pre-commit install
    echo -e "${GREEN}✓ Pre-commit hooks 已安装${NC}"
else
    echo -e "${YELLOW}⚠ Pre-commit 未安装，无法安装 hooks${NC}"
    echo "请运行: pre-commit install"
fi

# 生成使用说明
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}          设置完成！${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

cat << 'EOF'

📋 生成的文件:
  - pyproject.toml          # 工具配置
  - .pre-commit-config.yaml # Pre-commit hooks 配置
  - .gitignore              # Git 忽略文件（如果不存在）

🔧 工具说明:

1️⃣  Black (代码格式化)
   black .                          # 格式化所有代码
   black file.py                    # 格式化单个文件
   black --check .                  # 检查格式（不修改）
   black --diff .                   # 显示差异

2️⃣  Ruff (代码检查)
   ruff check .                     # 检查所有代码
   ruff check . --fix               # 自动修复问题
   ruff check file.py               # 检查单个文件
   ruff --select F401               # 检查特定规则

3️⃣  MyPy (类型检查)
   mypy .                           # 类型检查所有代码
   mypy file.py                     # 检查单个文件
   mypy --ignore-missing-imports .  # 忽略缺失的导入

4️⃣  Pre-commit (Git hooks)
   pre-commit run --all-files       # 运行所有 hooks
   pre-commit run black --all-files # 运行特定 hook
   pre-commit uninstall            # 卸载 hooks

💡 常用工作流:

   开发时:
   1. 修改代码
   2. git add .
   3. git commit    # hooks 自动运行
   4. 如果失败，修复后重新 commit

   手动运行:
   black . && ruff check . --fix && mypy .

📚 配置说明:

   - Line length: 120 字符
   - Python 版本: 3.11+
   - Black: 严格格式化
   - Ruff: 快速 linting
   - MyPy: 类型检查（可选）

🔄 更新配置:

   编辑 pyproject.toml 中的 [tool.*] 部分

EOF

echo -e "${YELLOW}提示: 首次运行 pre-commit 可能需要较长时间下载 hooks${NC}"
echo -e "${YELLOW}运行 'pre-commit run --all-files' 验证设置${NC}"