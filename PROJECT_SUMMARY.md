# BTC交易Agent - 项目完整总结

## 项目概述

**项目名称**: BTC永续合约拟人化交易Agent  
**核心哲学**: AI simulates traders, not math. (让LLM模拟人的主观判断，而非数学近似市场)  
**开发周期**: 2026/04/09  
**部署状态**: ✅ 已上线运行  

---

## 一、系统架构

### 五阶段交易流程

```
┌─────────────────────────────────────────────────────────────┐
│                    BTC Trading Agent                         │
├─────────────┬─────────────┬─────────────┬──────────┬────────┤
│  Phase 1    │   Phase 2   │   Phase 3   │ Phase 4  │ Phase 5│
│ 市场感知层   │ 主观判断引擎 │  决策执行层  │ 记忆系统 │ 自迭代 │
├─────────────┼─────────────┼─────────────┼──────────┼────────┤
│ 数据获取     │ 多角色辩论   │ 仓位计算     │ 交易记录 │ 元分析 │
│ 市场叙述     │ 状态检测     │ 风控管理     │ 向量存储 │ 提示词 │
│ 情绪分析     │ 关键价位     │ 订单执行     │ 复盘引擎 │ 蒸馏   │
└─────────────┴─────────────┴─────────────┴──────────┴────────┘
```

### 多角色辩论引擎
- **Bull** (看涨派) - temperature=0.9
- **Bear** (看跌派) - temperature=0.9
- **Neutral** (中性派) - temperature=0.7
- **Risk** (风控官) - temperature=0.3
- **Judge** (决策者) - temperature=0.5

---

## 二、技术栈

| 层级 | 技术 |
|------|------|
| **LLM** | 腾讯云LKEAP (kimi-k2.5) |
| **交易所** | OKX Demo Trading (ccxt) |
| **数据库** | SQLite + ChromaDB |
| **通知** | Telegram Bot |
| **部署** | Docker + Docker Compose |
| **监控** | HTTP健康检查端点 |

---

## 三、开发历程

### Phase 1: 项目初始化
- 创建目录结构
- 配置文件设计
- 基础模块搭建

### Phase 2: 核心模块开发
| 模块 | 文件 | 功能 |
|------|------|------|
| 市场感知 | `perception/` | 数据获取、叙述生成、情绪分析 |
| 主观判断 | `judgment/` | 辩论引擎、状态检测、价位分析 |
| 决策执行 | `decision/` | 仓位计算、风控、订单执行 |
| 记忆系统 | `memory/` | 交易记录、向量存储、复盘 |
| 自迭代 | `evolution/` | 元分析、提示词优化、蒸馏 |

### Phase 3: 关键Bug修复

| Bug | 原因 | 修复 |
|-----|------|------|
| 仓位1123% | 杠杆计算错误 | 添加max_margin约束 |
| TradeLog接口 | 字段名不一致 | 统一entry_time/direction |
| RegimeFlags错误 | 类型处理缺失 | 支持Dict和dataclass |
| OKX下单失败 | 缺少posSide参数 | 添加long/short参数 |
| Telegram接口 | 参数不匹配 | 支持多种调用方式 |

### Phase 4: 部署上线
- Docker容器化
- 云服务器部署 (43.167.232.83)
- 健康检查端点
- 24小时自动运行

---

## 四、运行配置

### 当前运行参数
```yaml
运行间隔: 1800秒 (30分钟)
交易模式: 纸面交易 (PAPER_TRADING)
通知频率: 每周期完成推送
监控端点: http://服务器IP:8080/health
```

### Telegram通知内容
```
📊 市场感知
• 类型: consolidation/trending/ranging
• 情绪: bullish/bearish/neutral
• 叙述: 市场状态描述

🧠 主观判断  
• 方向: long/short/neutral
• 置信度: 0-100%
• 辩论: 多空观点摘要

📌 最终决策
• 行动: open_long/open_short/no_trade
• 原因: 开单参数 / 不交易理由
```

---

## 五、风控体系

### 硬风控 (不可覆盖)
- 仓位上限: 30%
- 杠杆上限: 10x
- 单笔风险: 0.5%-2%
- 连续亏损限制: 3次

### 软风控 (可配置)
- 市场状态过滤
- 置信度阈值
- 波动率限制

---

## 六、部署架构

```
┌─────────────────────────────────────┐
│          云服务器 (Ubuntu)           │
│         43.167.232.83               │
├─────────────────────────────────────┤
│  Docker Container: btc-trading-agent │
├─────────────────────────────────────┤
│  • Agent Core (Python 3.11)         │
│  • LLM Client (Tencent LKEAP)       │
│  • Exchange Client (OKX)            │
│  • Telegram Notifier                │
│  • Health Server (Port 8080)        │
├─────────────────────────────────────┤
│  Volumes:                           │
│  • ./data → /app/data (SQLite)      │
│  • ./logs → /app/logs               │
│  • ./reports → /app/reports         │
└─────────────────────────────────────┘
```

---

## 七、项目文件结构

```
btc-agent/
├── src/                          # 源代码
│   ├── agent.py                  # 主程序
│   ├── perception/               # Phase 1: 市场感知
│   ├── judgment/                 # Phase 2: 主观判断
│   ├── decision/                 # Phase 3: 决策执行
│   ├── memory/                   # Phase 4: 记忆系统
│   ├── evolution/                # Phase 5: 自迭代
│   ├── exchange/                 # 交易所接口
│   └── utils/                    # 工具模块
├── config/                       # 配置文件
│   ├── settings.yaml             # 主配置
│   └── risk_rules.yaml           # 风控规则
├── prompts/                      # LLM提示词
│   ├── perception_v1.yaml
│   ├── judgment_v1.yaml
│   ├── decision_v1.yaml
│   ├── review_v1.yaml
│   └── evolution_v1.yaml
├── deploy/                       # 部署文件
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── deploy.sh
│   └── DEPLOY.md
├── tools/                        # 工具脚本
│   └── monitor_agent.py          # 监控工具
├── data/                         # 数据存储
├── logs/                         # 日志文件
├── requirements.txt              # Python依赖
├── README.md                     # 项目说明
├── CLAUDE.md                     # 开发规范
└── DEVELOPMENT_LOG.md            # 开发记录
```

---

## 八、GitHub仓库

- **地址**: https://github.com/BQstudy/BQstudy-btc-trading-agent-
- **分支**: main
- **文件数**: 68个
- **提交数**: 15+

---

## 九、监控与维护

### 常用命令
```bash
# 查看实时日志
docker compose -f deploy/docker-compose.yml logs -f

# 查看容器状态
docker ps

# 健康检查
curl http://localhost:8080/health

# 重启服务
docker compose -f deploy/docker-compose.yml restart
```

### Telegram Bot
- **Bot**: @yggai9bot
- **Chat ID**: 6415396006
- **通知类型**: 周期完成/交易执行/风控警报/系统错误

---

## 十、五大风险消解

1. **LLM数学不可靠** → 认知与计算解耦，Python工具层执行精确计算
2. **纯叙事无锚点** → 注入事实锚点（波动率/费率/OI布尔值）
3. **执行缺流动性** → 滑点保护、OCO订单、部分成交处理
4. **辩论共识幻觉** → 差异化temperature、冲突度量化
5. **长CoT低质量** → CoTValidator校验、低质量降级

---

## 十一、后续优化方向

1. **策略优化**: 根据历史交易数据优化提示词
2. **多币种**: 扩展支持ETH等其他币种
3. **实盘交易**: 在纸面交易验证稳定后切换实盘
4. **Web界面**: 添加交易面板和实时图表
5. **报警升级**: 添加短信/邮件等多渠道报警

---

## 十二、关键成果

✅ **完整交易流程**: 5阶段闭环交易系统  
✅ **多角色辩论**: 5个AI角色协同决策  
✅ **严格风控**: 硬风控不可覆盖  
✅ **实时通知**: Telegram实时推送  
✅ **24小时运行**: Docker容器化部署  
✅ **健康监控**: HTTP端点+自动重启  
✅ **详细日志**: 完整CoT记录  

---

**项目状态**: 🟢 生产环境运行中  
**最后更新**: 2026/04/09  
**版本**: v1.0
