#!/bin/bash
# npm 常用命令助手

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
${BLUE}          npm 常用命令助手${NC}
${BLUE}═══════════════════════════════════════════════════════════════${NC}

${GREEN}📦 项目初始化${NC}
  npm init -y                    # 快速创建 package.json
  npm init -y es6                # 现代 ES6 设置

${GREEN}➕ 依赖管理${NC}
  npm install <package>          # 安装包（生产依赖）
  npm install -D <package>       # 安装开发依赖
  npm install -g <package>       # 全局安装
  npm install <package>@latest   # 安装最新版本
  npm install <package>@^1.0     # 指定版本范围

${GREEN}📋 查看依赖${NC}
  npm list                       # 显示所有依赖
  npm list --depth=0             # 仅显示顶层依赖
  npm list -g --depth=0          # 显示全局包
  npm outdated                   # 检查过期的包
  npm view <package>             # 查看包信息
  npm view <package> versions     # 查看所有版本

${GREEN}🗑️ 移除依赖${NC}
  npm uninstall <package>        # 移除包
  npm uninstall -g <package>     # 移除全局包
  npm prune                      # 移除未使用的依赖

${GREEN}🔄 更新依赖${NC}
  npm update                     # 更新所有依赖
  npm update <package>           # 更新特定包
  npm outdated                   # 查看可更新的包

${GREEN>📜 运行脚本${NC}
  npm run                        # 列出所有脚本
  npm run <script>               # 运行脚本
  npm run dev                    # 运行开发脚本
  npm run build                  # 运行构建脚本
  npm run test                   # 运行测试
  npm start                      # 运行启动脚本

${GREEN}🔧 配置${NC}
  npm config set <key> <value>   # 设置配置
  npm config get <key>           # 获取配置
  npm config list                # 显示所有配置
  npm config set registry https://registry.npmmirror.com  # 设置淘宝镜像

${GREEN}🧹 清理${NC}
  npm cache clean --force        # 清除缓存
  npm cache verify               # 验证缓存

${GREEN}🔍 安全审计${NC}
  npm audit                      # 安全审计
  npm audit fix                  # 自动修复漏洞
  npm audit fix --force          # 强制修复（可能破坏性更改）

${GREEN}🌐 工作区（Monorepo）${NC}
  npm workspace                 # 管理工作区
  npm install -w <workspace> <pkg>  # 安装到特定工作区

${BLUE}═══════════════════════════════════════════════════════════════${NC}
${BLUE}          常用工作流${NC}
${BLUE}═══════════════════════════════════════════════════════════════${NC}

${GREEN}1️⃣  新项目${NC}
  mkdir my-app && cd my-app
  npm init -y
  npm install express

${GREEN}2️⃣  添加开发依赖${NC}
  npm install -D eslint prettier jest

${GREEN}3️⃣  设置脚本${NC}
  # 在 package.json 中添加:
  # "scripts": {
  #   "dev": "nodemon src/index.js",
  #   "start": "node src/index.js",
  #   "test": "jest",
  #   "lint": "eslint .",
  #   "format": "prettier --write ."
  # }

${GREEN}4️⃣  日常开发${NC}
  npm run dev                    # 开发模式
  npm test                       # 运行测试
  npm run lint                   # 代码检查
  npm run format                 # 代码格式化

${GREEN}5️⃣  部署前${NC}
  npm audit                      # 安全检查
  npm outdated                   # 检查更新
  npm run build                  # 构建
  npm install --production       # 仅安装生产依赖

EOF
}

main() {
    if [ $# -gt 0 ]; then
        case "$1" in
            init)
                npm init -y
                ;;
            install)
                shift
                npm install "$@"
                ;;
            add)
                shift
                npm install "$@"
                ;;
            dev)
                shift
                npm install -D "$@"
                ;;
            run)
                shift
                npm run "$@"
                ;;
            list)
                npm list --depth=0
                ;;
            outdated)
                npm outdated
                ;;
            audit)
                npm audit
                npm audit fix
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