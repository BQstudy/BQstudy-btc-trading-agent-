# 快速部署指南

## 在服务器上执行以下命令，一行一行复制粘贴：

# 1. 安装Docker
curl -fsSL https://get.docker.com | sh

# 2. 启动Docker
systemctl start docker
systemctl enable docker

# 3. 创建项目目录
mkdir -p /opt/btc-agent
cd /opt/btc-agent

# 4. 创建.env文件
cat > .env << 'EOF'
TELEGRAM_BOT_TOKEN=8497683014:AAEhTmi5fUA-FC3lF_wb7U3LU-U2e5SO8KE
TELEGRAM_CHAT_ID=6415396006
OKX_API_KEY=bedc2600-1879-416a-9375-3c7a6c594c50
OKX_API_SECRET=F68A63AA108E8B6BC20BA58BF327F6A2
OKX_PASSPHRASE=Bc887720.
PAPER_TRADING=true
TRADE_INTERVAL=3600
EOF

# 5. 创建必要目录
mkdir -p data logs reports config

# 6. 克隆项目
git clone https://github.com/BQstudy/BQstudy-btc-trading-agent-.git temp_project

# 7. 复制项目文件
cp -r temp_project/src .
cp -r temp_project/config .
cp -r temp_project/prompts .
cp -r temp_project/deploy/* .
cp temp_project/requirements.txt .
cp temp_project/CLAUDE.md .
cp -r temp_project/.gitignore .
rm -rf temp_project

# 8. 构建并启动
docker compose -f docker-compose.yml up -d --build

# 9. 查看日志
docker compose -f docker-compose.yml logs -f
