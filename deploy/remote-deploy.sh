#!/bin/bash
# BTC交易Agent 远程部署脚本
# 在服务器上执行

set -e

echo "========================================"
echo "  BTC交易Agent 远程部署"
echo "========================================"
echo ""

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查并安装Docker
install_docker() {
    print_info "检查Docker..."

    if command -v docker &> /dev/null; then
        print_info "Docker已安装: $(docker --version)"
        return
    fi

    print_info "正在安装Docker..."
    curl -fsSL https://get.docker.com | sh

    systemctl start docker
    systemctl enable docker

    print_info "Docker安装完成"
}

# 克隆项目
clone_project() {
    print_info "克隆项目..."

    PROJECT_DIR="/opt/btc-agent"

    if [ -d "$PROJECT_DIR" ]; then
        print_warn "目录已存在，更新代码..."
        cd $PROJECT_DIR
        git pull
    else
        mkdir -p /opt
        cd /opt
        git clone https://github.com/BQstudy/BQstudy-btc-trading-agent-.git btc-agent
        cd btc-agent
    fi

    print_info "项目已准备"
}

# 配置环境
setup_env() {
    print_info "配置环境变量..."

    cd /opt/btc-agent

    # 创建.env文件
    cat > .env << 'EOF'
# Telegram通知配置
TELEGRAM_BOT_TOKEN=8497683014:AAEhTmi5fUA-FC3lF_wb7U3LU-U2e5SO8KE
TELEGRAM_CHAT_ID=6415396006

# OKX API配置 (模拟盘)
OKX_API_KEY=bedc2600-1879-416a-9375-3c7a6c594c50
OKX_API_SECRET=F68A63AA108E8B6BC20BA58BF327F6A2
OKX_PASSPHRASE=Bc887720.

# 运行模式
PAPER_TRADING=true
TRADE_INTERVAL=3600
LOG_LEVEL=INFO
EOF

    print_info "环境变量已配置"
}

# 构建并启动
deploy() {
    print_info "构建Docker镜像..."

    cd /opt/btc-agent

    # 创建必要目录
    mkdir -p data logs reports

    # 构建并启动
    docker compose -f deploy/docker-compose.yml down 2>/dev/null || true
    docker compose -f deploy/docker-compose.yml build --no-cache
    docker compose -f deploy/docker-compose.yml up -d

    print_info "服务已启动"
}

# 显示状态
show_status() {
    echo ""
    echo "========================================"
    print_info "部署完成!"
    echo "========================================"
    echo ""

    # 显示容器状态
    docker ps --filter "name=btc" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    echo ""
    print_info "常用命令:"
    echo "  查看日志: docker compose -f /opt/btc-agent/deploy/docker-compose.yml logs -f"
    echo "  重启服务: docker compose -f /opt/btc-agent/deploy/docker-compose.yml restart"
    echo "  停止服务: docker compose -f /opt/btc-agent/deploy/docker-compose.yml down"
    echo ""
    print_info "Telegram Bot: @yggai9bot"
}

# 主函数
main() {
    install_docker
    clone_project
    setup_env
    deploy
    show_status
}

main
