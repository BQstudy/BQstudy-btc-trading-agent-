# BTC交易Agent 云服务器部署指南

## 部署方式选择

### 方式1: Docker部署 (推荐)
使用Docker容器化部署，便于管理和迁移。

### 方式2: 直接部署
直接在服务器上运行Python程序。

---

## 方式1: Docker部署

### 1. 准备服务器

**最低配置:**
- CPU: 1核
- 内存: 512MB
- 磁盘: 10GB
- 系统: Ubuntu 20.04/22.04, CentOS 7/8, Debian 10/11

**推荐配置:**
- CPU: 2核
- 内存: 1GB
- 磁盘: 20GB

### 2. 安装Docker

```bash
# 一键安装Docker
curl -fsSL https://get.docker.com | sh

# 启动Docker
sudo systemctl start docker
sudo systemctl enable docker

# 验证安装
docker --version
docker compose version
```

### 3. 上传项目文件

**方法A: 使用scp命令**
```bash
# 在本地执行，将项目上传到服务器
scp -r "E:\AI 项目开发\6、交易agent开发\1.主观交易agent" root@你的服务器IP:/opt/btc-agent
```

**方法B: 使用git**
```bash
# 如果项目已推送到git仓库
git clone https://github.com/yourusername/btc-agent.git /opt/btc-agent
```

**方法C: 使用FTP工具**
- 使用FileZilla、WinSCP等工具上传

### 4. 配置环境变量

```bash
cd /opt/btc-agent

# 复制环境变量示例文件
cp deploy/.env.example .env

# 编辑环境变量文件
nano .env
```

**必须配置的变量:**
```bash
# Telegram通知
TELEGRAM_BOT_TOKEN=8497683014:AAEhTmi5fUA-FC3lF_wb7U3LU-U2e5SO8KE
TELEGRAM_CHAT_ID=6415396006

# OKX API (模拟盘)
OKX_API_KEY=bedc2600-1879-416a-9375-3c7a6c594c50
OKX_API_SECRET=F68A63AA108E8B6BC20BA58BF327F6A2
OKX_PASSPHRASE=Bc887720.
```

### 5. 启动服务

```bash
# 构建并启动
docker compose -f deploy/docker-compose.yml up -d --build

# 查看日志
docker compose -f deploy/docker-compose.yml logs -f

# 查看运行状态
docker ps
```

### 6. 设置开机自启

```bash
# 复制系统服务文件
sudo cp deploy/btc-agent.service /etc/systemd/system/

# 重新加载服务
sudo systemctl daemon-reload

# 设置开机自启
sudo systemctl enable btc-agent

# 启动服务
sudo systemctl start btc-agent

# 查看状态
sudo systemctl status btc-agent
```

---

## 方式2: 直接部署

### 1. 安装Python环境

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# CentOS
sudo yum install -y python3 python3-pip
```

### 2. 创建虚拟环境

```bash
cd /opt/btc-agent
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4. 配置环境变量

```bash
export TELEGRAM_BOT_TOKEN="8497683014:AAEhTmi5fUA-FC3lF_wb7U3LU-U2e5SO8KE"
export TELEGRAM_CHAT_ID="6415396006"
export OKX_API_KEY="bedc2600-1879-416a-9375-3c7a6c594c50"
export OKX_API_SECRET="F68A63AA108E8B6BC20BA58BF327F6A2"
export OKX_PASSPHRASE="Bc887720."
```

### 5. 使用screen后台运行

```bash
# 安装screen
sudo apt install -y screen

# 创建screen会话
screen -S btc-agent

# 运行Agent
cd /opt/btc-agent
source venv/bin/activate
python src/agent.py --paper --interval 1800

# 分离会话: Ctrl+A, 然后按D
# 重新连接: screen -r btc-agent
```

### 6. 或使用systemd服务

创建服务文件 `/etc/systemd/system/btc-agent.service`:

```ini
[Unit]
Description=BTC Trading Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/btc-agent
Environment="PYTHONPATH=/opt/btc-agent"
Environment="TELEGRAM_BOT_TOKEN=8497683014:AAEhTmi5fUA-FC3lF_wb7U3LU-U2e5SO8KE"
Environment="TELEGRAM_CHAT_ID=6415396006"
Environment="OKX_API_KEY=bedc2600-1879-416a-9375-3c7a6c594c50"
Environment="OKX_API_SECRET=F68A63AA108E8B6BC20BA58BF327F6A2"
Environment="OKX_PASSPHRASE=Bc887720."
ExecStart=/opt/btc-agent/venv/bin/python src/agent.py --paper --interval 1800
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务:
```bash
sudo systemctl daemon-reload
sudo systemctl enable btc-agent
sudo systemctl start btc-agent
sudo systemctl status btc-agent
```

---

## 常用命令

### Docker方式

```bash
# 查看日志
docker compose -f deploy/docker-compose.yml logs -f

# 重启服务
docker compose -f deploy/docker-compose.yml restart

# 停止服务
docker compose -f deploy/docker-compose.yml down

# 更新代码后重新构建
docker compose -f deploy/docker-compose.yml up -d --build

# 进入容器
docker exec -it btc-trading-agent bash
```

### Systemd方式

```bash
# 查看状态
sudo systemctl status btc-agent

# 查看日志
sudo journalctl -u btc-agent -f

# 重启服务
sudo systemctl restart btc-agent

# 停止服务
sudo systemctl stop btc-agent
```

---

## 监控和维护

### 1. 查看运行状态

```bash
# 查看Agent是否运行
docker ps | grep btc

# 或
ps aux | grep agent.py
```

### 2. 查看交易日志

```bash
# 实时查看日志
tail -f /opt/btc-agent/logs/agent.log

# 或Docker日志
docker logs -f btc-trading-agent
```

### 3. 备份数据

```bash
# 备份数据库和配置
tar -czvf backup-$(date +%Y%m%d).tar.gz /opt/btc-agent/data /opt/btc-agent/config
```

### 4. 更新代码

```bash
cd /opt/btc-agent

# 拉取最新代码
git pull

# 或使用scp重新上传

# 重启服务
docker compose -f deploy/docker-compose.yml restart
```

---

## 安全建议

1. **使用防火墙**
```bash
# 仅开放必要端口
sudo ufw default deny incoming
sudo ufw allow ssh
sudo ufw enable
```

2. **定期更新系统**
```bash
sudo apt update && sudo apt upgrade -y
```

3. **配置日志轮转**
```bash
# 已配置在docker-compose.yml中
# 日志保留3个文件，每个10MB
```

4. **使用非root用户运行** (可选)
```bash
# 创建专用用户
sudo useradd -r -s /bin/false btcagent
sudo chown -R btcagent:btcagent /opt/btc-agent
```

---

## 故障排查

### 1. 容器无法启动

```bash
# 查看错误日志
docker compose -f deploy/docker-compose.yml logs

# 检查环境变量
cat .env
```

### 2. API连接失败

```bash
# 测试OKX连接
docker exec btc-trading-agent python -c "from src.exchange.okx_client import OKXClient; c = OKXClient(testnet=True); print(c.get_account_info())"
```

### 3. Telegram通知失败

```bash
# 测试Telegram
docker exec btc-trading-agent python test_telegram.py
```

---

## 云服务推荐

| 服务商 | 推荐配置 | 价格(月) | 链接 |
|--------|----------|----------|------|
| 阿里云 | 1核1G | ~30元 | [链接](https://www.aliyun.com) |
| 腾讯云 | 1核1G | ~30元 | [链接](https://cloud.tencent.com) |
| AWS | t3.micro | 免费(1年) | [链接](https://aws.amazon.com) |
| Vultr | 1核1G | $5 | [链接](https://www.vultr.com) |

---

## 部署检查清单

- [ ] 服务器已购买并配置好SSH
- [ ] Docker已安装
- [ ] 项目文件已上传到 `/opt/btc-agent`
- [ ] `.env` 文件已配置
- [ ] 服务已启动
- [ ] Telegram通知测试成功
- [ ] 开机自启已设置
- [ ] 日志正常输出
