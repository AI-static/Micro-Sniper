#!/bin/bash
# Poetry Commands Helper - 常用 Poetry 命令参考
# Micro-Sniper Code Generator Skill

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 显示使用说明
show_usage() {
    cat << EOF

${BLUE}═══════════════════════════════════════════════════════════════${NC}
${BLUE}          Poetry 常用命令助手${NC}
${BLUE}═══════════════════════════════════════════════════════════════${NC}

${GREEN}📦 项目初始化${NC}
  poetry init                    # 交互式创建新项目
  poetry new <name>              # 创建新项目目录
  poetry new <name> --src        # 创建 src/ 布局的项目

${GREEN}➕ 依赖管理${NC}
  poetry add <package>           # 添加依赖（生产环境）
  poetry add -D <package>        # 添加开发依赖
  poetry add "package@^1.0"      # 指定版本
  poetry add --group dev black   # 添加到特定组

${GREEN}📋 查看依赖${NC}
  poetry show                    # 显示所有已安装的包
  poetry show --tree             # 显示依赖树
  poetry show <package>          # 显示包详细信息
  poetry outdated                # 检查过期的包

${GREEN}🗑️ 移除依赖${NC}
  poetry remove <package>        # 移除包
  poetry remove --dev <package>  # 移除开发依赖

${GREEN}🔄 更新依赖${NC}
  poetry update                  # 更新所有依赖
  poetry update <package>        # 更新特定包
  poetry lock                    # 更新 poetry.lock（不安装）

${GREEN}⬇️ 安装依赖${NC}
  poetry install                 # 安装所有依赖
  poetry install --no-dev        # 仅安装生产依赖
  poetry install --no-root       # 不安装根包
  poetry install --sync          # 同步环境（移除不需要的）

${GREEN}🔧 虚拟环境${NC}
  poetry env list                # 列出所有虚拟环境
  poetry env info                # 显示当前虚拟环境信息
  poetry env remove --all        # 删除所有虚拟环境
  poetry env use /path/to/python  # 指定 Python 版本

${GREEN}🐚 命令执行${NC}
  poetry shell                   # 激活虚拟环境（进入 shell）
  poetry run <command>           # 在虚拟环境中执行命令
  poetry run python main.py      # 运行 Python 脚本
  poetry run python -m pytest    # 运行测试
  exit                          # 退出 poetry shell

${GREEN}🏗️ 构建与发布${NC}
  poetry build                   # 构建 sdist 和 wheel
  poetry build --format wheel    # 仅构建 wheel
  poetry publish                 # 发布到 PyPI
  poetry publish --repository private-repo  # 发布到私有仓库

${GREEN}📤 导出${NC}
  poetry export -f requirements.txt               # 导出为 requirements.txt
  poetry export -f requirements.txt --without-hashes  # 不包含哈希
  poetry export -f requirements.txt --without dev  # 仅生产依赖
  poetry export -f requirements.txt --without-hashes --without dev > requirements.txt

${GREEN}🧹 清理${NC}
  poetry cache clear --all       # 清除所有缓存
  poetry cache clear pypi --all  # 清除 PyPI 缓存
  poetry cache clear <package>   # 清除特定包缓存

${GREEN}📊 配置${NC}
  poetry config --list           # 查看所有配置
  poetry config virtualenvs.in-project true  # 在项目中创建 .venv
  poetry config virtualenvs.path ~/.venvs     # 设置虚拟环境目录

${BLUE}═══════════════════════════════════════════════════════════════${NC}
${BLUE}          Micro-Sniper 常用工作流${NC}
${BLUE}═══════════════════════════════════════════════════════════════${NC}

${GREEN}1️⃣  新项目${NC}
  poetry new my-project
  cd my-project
  poetry install
  poetry shell

${GREEN}2️⃣  添加依赖${NC}
  poetry add fastapi uvicorn
  poetry add -D pytest black ruff mypy
  poetry install

${GREEN}3️⃣  日常开发${NC}
  poetry run python main.py
  poetry run pytest
  poetry run black .
  poetry run ruff check .

${GREEN}4️⃣  导出到 requirements.txt${NC}
  poetry export -f requirements.txt --without-hashes --without dev > requirements.txt

${GREEN}5️⃣  清理环境${NC}
  poetry cache clear --all
  poetry env remove --all

EOF
}

# 交互式菜单
show_menu() {
    echo -e "\n${BLUE}选择一个操作:${NC}"
    echo "1. 初始化新项目"
    echo "2. 添加依赖"
    echo "3. 移除依赖"
    echo "4. 查看已安装的包"
    echo "5. 安装依赖"
    echo "6. 运行命令"
    echo "7. 导出 requirements.txt"
    echo "8. 清理缓存"
    echo "9. 显示完整命令列表"
    echo "0. 退出"
    echo -n "请选择 [0-9]: "
}

# 主函数
main() {
    # 如果带参数，直接执行命令
    if [ $# -gt 0 ]; then
        case "$1" in
            init)
                echo "初始化新项目: poetry init"
                poetry init
                ;;
            add)
                shift
                if [ -z "$1" ]; then
                    echo -e "${RED}错误: 请指定要添加的包${NC}"
                    exit 1
                fi
                echo "添加依赖: poetry add $@"
                poetry add "$@"
                ;;
            install)
                echo "安装依赖: poetry install"
                poetry install
                ;;
            shell)
                echo "进入 Poetry shell"
                poetry shell
                ;;
            export)
                echo "导出到 requirements.txt..."
                poetry export -f requirements.txt --without-hashes --without dev -o requirements.txt
                echo -e "${GREEN}✓ 已导出到 requirements.txt${NC}"
                ;;
            update)
                echo "更新依赖: poetry update"
                poetry update
                ;;
            show)
                echo "显示已安装的包:"
                poetry show
                ;;
            *)
                show_usage
                ;;
        esac
        exit 0
    fi

    # 交互式菜单
    while true; do
        clear
        show_usage
        show_menu
        read -r choice

        case $choice in
            1)
                echo -e "\n${GREEN}初始化新项目${NC}"
                poetry init
                ;;
            2)
                echo -e "\n${GREEN}添加依赖${NC}"
                echo -n "输入包名（例如: fastapi）: "
                read -r package
                if [ -n "$package" ]; then
                    poetry add "$package"
                fi
                ;;
            3)
                echo -e "\n${GREEN}移除依赖${NC}"
                echo -n "输入包名: "
                read -r package
                if [ -n "$package" ]; then
                    poetry remove "$package"
                fi
                ;;
            4)
                echo -e "\n${GREEN}已安装的包:${NC}"
                poetry show
                ;;
            5)
                echo -e "\n${GREEN}安装依赖...${NC}"
                poetry install
                ;;
            6)
                echo -e "\n${GREEN}运行命令${NC}"
                echo -n "输入命令（例如: python main.py）: "
                read -r cmd
                if [ -n "$cmd" ]; then
                    poetry run $cmd
                fi
                ;;
            7)
                echo -e "\n${GREEN}导出到 requirements.txt...${NC}"
                poetry export -f requirements.txt --without-hashes --without dev -o requirements.txt
                echo -e "${GREEN}✓ 已导出${NC}"
                ;;
            8)
                echo -e "\n${GREEN}清理缓存...${NC}"
                poetry cache clear --all
                echo -e "${GREEN}✓ 缓存已清理${NC}"
                ;;
            9)
                show_usage
                ;;
            0)
                echo -e "\n${GREEN}再见！${NC}"
                exit 0
                ;;
            *)
                echo -e "\n${RED}无效选择，请重试${NC}"
                ;;
        esac

        echo -e "\n按任意键继续..."
        read -n 1 -s
    done
}

# 检查 poetry 是否安装
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}错误: Poetry 未安装${NC}"
    echo "请先安装 Poetry: curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

# 运行主函数
main "$@"