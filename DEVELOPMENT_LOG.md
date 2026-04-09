# BTC交易Agent开发记录

## 项目概述
基于LLM的主观判断交易Agent，支持OKX模拟盘交易。

**核心哲学**: AI simulates traders, not math. (让LLM模拟人的主观判断，而非数学近似市场)

---

## 开发时间线

### Phase 1: 项目初始化
- **时间**: 2026/04/09
- **内容**: 创建目录结构、配置文件、基础模块
- **文件**: `src/agent.py`, `config/settings.yaml`, `prompts/*.yaml`

### Phase 2: 市场感知层 (Perception)
- **文件**: `src/perception/data_fetcher.py`, `market_narrator.py`, `sentiment.py`
- **功能**: 获取市场数据、生成市场叙述、情绪分析
- **依赖**: ccxt (交易所API), Tencent Cloud LKEAP API

### Phase 3: 主观判断引擎 (Judgment)
- **文件**: `src/judgment/debate_engine.py`, `regime_detector.py`, `level_analyzer.py`
- **功能**: 多角色辩论(Bull/Bear/Neutral/Risk/Judge)、市场状态检测、关键价位分析

### Phase 4: 决策执行层 (Decision)
- **文件**: `src/decision/decision_engine.py`, `position_calculator.py`, `risk_manager.py`, `executor.py`
- **功能**: 仓位计算、风控管理、订单执行

### Phase 5: 记忆系统 (Memory)
- **文件**: `src/memory/trade_logger.py`, `vector_store.py`, `review_engine.py`
- **功能**: 交易记录、向量存储、复盘分析

### Phase 6: 自迭代引擎 (Evolution)
- **文件**: `src/evolution/meta_analyzer.py`, `prompt_optimizer.py`, `distill_exporter.py`
- **功能**: 元分析、提示词优化、蒸馏导出

---

## 关键Bug修复记录

### 1. 仓位计算错误 (Critical)
**问题**: 仓位显示1123%，远超30%限制
**原因**: 杠杆计算逻辑错误，未正确应用max_margin约束
**修复文件**: `src/decision/position_calculator.py`
**修复内容**:
```python
# 修复前: 错误计算
max_notional_by_margin = account * max_margin_pct * max_leverage

# 修复后: 正确计算
max_notional_by_leverage = account * max_leverage
max_notional_by_margin = account * max_margin_pct * max_leverage
max_notional = min(max_notional_by_leverage, max_notional_by_margin)
```
**验证结果**: 23%仓位，10x杠杆，通过所有风控检查

### 2. TradeLog接口不一致 (High)
**问题**: `trade_logger.py`使用`timestamp`字段，其他模块使用`entry_time`
**修复文件**: `src/memory/trade_logger.py`
**修复内容**:
```python
# 统一字段名
entry_time: Optional[str] = None
direction: str = ""  # long/short
entry_price: float = 0.0
exit_price: Optional[float] = None
pnl: Optional[float] = None
```

### 3. DebateEngine RegimeFlags处理错误 (High)
**问题**: `'RegimeFlags' object has no attribute 'get'`
**原因**: `_format_regime_flags`方法只处理Dict，不处理dataclass对象
**修复文件**: `src/judgment/debate_engine.py`
**修复内容**:
```python
def _format_regime_flags(self, flags) -> str:
    """格式化事实锚点 - 支持Dict或RegimeFlags对象"""
    # 处理dataclass对象
    if hasattr(flags, 'is_trending'):
        lines = [...]
    # 处理Dict
    elif isinstance(flags, dict):
        lines = [...]
```

### 4. OKX API订单参数缺失 (High)
**问题**: OKX下单失败，缺少`posSide`参数
**修复文件**: `src/exchange/okx_client.py`
**修复内容**:
```python
params = {
    'posSide': 'long' if side == 'buy' else 'short',
    'tdMode': 'cross',
}
```

### 5. Telegram通知模块完善 (Medium)
**文件**: `src/utils/telegram_notifier.py`
**功能**: 交易通知、风险警报、周期报告
**集成**: 在`agent.py`的`run_single_cycle`和`run_continuous`中添加通知调用

---

## API配置记录

### Tencent Cloud LKEAP (LLM)
- **base_url**: `https://api.lkeap.cloud.tencent.com/coding/v3`
- **model**: `kimi-k2.5`
- **注意**: 必须使用`/coding/v3`路径，不是`/v1`

### OKX Demo Trading
- **API Key**: `bedc2600-1879-416a-9375-3c7a6c594c50`
- **Secret**: `F68A63AA108E8B6BC20BA58BF327F6A2`
- **Passphrase**: `Bc887720.` (注意末尾有句号)
- **配置**: `sandbox: true`, `password`参数必须提供

### Telegram Bot
- 用于实时交易通知和警报
- 配置在`config/settings.yaml`中

---

## 测试记录

### 已测试模块
| 模块 | 状态 | 备注 |
|------|------|------|
| 仓位计算 | ✅ | 23%仓位，10x杠杆 |
| 风控管理 | ✅ | 拦截超额风险/杠杆/连续亏损 |
| 向量存储 | ✅ | add/search/summary功能正常 |
| 辩论质量 | ✅ | 多样性验证、矛盾检测 |
| 交易周期 | ✅ | Phase 1-3全流程 |

### 测试命令
```bash
# 单次纸面交易
python src/agent.py --paper --once

# 持续运行
python src/agent.py --paper --interval 3600
```

---

## 部署记录

### GitHub仓库
- **地址**: https://github.com/BQstudy/BQstudy-btc-trading-agent-
- **分支**: main
- **文件数**: 68个

### 云服务器部署
- **方式**: Docker + docker-compose
- **配置**: `deploy/docker-compose.yml`
- **命令**:
```bash
cd deploy
docker compose up -d
```

---

## 五大风险消解原则

1. **LLM数学不可靠** → 认知与计算解耦，Python工具层执行精确计算
2. **纯叙事无锚点** → 注入事实锚点（波动率/费率/OI布尔值）
3. **执行缺流动性** → 滑点保护、OCO订单、部分成交处理
4. **辩论共识幻觉** → 差异化temperature、冲突度量化
5. **长CoT低质量** → CoTValidator校验、低质量降级

---

## 后续修改快速参考

### 修改仓位计算逻辑
- **文件**: `src/decision/position_calculator.py`
- **关键类**: `PositionCalculator.calculate_position_size()`
- **约束**: 仓位≤30%，杠杆≤10x

### 修改风控规则
- **文件**: `src/decision/risk_manager.py`, `config/risk_rules.yaml`
- **关键类**: `RiskManager.validate_position()`

### 修改LLM提示词
- **目录**: `prompts/`
- **文件**: `perception_v1.yaml`, `judgment_v1.yaml`, `decision_v1.yaml`

### 修改交易所配置
- **文件**: `src/exchange/okx_client.py`, `config/settings.yaml`
- **注意**: OKX需要`posSide`参数

### 添加新通知类型
- **文件**: `src/utils/telegram_notifier.py`
- **集成点**: `src/agent.py`中的通知调用

---

## 注意事项

1. **硬风控不可覆盖**: 任何情况下都不能绕过风控限制
2. **日志即资产**: CoT完整保留，用于后续分析
3. **"不做交易"是最高级决策**: 没有明确信号时选择观望
4. **模拟盘优先**: 实盘交易前必须充分测试

---

*最后更新: 2026/04/09*
