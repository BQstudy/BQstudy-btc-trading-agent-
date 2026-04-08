"""
决策引擎 - Phase 3 核心
将判断引擎的主观结论转化为具体的、可执行的交易指令
"""

import json
import uuid
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .position_calculator import PositionCalculator, PositionResult
from .risk_manager import RiskManager, AccountState, RiskCheckResult
from .executor import ExchangeExecutor, ExecutionPlan


@dataclass
class DecisionOutput:
    """决策输出数据结构"""
    call_id: str
    timestamp: str
    phase: str = "decision"

    # 决策内容
    action: str = "no_trade"  # long/short/no_trade
    reason_for_no_trade: str = ""

    # 入场参数
    entry_zone: List[float] = field(default_factory=list)
    trigger_condition: str = ""

    # 风控参数
    stop_loss: float = 0.0
    stop_invalidation_reason: str = ""
    targets: List[Dict] = field(default_factory=list)

    # 仓位参数
    position_size_pct: float = 0.0
    leverage: int = 1
    confidence: float = 0.0
    risk_reward_ratio: float = 0.0

    # 计算详情
    position_result: Optional[PositionResult] = None
    risk_check: Optional[RiskCheckResult] = None

    # 执行计划
    execution_plan: Optional[ExecutionPlan] = None

    # 风控检查
    risk_check_passed: bool = False
    risk_check_details: Dict = field(default_factory=dict)

    # 思维链
    chain_of_thought: str = ""

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "call_id": self.call_id,
            "timestamp": self.timestamp,
            "phase": self.phase,
            "decision": {
                "action": self.action,
                "reason_for_no_trade": self.reason_for_no_trade,
                "entry_zone": self.entry_zone,
                "trigger_condition": self.trigger_condition,
                "stop_loss": self.stop_loss,
                "stop_invalidation_reason": self.stop_invalidation_reason,
                "targets": self.targets,
                "position_size_pct": self.position_size_pct,
                "leverage": self.leverage,
                "confidence": self.confidence,
                "risk_reward_ratio": self.risk_reward_ratio
            },
            "risk_check_passed": self.risk_check_passed,
            "risk_check_details": self.risk_check_details if self.risk_check else {},
            "position_calculation": self.position_result.__dict__ if self.position_result else None
        }


class DecisionEngine:
    """
    决策引擎
    整合仓位计算、风控检查、执行计划
    """

    def __init__(
        self,
        position_calculator: Optional[PositionCalculator] = None,
        risk_manager: Optional[RiskManager] = None,
        executor: Optional[ExchangeExecutor] = None
    ):
        self.position_calculator = position_calculator or PositionCalculator()
        self.risk_manager = risk_manager or RiskManager()
        self.executor = executor or ExchangeExecutor()

    def make_decision(
        self,
        judgment_result: Dict,
        perception_output: Dict,
        account_state: AccountState,
        market_data: Dict
    ) -> DecisionOutput:
        """
        做出交易决策

        Args:
            judgment_result: 判断引擎输出
            perception_output: 感知层输出
            account_state: 账户状态
            market_data: 市场数据

        Returns:
            DecisionOutput对象
        """
        call_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"

        decision = DecisionOutput(
            call_id=call_id,
            timestamp=timestamp
        )

        # 1. 提取判断结果
        final_judgment = judgment_result.get("final_judgment", {})
        bias = final_judgment.get("bias", "neutral")
        confidence = final_judgment.get("confidence", 0.5)

        # 2. 交易资格审查
        if not self._check_trade_eligibility(judgment_result, account_state):
            decision.action = "no_trade"
            decision.reason_for_no_trade = self._get_no_trade_reason(judgment_result, account_state)
            decision.confidence = confidence
            return decision

        # 3. 方向选择
        if bias == "neutral" or confidence < 0.4:
            decision.action = "no_trade"
            decision.reason_for_no_trade = f"方向不明或置信度{confidence}过低"
            decision.confidence = confidence
            return decision

        decision.action = "long" if bias == "bullish" else "short"
        decision.confidence = confidence

        # 4. 入场计划
        entry_zone = self._determine_entry_zone(
            perception_output,
            judgment_result,
            market_data
        )
        decision.entry_zone = entry_zone
        decision.trigger_condition = self._determine_trigger_condition(judgment_result)

        # 5. 止损设置
        stop_loss = self._determine_stop_loss(
            perception_output,
            judgment_result,
            entry_zone,
            decision.action
        )
        decision.stop_loss = stop_loss
        decision.stop_invalidation_reason = final_judgment.get("key_invalidation", "")

        # 6. 目标管理
        targets = self.position_calculator.calculate_targets(
            entry_price=entry_zone[0] if entry_zone else 0,
            stop_loss=stop_loss
        )
        decision.targets = targets

        # 计算风险收益比
        if targets:
            decision.risk_reward_ratio = targets[0]["risk_reward_ratio"]

        # 7. 仓位计算（Python工具层，LLM不碰）
        position_result = self.position_calculator.calculate_position_size(
            account_usdt=account_state.equity_usdt,
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            risk_pct=0.02,  # 默认2%
            leverage_cap=10,
            confidence=confidence
        )
        decision.position_result = position_result

        if not position_result.validation_passed:
            decision.action = "no_trade"
            decision.reason_for_no_trade = f"仓位计算失败: {', '.join(position_result.validation_errors)}"
            return decision

        decision.position_size_pct = position_result.position_size_pct
        decision.leverage = position_result.leverage

        # 8. 风控检查
        decision_params = {
            "risk_amount_usdt": position_result.risk_amount_usdt,
            "leverage": position_result.leverage,
            "margin_usdt": position_result.margin_usdt,
            "notional_usdt": position_result.notional_usdt
        }

        risk_check = self.risk_manager.check_all(decision_params, account_state)
        decision.risk_check = risk_check
        decision.risk_check_passed = risk_check.passed
        decision.risk_check_details = risk_check.details

        if not risk_check.passed:
            decision.action = "no_trade"
            decision.reason_for_no_trade = f"风控拦截: {', '.join(risk_check.violations)}"
            return decision

        # 9. 执行计划
        execution_plan = self.executor.route_order({
            **decision_params,
            "entry_zone": entry_zone,
            "targets": targets,
            "stop_loss": stop_loss,
            "side": "buy" if decision.action == "long" else "sell"
        }, market_data.get("orderbook"))
        decision.execution_plan = execution_plan

        # 10. 生成思维链
        decision.chain_of_thought = self._generate_chain_of_thought(decision)

        return decision

    def _check_trade_eligibility(
        self,
        judgment_result: Dict,
        account_state: AccountState
    ) -> bool:
        """检查交易资格"""
        final_judgment = judgment_result.get("final_judgment", {})

        # 检查置信度
        if final_judgment.get("confidence", 0) < 0.4:
            return False

        # 检查行情性质
        regime = judgment_result.get("market_regime", "uncertain")
        if regime == "uncertain":
            return False

        # 检查连续亏损
        if account_state.consecutive_losses >= 3:
            return False

        return True

    def _get_no_trade_reason(
        self,
        judgment_result: Dict,
        account_state: AccountState
    ) -> str:
        """获取不交易的原因"""
        reasons = []

        final_judgment = judgment_result.get("final_judgment", {})
        if final_judgment.get("confidence", 0) < 0.4:
            reasons.append("置信度不足")

        regime = judgment_result.get("market_regime", "uncertain")
        if regime == "uncertain":
            reasons.append("行情性质不明")

        if account_state.consecutive_losses >= 3:
            reasons.append("连续亏损暂停")

        return "; ".join(reasons) if reasons else "不符合交易条件"

    def _determine_entry_zone(
        self,
        perception_output: Dict,
        judgment_result: Dict,
        market_data: Dict
    ) -> List[float]:
        """确定入场区间 - 确保与止损有合理距离"""
        # 从支撑压力分析获取
        supports = perception_output.get("key_supports", perception_output.get("key_support", []))
        resistances = perception_output.get("key_resistances", perception_output.get("key_resistance", []))

        current_price = market_data.get("current_price", 0)
        if current_price == 0:
            return []

        final_judgment = judgment_result.get("final_judgment", {})
        bias = final_judgment.get("bias", "neutral")

        # 最小止损距离1%，入场点至少要比止损远1%
        min_entry_distance_pct = 0.02  # 2%

        if bias == "bullish":
            # 做多：入场在支撑附近，但确保与止损有2%以上距离
            if supports:
                support = supports[0]
                # 入场价格 = 支撑位附近
                entry = support * 1.0  # 支撑位
                # 止损至少在入场下方2%
                stop = entry * (1 - min_entry_distance_pct)
                # 如果第二支撑比这个位置更低，用第二支撑作为止损
                if len(supports) >= 2 and supports[1] < stop:
                    stop = supports[1] * 0.99

                entry_zone = [entry * 0.995, entry * 1.005]  # ±0.5%
            else:
                # 没有支撑位时，在当前价下方1%入场
                entry = current_price * 0.99
                stop = current_price * (1 - min_entry_distance_pct)
                entry_zone = [current_price * 0.985, current_price * 0.995]

            return entry_zone
        else:
            # 做空：入场在压力位附近，但确保与止损有2%以上距离
            if resistances:
                resistance = resistances[0]
                entry = resistance * 1.0
                stop = entry * (1 + min_entry_distance_pct)
                if len(resistances) >= 2 and resistances[1] > stop:
                    stop = resistances[1] * 1.01

                entry_zone = [resistance * 0.995, resistance * 1.005]
            else:
                entry = current_price * 1.01
                stop = current_price * (1 + min_entry_distance_pct)
                entry_zone = [current_price * 1.005, current_price * 1.015]

            return entry_zone

    def _determine_trigger_condition(self, judgment_result: Dict) -> str:
        """确定触发条件"""
        final_judgment = judgment_result.get("final_judgment", {})
        bias = final_judgment.get("bias", "neutral")

        if bias == "bullish":
            return "价格触及支撑位并出现反弹信号（如锤头、吞没形态）"
        else:
            return "价格触及压力位并出现回落信号（如流星线、吞没形态）"

    def _determine_stop_loss(
        self,
        perception_output: Dict,
        judgment_result: Dict,
        entry_zone: List[float],
        action: str
    ) -> float:
        """确定止损价格 - 平衡风险控制和仓位合理性"""
        # 基于结构设置止损
        supports = perception_output.get("key_supports", perception_output.get("key_support", []))
        resistances = perception_output.get("key_resistances", perception_output.get("key_resistance", []))

        entry_price = entry_zone[0] if entry_zone else 0
        if entry_price == 0:
            return 0

        # 目标止损距离：0.5%-1.5%
        # - 太小：仓位过大，超过30%限制
        # - 太大：单次亏损过大
        target_stop_distance_pct = 0.008  # 0.8%

        if action == "long":
            # 做多止损：在支撑位下方，但距离控制在0.8%左右
            if supports:
                # 理想止损位置
                ideal_stop = entry_price * (1 - target_stop_distance_pct)
                # 如果支撑位比理想位置更低，用支撑位
                support_stop = supports[0] * 0.995
                # 取两者中较高的（距离入场更近的）
                stop = max(ideal_stop, support_stop)
            else:
                stop = entry_price * (1 - target_stop_distance_pct)

            return stop

        else:
            # 做空止损：在压力位上方，但距离控制在0.8%左右
            if resistances:
                ideal_stop = entry_price * (1 + target_stop_distance_pct)
                resistance_stop = resistances[0] * 1.005
                stop = min(ideal_stop, resistance_stop)
            else:
                stop = entry_price * (1 + target_stop_distance_pct)

            return stop

    def _generate_chain_of_thought(self, decision: DecisionOutput) -> str:
        """生成思维链"""
        lines = [
            "【Step 1: 交易资格审查】",
            f"  - 行情性质：{decision.action}",
            f"  - 置信度：{decision.confidence}",
            "  → 结论：通过" if decision.action != "no_trade" else "  → 结论：不交易",
            "",
            "【Step 2: 方向选择】",
            f"  - 方向：{decision.action}",
            "",
            "【Step 3: 入场计划】",
            f"  - 入场区间：{decision.entry_zone}",
            f"  - 触发条件：{decision.trigger_condition}",
            "",
            "【Step 4: 止损设置】",
            f"  - 止损价格：{decision.stop_loss}",
            f"  - 失效条件：{decision.stop_invalidation_reason}",
            "",
            "【Step 5: 目标管理】",
        ]

        for i, target in enumerate(decision.targets):
            lines.append(f"  - 目标{i+1}：{target['price']} ({target['size_pct']}%仓位, RR={target['risk_reward_ratio']})")

        lines.extend([
            "",
            "【Step 6: 仓位计算】",
            f"  - 仓位占比：{decision.position_size_pct}%",
            f"  - 杠杆：{decision.leverage}x",
            f"  - 风险收益比：{decision.risk_reward_ratio}",
            "",
            "【风控检查】",
            f"  - 通过：{decision.risk_check_passed}",
        ])

        if decision.risk_check and not decision.risk_check.passed:
            lines.append(f"  - 违规：{', '.join(decision.risk_check.violations)}")

        return "\n".join(lines)
