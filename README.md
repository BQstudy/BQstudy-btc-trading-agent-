# BTC永续合约交易Agent

基于LLM的主观判断交易Agent，支持OKX模拟盘交易。

## 功能特性

- **五阶段交易流程**: 市场感知 → 主观判断 → 决策执行 → 记忆系统 → 自迭代
- **多角色辩论**: Bull/Bear/Neutral/Risk/Judge 5角色辩论决策
- **硬风控**: 仓位、杠杆、止损等严格限制
- **Telegram通知**: 实时交易通知和警报
- **纸面/实盘**: 支持模拟盘和实盘交易

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/btc-trading-agent.git
cd btc-trading-agent
```

### 2. 配置环境

```bash
# 复制环境变量文件
cp deploy/.env.example .env

# 编辑配置
nano .env
```

### 3. 运行

```bash
# 本地运行
python src/agent.py --paper --once

# Docker运行
docker compose -f deploy/docker-compose.yml up -d
```

## 项目结构

```
btc-agent/
├── src/
│   ├── agent.py              # 主程序
│   ├── perception/           # 市场感知层
│   ├── judgment/             # 主观判断引擎
│   ├── decision/             # 决策执行层
│   ├── memory/               # 记忆系统
│   ├── evolution/            # 自迭代引擎
│   ├── exchange/             # 交易所接口
│   └── utils/                # 工具模块
├── config/                   # 配置文件
├── deploy/                   # 部署文件
├── prompts/                  # LLM提示词
└── data/                     # 数据存储
```

## 配置说明

### 必需配置

```bash
# Telegram通知
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# OKX API (模拟盘)
OKX_API_KEY=your_key
OKX_API_SECRET=your_secret
OKX_PASSPHRASE=your_passphrase

# LLM API (腾讯云Kimi)
# 已在config/settings.yaml中配置
```

### 运行模式

```bash
# 纸面交易（测试）
python src/agent.py --paper --once

# 持续运行（每小时）
python src/agent.py --paper --interval 3600

# 实盘交易（谨慎！）
python src/agent.py --interval 3600
```

## 部署到云服务器

详见 [deploy/DEPLOY.md](deploy/DEPLOY.md)

```bash
# 一键部署
cd deploy
chmod +x deploy.sh
sudo ./deploy.sh
```

## 技术栈

- **Python 3.11**
- **LLM**: 腾讯云Kimi (kimi-k2.5)
- **交易所**: OKX (ccxt)
- **数据库**: SQLite
- **通知**: Telegram Bot
- **部署**: Docker

## 风险提示

⚠️ **交易有风险，使用需谨慎**

- 默认使用**纸面交易**模式，不会真实下单
- 实盘交易前请充分测试
- 请合理设置风控参数
- 不要投入无法承受损失的资金

## License

MIT License
