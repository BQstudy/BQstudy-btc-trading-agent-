# BTC永续合约交易Agent - 项目总结

## 项目概述

| 属性 | 值 |
|------|-----|
| **项目名称** | BTC永续合约拟人化交易Agent |
| **核心哲学** | AI simulates traders, not math. |
| **开发日期** | 2026/04/09 |
| **部署状态** | 🟢 生产环境运行中 |
| **版本** | v1.0 |

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

| 角色 | 定位 | Temperature |
|------|------|-------------|
| **Bull** | 看涨派 | 0.9 |
| **Bear** | 看跌派 | 0.9 |
| **Neutral** | 中性派 | 0.7 |
| **Risk** | 风控官 | 0.3 |
| **Judge** | 决策者 | 0.5 |

---

## 二、技术栈

| 层级 | 技术选择 | 备注 |
|------|----------|------|
| **LLM** | 腾讯云LKEAP (kimi-k2.5) | 支持Claude API兼容模式 |
| **交易所** | OKX Demo Trading | ccxt库集成 |
| **数据库** | SQLite | 交易记录存储 |
| **向量库** | ChromaDB | 经验向量化存储 |
| **通知** | Telegram Bot | @yggai9bot |
| **部署** | Docker | Ubuntu云服务器 |
| **监控** | HTTP健康检查 | 端口8080 |

---

## 三、模块开发状态

### 模块完成度矩阵

| 模块 | 核心文件 | 状态 | 说明 |
|------|----------|------|------|
| **市场感知** | `perception/` | ✅ 完成 | 数据获取、叙述生成、情绪分析 |
| **主观判断** | `judgment/` | ✅ 完成 | 辩论引擎、状态检测、价位分析 |
| **决策执行** | `decision/` | ✅ 完成 | 仓位计算、风控、订单执行 |
| **记忆系统** | `memory/` | ⚠️ 部分 | 交易记录可用，向量存储待优化 |
| **自迭代** | `evolution/` | 🔶 未测试 | 元分析、提示词优化、蒸馏 |

### 历史Bug修复

| Bug | 影响 | 状态 |
|-----|------|------|
| 仓位1123% | 杠杆计算错误 | ✅ 已修复 |
| TradeLog接口 | 字段名不一致 | ✅ 已修复 |
| RegimeFlags错误 | 类型处理缺失 | ✅ 已修复 |
| OKX下单失败 | 缺少posSide参数 | ✅ 已修复 |
| Telegram接口 | 参数不匹配 | ✅ 已修复 |

---

## 四、运行配置

### 运行时参数

```yaml
运行间隔:  1800秒 (30分钟)
交易模式:  PAPER_TRADING (纸面交易)
通知频率:  每周期完成推送 (开单/不开单理由)
监控端点:  http://43.167.232.83:8080/health
```

### Telegram通知模板

```
📊 市场感知
• 类型: consolidation/trending/ranging
• 情绪: bullish/bearish/neutral
• 叙述: [AI生成的市场描述]

🧠 主观判断
• 方向: long/short/neutral
• 置信度: 0-100%
• 辩论: [多空观点摘要]

📌 最终决策
• 行动: open_long / open_short / no_trade
• 原因: [开单参数或风控拦截原因]
```

---

## 五、风控体系

### 硬风控 (不可覆盖)

| 规则 | 限制值 |
|------|--------|
| 仓位上限 | 30% |
| 杠杆上限 | 10x |
| 单笔风险 | 0.5%-2% |
| 连续亏损 | 3次后暂停 |

### 软风控 (可配置)

- [ ] 市场状态过滤
- [ ] 置信度阈值
- [ ] 波动率限制
- [ ] 交易时段限制

---

## 六、部署架构

```
┌─────────────────────────────────────────────────────────┐
│                    云服务器 (Ubuntu)                      │
│                   43.167.232.83                         │
├─────────────────────────────────────────────────────────┤
│  Docker Container: btc-trading-agent                   │
│  ┌─────────────────────────────────────────────────────┐│
│  │  • Agent Core (Python 3.11)                        ││
│  │  • LLM Client (Tencent LKEAP)                      ││
│  │  • Exchange Client (OKX)                          ││
│  │  • Telegram Notifier                              ││
│  │  • Health Server (Port 8080)                      ││
│  └─────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────┤
│  Volumes:                                                │
│  • ./data    → /app/data   (SQLite + ChromaDB)         │
│  • ./logs    → /app/logs   (CoT日志)                   │
│  • ./reports → /app/reports (周报)                     │
└─────────────────────────────────────────────────────────┘
```

---

## 七、项目文件结构

```
btc-agent/
├── src/                          # 源代码 (21个Python文件)
│   ├── agent.py                  # 主程序入口
│   ├── perception/               # Phase 1: 市场感知
│   │   ├── data_fetcher.py      # 数据获取
│   │   ├── market_narrator.py   # 市场叙述生成
│   │   └── sentiment.py         # 情绪分析
│   ├── judgment/                # Phase 2: 主观判断
│   │   ├── debate_engine.py     # 辩论引擎
│   │   ├── regime_detector.py    # 状态检测
│   │   └── level_analyzer.py    # 价位分析
│   ├── decision/                 # Phase 3: 决策执行
│   │   ├── decision_engine.py    # 决策引擎
│   │   ├── position_calculator.py # 仓位计算
│   │   ├── risk_manager.py       # 风控管理
│   │   └── executor.py           # 订单执行
│   ├── memory/                   # Phase 4: 记忆系统
│   │   ├── trade_logger.py      # 交易记录
│   │   ├── vector_store.py       # 向量存储
│   │   └── review_engine.py      # 复盘引擎
│   ├── evolution/                # Phase 5: 自迭代
│   │   ├── meta_analyzer.py      # 元分析
│   │   ├── prompt_optimizer.py   # 提示词优化
│   │   └── distill_exporter.py   # 蒸馏导出
│   ├── exchange/                 # 交易所接口
│   │   ├── okx_client.py        # OKX客户端
│   │   ├── binance_client.py    # Binance客户端
│   │   └── exchange_factory.py  # 工厂模式
│   └── utils/                    # 工具模块
│       ├── llm_client.py        # LLM调用
│       ├── telegram_notifier.py  # Telegram通知
│       └── cot_logger.py         # CoT日志
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
│   └── remote-deploy.sh
├── tools/                        # 工具脚本
│   ├── monitor_agent.py          # 监控脚本
│   └── weekly_report.py          # 周报生成
├── data/                         # 数据存储
│   ├── trades.db                 # SQLite数据库
│   └── chroma_db/                # 向量数据库
├── logs/                         # 日志目录
│   ├── cot_perception/           # Phase1 CoT日志
│   ├── cot_judgment/             # Phase2 CoT日志
│   ├── cot_decision/             # Phase3 CoT日志
│   └── cot_review/               # Phase4 CoT日志
├── tests/                        # 测试文件
├── requirements.txt               # Python依赖
├── README.md                     # 项目说明
├── CLAUDE.md                     # 开发规范
├── DEVELOPMENT_LOG.md            # 开发记录
├── MODULE_STATUS.md              # 模块状态
└── PROJECT_SUMMARY.md            # 项目总结
```

---

## 八、运维指南

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

# 进入容器
docker exec -it btc-trading-agent bash
```

### 服务监控

| 监控项 | 端点 | 状态 |
|--------|------|------|
| HTTP健康检查 | `/health` | ✅ |
| Telegram通知 | Bot API | ✅ |
| 日志输出 | CoT文件 | ✅ |

---

## 九、五大风险消解机制

| 风险 | 消解方案 |
|------|----------|
| **LLM数学不可靠** | 认知与计算解耦，Python工具层执行精确计算 |
| **纯叙事无锚点** | 注入事实锚点（波动率/费率/OI布尔值） |
| **执行缺流动性** | 滑点保护、OCO订单、部分成交处理 |
| **辩论共识幻觉** | 差异化temperature、冲突度量化 |
| **长CoT低质量** | CoTValidator校验、低质量降级 |

---

## 十、GitHub仓库

- **地址**: https://github.com/BQstudy/BQstudy-btc-trading-agent-
- **分支**: main
- **语言**: Python 3.11

---

## 十一、后续优化方向

### 短期 (1-2周)
- [ ] 完善向量存储模块
- [ ] 测试Phase 5自迭代功能
- [ ] 添加更多风控指标

### 中期 (1-3月)
- [ ] 扩展支持ETH等其他币种
- [ ] 从纸面交易切换实盘
- [ ] 添加Web管理界面

### 长期 (3-6月)
- [ ] 多策略并行运行
- [ ] 机器学习辅助决策
- [ ] 社区策略分享机制

---

## 十二、关键成果

| 成果 | 状态 |
|------|------|
| 完整5阶段交易流程 | ✅ |
| 多角色AI辩论决策 | ✅ |
| 严格硬风控体系 | ✅ |
| Telegram实时通知 | ✅ |
| Docker容器化部署 | ✅ |
| HTTP健康监控 | ✅ |
| 完整CoT日志记录 | ✅ |

---

**项目状态**: 🟢 生产环境运行中
**最后更新**: 2026/04/09
