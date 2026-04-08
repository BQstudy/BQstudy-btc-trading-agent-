#!/bin/bash
# BTC交易Agent 部署脚本
# 支持Ubuntu/CentOS/Debian

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印信息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查root权限
check_root() {
    if [[ $EUID -ne 0 ]]; then
       print_error "请使用root权限运行此脚本"
       exit 1
    fi
}

# 安装Docker
install_docker() {
    print_info "安装Docker..."

    if command -v docker &> /dev/null; then
        print_warn "Docker已安装，跳过"
        docker --version
        return
    fi

    # 检测系统类型
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    else
        print_error "无法检测操作系统类型"
        exit 1
    fi

    case $OS in
        ubuntu|debian)
            apt-get update
            apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
            curl -fsSL https://download.docker.com/linux/$OS/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/$OS $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
            apt-get update
            apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        centos|rhel|fedora)
            yum install -y yum-utils
            yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            systemctl start docker
            systemctl enable docker
            ;;
        *)
            print_error "不支持的操作系统: $OS"
            exit 1
            ;;
    esac

    # 验证安装
    docker --version
    docker compose version
    print_info "Docker安装完成"
}

# 创建项目目录
setup_project() {
    print_info "设置项目目录..."

    PROJECT_DIR="/opt/btc-agent"
    mkdir -p $PROJECT_DIR
    cd $PROJECT_DIR

    # 创建必要目录
    mkdir -p data logs reports config deploy

    print_info "项目目录: $PROJECT_DIR"
}

# 复制项目文件
copy_files() {
    print_info "复制项目文件..."

    # 注意：这些文件需要手动上传或使用git克隆
    print_warn "请确保以下文件已上传到服务器:"
    echo "  - src/ 目录"
    echo "  - config/ 目录"
    echo "  - deploy/ 目录"
    echo "  - requirements.txt"

    read -p "文件是否已准备好? (y/n): " ready
    if [ "$ready" != "y" ]; then
        print_error "请先上传项目文件"
        exit 1
    fi
}

# 配置环境变量
setup_env() {
    print_info "配置环境变量..."

    ENV_FILE=".env"

    if [ -f "$ENV_FILE" ]; then
        print_warn ".env文件已存在"
        read -p "是否覆盖? (y/n): " overwrite
        if [ "$overwrite" != "y" ]; then
            return
        fi
    fi

    # 复制示例文件
    cp deploy/.env.example .env

    print_info "请编辑 .env 文件配置敏感信息"
    print_info "使用命令: nano .env 或 vim .env"
}

# 构建和启动
build_and_start() {
    print_info "构建Docker镜像..."

    cd /opt/btc-agent

    # 构建镜像
    docker compose -f deploy/docker-compose.yml build

    print_info "启动服务..."
    docker compose -f deploy/docker-compose.yml up -d

    print_info "查看日志..."
    sleep 3
    docker compose -f deploy/docker-compose.yml logs -f
}

# 设置系统服务
setup_systemd() {
    print_info "设置系统服务..."

    cat > /etc/systemd/system/btc-agent.service << 'EOF'
[Unit]
Description=BTC Trading Agent
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/btc-agent
ExecStart=/usr/bin/docker compose -f deploy/docker-compose.yml up -d
ExecStop=/usr/bin/docker compose -f deploy/docker-compose.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable btc-agent
    print_info "系统服务已设置，可使用: systemctl start|stop|restart btc-agent"
}

# 显示状态
show_status() {
    print_info "部署状态:"
    echo ""
    docker ps --filter "name=btc" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    print_info "日志查看: docker compose -f deploy/docker-compose.yml logs -f"
    print_info "停止服务: docker compose -f deploy/docker-compose.yml down"
    print_info "重启服务: docker compose -f deploy/docker-compose.yml restart"
}

# 主函数
main() {
    echo "========================================"
    echo "  BTC交易Agent 部署脚本"
    echo "========================================"
    echo ""

    check_root
    install_docker
    setup_project
    copy_files
    setup_env
    build_and_start
    setup_systemd
    show_status

    print_info "部署完成!"
    print_info "Telegram Bot: @yggai9bot"
}

# 运行主函数
main
