# BTC永续合约拟人化交易Agent

## 项目概述
让LLM模拟人的主观判断，而非数学近似市场。AI simulates traders, not math.

## 开发进度

- [x] 项目初始化（目录结构创建）
- [x] Phase 1: 市场感知层 Market Perception ← 完成
- [x] Phase 2: 主观判断引擎 Judgment Engine ← 完成
- [x] Phase 3: 决策执行层 Decision Execution ← 完成
- [x] Phase 4: 记忆经验系统 Memory System ← 完成
- [x] Phase 5: 自我迭代引擎 Self-Evolution ← 完成

## 核心哲学（五大风险消解）

1. **LLM数学不可靠** → 认知与计算解耦，Python工具层执行精确计算
2. **纯叙事无锚点** → 注入事实锚点（波动率/费率/OI布尔值）
3. **执行缺流动性** → 滑点保护、OCO订单、部分成交处理
4. **辩论共识幻觉** → 差异化temperature、冲突度量化
5. **长CoT低质量** → CoTValidator校验、低质量降级

## 开发纪律

- LLM不碰确定性计算，所有数值由Python工具层
- "不做交易"是最高级决策
- 硬风控不可覆盖
- 日志即资产，CoT完整保留

## 项目结构

```
btc-agent/
├── src/
│   ├── perception/          # Phase 1
│   │   ├── data_fetcher.py
│   │   ├── market_narrator.py
│   │   └── sentiment.py
│   ├── judgment/            # Phase 2
│   │   ├── debate_engine.py
│   │   ├── regime_detector.py
│   │   └── level_analyzer.py
│   ├── decision/            # Phase 3
│   │   ├── decision_engine.py
│   │   ├── risk_manager.py
│   │   ├── position_calculator.py
│   │   └── executor.py
│   ├── memory/              # Phase 4
│   │   ├── trade_logger.py
│   │   ├── review_engine.py
│   │   └── vector_store.py
│   └── evolution/           # Phase 5
│       ├── meta_analyzer.py
│       ├── prompt_optimizer.py
│       └── distill_exporter.py
├── prompts/
│   ├── perception_v1.yaml
│   ├── judgment_v1.yaml
│   ├── decision_v1.yaml
│   ├── review_v1.yaml
│   └── evolution_v1.yaml
├── logs/
│   ├── cot_perception/
│   ├── cot_judgment/
│   ├── cot_decision/
│   └── cot_review/
├── data/
│   ├── trades.db
│   └── chroma_db/
├── config/
│   ├── settings.yaml
│   └── risk_rules.yaml
├── tools/
│   ├── cot_viewer.py
│   └── export_distillation_dataset.py
└── tests/
```

## 外部依赖

- 交易所: Binance / OKX Futures API (ccxt库)
- LLM: Anthropic Claude API
- 向量库: Chroma DB 或 Qdrant
- 数据库: SQLite
- 部署: 云服务器 + 网站集成
