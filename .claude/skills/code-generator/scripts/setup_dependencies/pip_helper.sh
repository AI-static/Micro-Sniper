#!/bin/bash
# pip 常用命令助手

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

show_usage() {
    cat << EOF

${BLUE}═══════════════════════════════════════════════════════════════${NC}
${BLUE}          pip 常用命令助手${NC}
${BLUE}═══════════════════════════════════════════════════════════════${NC}

${GREEN}📦 包管理${NC}
  pip install <package>          # 安装包
  pip install -r requirements.txt # 从文件安装
  pip install --upgrade <package> # 升级包
  pip install -e .               # 可编辑安装（当前项目）
  pip uninstall <package>        # 卸载包

${GREEN}📋 查看信息${NC}
  pip list                       # 列出已安装的包
  pip show <package>             # 显示包详细信息
  pip index versions <package>   # 查看包的所有版本
  pip check                      # 检查依赖冲突

${GREEN}🔒 依赖导出${NC}
  pip freeze > requirements.txt  # 导出所有依赖
  pip freeze | grep -v "^\-e" > requirements.txt  # 排除可编辑包

${GREEN}🔧 虚拟环境${NC}
  python -m venv .venv           # 创建虚拟环境
  source .venv/bin/activate      # 激活环境 (Linux/Mac)
  .venv\Scripts\activate         # 激活环境 (Windows)
  deactivate                    # 退出虚拟环境

${GREEN}🧹 清理${NC}
  pip cache purge                # 清除缓存
  pip cache remove <package>     # 清除特定包缓存

${GREEN}🔍 搜索${NC}
  pip search <query>             # 搜索包（需要索引）
  pip index versions <package>   # 查看可用版本

${GREEN}📈 升级 pip${NC}
  pip install --upgrade pip      # 升级 pip
  python -m pip install --upgrade pip

${BLUE}═══════════════════════════════════════════════════════════════${NC}
${BLUE}          常用工作流${NC}
${BLUE}═══════════════════════════════════════════════════════════════${NC}

${GREEN}1️⃣  新项目${NC}
  python -m venv .venv
  source .venv/bin/activate
  pip install fastapi uvicorn
  pip freeze > requirements.txt

${GREEN}2️⃣  安装依赖${NC}
  source .venv/bin/activate
  pip install -r requirements.txt

${GREEN}3️⃣  添加新依赖${NC}
  pip install <package>
  pip freeze > requirements.txt  # 更新 requirements.txt

${GREEN}4️⃣  日常开发${NC}
  python main.py                # 运行应用
  pip list                      # 查看已安装的包
  pip check                      # 检查冲突

${GREEN}5️⃣  最佳实践${NC}
  ✅ 始终使用虚拟环境
  ✅ 锁定依赖版本（pip freeze）
  ✅ 分离开发和生产依赖
  ✅ 定期运行 pip check
  ⚠️  考虑迁移到 Poetry 获得更好的依赖管理

${BLUE}═══════════════════════════════════════════════════════════════${NC}
${BLUE}          pip vs Poetry${NC}
${BLUE}═══════════════════════════════════════════════════════════════${NC}

${YELLOW}pip: 简单直接${NC}
  ✅ 内置于 Python
  ✅ 简单易用
  ❌ 依赖解析不完善
  ❌ 无锁文件
  ❌ 开发依赖管理不便

${YELLOW}Poetry: 现代标准${NC}
  ✅ 依赖解析更智能
  ✅ poetry.lock 锁文件
  ✅ 区分开发/生产依赖
  ✅ 内置虚拟环境管理
  ✅ 更好的依赖树管理

${GREEN}建议: 新项目使用 Poetry，现有项目可继续使用 pip${NC}

${BLUE}═══════════════════════════════════════════════════════════════${NC}
${BLUE}          常用包推荐${NC}
${BLUE}═══════════════════════════════════════════════════════════════${NC}

${GREEN}Web 框架:${NC}
  fastapi, uvicorn, sanic, flask, django

${GREEN}数据库:${NC}
  sqlalchemy, psycopg2-binary, pymongo, redis

${GREEN}代码质量:${NC}
  black, ruff, mypy, pytest

${GREEN}数据处理:${NC}
  pandas, numpy, requests

${GREEN}工具:${NC}
  python-dotenv, pydantic, click, typer

EOF
}

main() {
    if [ $# -gt 0 ]; then
        case "$1" in
            install)
                shift
                pip install "$@"
                ;;
            uninstall)
                shift
                pip uninstall "$@"
                ;;
            freeze)
                pip freeze
                ;;
            list)
                pip list
                ;;
            check)
                pip check
                ;;
            venv)
                python -m venv .venv
                echo -e "${GREEN}✓ 虚拟环境已创建: .venv${NC}"
                echo -e "${YELLOW}激活: source .venv/bin/activate${NC}"
                ;;
            *)
                show_usage
                ;;
        esac
    else
        show_usage
    fi
}

main "$@"