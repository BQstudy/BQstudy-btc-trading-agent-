"""
确定性仓位计算器 - Phase 3 核心模块
解决五大风险消解指南：风险1（LLM数学不可靠）
LLM仅声明意图，本模块执行精确计算
"""

from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class PositionValidationError(Exception):
    """仓位验证错误"""
    pass


@dataclass
class PositionResult:
    """仓位计算结果"""
    # 基础参数
    notional_usdt: float  # 名义价值
    leverage: int  # 实际杠杆倍数
    margin_usdt: float  # 实际保证金
    risk_amount_usdt: float  # 风险金额
    position_size_pct: float  # 仓位百分比

    # 派生参数
    quantity_btc: float  # 币数量
    entry_price: float  # 入场价格
    stop_loss: float  # 止损价格

    # 验证结果
    validation_passed: bool
    validation_errors: List[str]

    # 计算详情
    calculation_details: Dict


class PositionCalculator:
    """
    确定性仓位计算器
    所有涉及资金、杠杆、仓位、手续费的数值必须由本模块计算
    LLM仅声明"意图"，不输出"绝对值"
    """

    def __init__(self):
        self.fee_rate = Decimal("0.0004")  # 0.04% 双边手续费
        self.min_leverage = 1
        self.max_leverage = 10  # 可配置
        self.price_precision = 2  # 价格精度
        self.quantity_precision = 6  # 数量精度

    def calculate_position_size(
        self,
        account_usdt: float,
        entry_zone: List[float],
        stop_loss: float,
        risk_pct: float,
        leverage_cap: int = 10,
        confidence: float = 0.5,
        fee_rate: Optional[float] = None
    ) -> PositionResult:
        """
        计算精确仓位

        Args:
            account_usdt: 账户净值(USDT)
            entry_zone: 入场区间[低位, 高位]
            stop_loss: 止损价格
            risk_pct: 单笔风险比例(0.005~0.02)
            leverage_cap: 建议杠杆上限
            confidence: 置信度(影响仓位调整)
            fee_rate: 手续费率(可选)

        Returns:
            PositionResult对象
        """
        errors = []

        # 使用Decimal保证精度
        account = Decimal(str(account_usdt))
        entry_low = Decimal(str(entry_zone[0]))
        entry_high = Decimal(str(entry_zone[1])) if len(entry_zone) > 1 else entry_low
        entry_avg = (entry_low + entry_high) / 2
        sl = Decimal(str(stop_loss))
        risk = Decimal(str(risk_pct))
        fee = Decimal(str(fee_rate)) if fee_rate else self.fee_rate

        # 1. 基础验证
        if account <= 0:
            errors.append("账户净值必须大于0")
            return self._create_error_result(errors)

        if risk <= 0 or risk > Decimal("0.05"):
            errors.append("风险比例必须在0-5%之间")

        # 2. 计算风险金额
        risk_amount = account * risk

        # 3. 计算价格差（止损距离）
        price_diff = abs(entry_avg - sl)
        price_diff_pct = price_diff / entry_avg

        if price_diff == 0:
            errors.append("止损价格不能等于入场价格")
            return self._create_error_result(errors)

        # 4. 计算目标名义价值
        # 公式: notional = risk_amount / stop_distance_pct
        target_notional = risk_amount / price_diff_pct

        # 5. 计算最大允许的名义价值
        # 约束1: 杠杆限制 - notional <= account * leverage_cap
        # 约束2: 仓位限制 - margin <= account * 30%, margin = notional / leverage
        # 合并: notional <= min(account * leverage_cap, account * 0.3 * leverage_cap * leverage_cap) ???
        # 简化: margin = notional / leverage <= account * 0.3, 所以 notional <= account * 0.3 * leverage
        max_leverage = Decimal(str(leverage_cap))
        max_margin_pct = Decimal("0.30")  # 30%仓位上限

        # 两种限制取较小值
        max_notional_by_leverage = account * max_leverage
        max_notional_by_margin = account * max_margin_pct * max_leverage

        max_notional = min(max_notional_by_leverage, max_notional_by_margin)

        # 6. 使用较小的名义价值
        notional = min(target_notional, max_notional)

        # 7. 计算实际杠杆（使用最大允许杠杆来最小化保证金）
        leverage = max_leverage  # 始终使用最大杠杆
        leverage_int = int(max_leverage)

        # 实际保证金（扣除手续费）
        actual_margin = (notional / leverage) * (1 - fee * 2)

        # 8. 计算币数量
        quantity = notional / entry_avg

        # 9. 根据置信度调整
        # confidence > 0.8: 乘以1.2
        # confidence < 0.5: 乘以0.7
        confidence_adj = Decimal("1.0")
        if confidence > 0.8:
            confidence_adj = Decimal("1.2")
        elif confidence < 0.5:
            confidence_adj = Decimal("0.7")

        adjusted_notional = notional * confidence_adj
        adjusted_margin = actual_margin * confidence_adj
        adjusted_quantity = quantity * confidence_adj

        # 10. 重新验证仓位
        position_pct = float(adjusted_margin / account * 100)

        if position_pct > 30:
            errors.append(f"仓位占比{position_pct:.1f}%超过30%限制")

        if leverage_int > self.max_leverage:
            errors.append(f"杠杆{leverage_int}x超过最大限制{self.max_leverage}x")

        # 10. 返回结果
        return PositionResult(
            notional_usdt=float(adjusted_notional.quantize(Decimal("0.01"), rounding=ROUND_DOWN)),
            leverage=leverage_int,
            margin_usdt=float(adjusted_margin.quantize(Decimal("0.01"), rounding=ROUND_DOWN)),
            risk_amount_usdt=float(risk_amount.quantize(Decimal("0.01"), rounding=ROUND_DOWN)),
            position_size_pct=round(position_pct, 2),
            quantity_btc=float(adjusted_quantity.quantize(Decimal("0.000001"), rounding=ROUND_DOWN)),
            entry_price=float(entry_avg),
            stop_loss=float(sl),
            validation_passed=len(errors) == 0,
            validation_errors=errors,
            calculation_details={
                "entry_zone": entry_zone,
                "stop_loss": float(sl),
                "risk_pct": risk_pct,
                "confidence": confidence,
                "confidence_adjustment": float(confidence_adj),
                "price_diff_pct": float(price_diff / entry_avg * 100),
                "fee_rate": float(fee)
            }
        )

    def calculate_targets(
        self,
        entry_price: float,
        stop_loss: float,
        risk_reward_ratios: List[float] = [1.0, 1.5, 2.0]  # 盈亏比>=1:1即进行交易
    ) -> List[Dict]:
        """
        计算分批止盈目标

        Args:
            entry_price: 入场价格
            stop_loss: 止损价格
            risk_reward_ratios: 风险收益比列表

        Returns:
            目标价格列表
        """
        entry = Decimal(str(entry_price))
        sl = Decimal(str(stop_loss))

        # 计算止损距离
        stop_distance = abs(entry - sl)

        # 判断方向
        is_long = entry > sl

        targets = []
        size_pcts = [50, 30, 20]  # 分批止盈比例

        for i, rr in enumerate(risk_reward_ratios):
            if is_long:
                target_price = entry + stop_distance * Decimal(str(rr))
            else:
                target_price = entry - stop_distance * Decimal(str(rr))

            size_pct = size_pcts[i] if i < len(size_pcts) else 20

            targets.append({
                "price": float(target_price.quantize(Decimal("0.01"), rounding=ROUND_DOWN)),
                "size_pct": size_pct,
                "risk_reward_ratio": rr,
                "distance_pct": float(abs(target_price - entry) / entry * 100)
            })

        return targets

    def calculate_risk_metrics(
        self,
        position: PositionResult,
        account_usdt: float
    ) -> Dict:
        """
        计算风险指标
        """
        account = Decimal(str(account_usdt))

        # 最大亏损（理论）
        max_loss_pct = float(position.risk_amount_usdt / account_usdt * 100)

        # 实际杠杆倍数
        effective_leverage = position.notional_usdt / account_usdt

        # 爆仓价格估算（简化，实际需考虑维持保证金）
        liquidation_buffer = 0.15  # 15%缓冲
        liquidation_pct = 1 / position.leverage - liquidation_buffer

        if position.entry_price > position.stop_loss:  # 做多
            liquidation_price = position.entry_price * (1 - liquidation_pct)
        else:  # 做空
            liquidation_price = position.entry_price * (1 + liquidation_pct)

        # 止损与爆仓距离
        liquidation_distance = abs(liquidation_price - position.stop_loss) / position.stop_loss * 100

        return {
            "max_loss_pct": round(max_loss_pct, 2),
            "effective_leverage": round(effective_leverage, 2),
            "liquidation_price": round(liquidation_price, 2),
            "liquidation_distance_pct": round(liquidation_distance, 2),
            "safety_margin": "safe" if liquidation_distance > 10 else "warning" if liquidation_distance > 5 else "danger"
        }

    def validate_position_math(
        self,
        position: PositionResult,
        account_usdt: float
    ) -> Tuple[bool, List[str]]:
        """
        仓位数学验证器
        拦截器：验证所有计算结果
        """
        errors = []

        # 验证1: 仓位不超过账户30%
        if position.position_size_pct > 30:
            errors.append(f"仓位占比{position.position_size_pct}%超过30%限制")

        # 验证2: 杠杆不超过10x
        if position.leverage > 10:
            errors.append(f"杠杆{position.leverage}x超过10x限制")

        # 验证3: 风险金额不超过账户2%
        risk_pct = position.risk_amount_usdt / account_usdt * 100
        if risk_pct > 2.5:  # 允许一点容差
            errors.append(f"风险金额占比{risk_pct:.2f}%超过2%限制")

        # 验证4: 止损距离合理（至少0.3%）
        stop_distance_pct = abs(position.entry_price - position.stop_loss) / position.entry_price * 100
        if stop_distance_pct < 0.3:
            errors.append(f"止损距离{stop_distance_pct:.2f}%过小，建议至少0.3%")

        # 验证5: 数学一致性检查
        expected_margin = position.notional_usdt / position.leverage
        if abs(expected_margin - position.margin_usdt) > 1:
            errors.append(f"保证金计算不一致: 期望{expected_margin:.2f}, 实际{position.margin_usdt:.2f}")

        return len(errors) == 0, errors

    def _create_error_result(self, errors: List[str]) -> PositionResult:
        """创建错误结果"""
        return PositionResult(
            notional_usdt=0.0,
            leverage=1,
            margin_usdt=0.0,
            risk_amount_usdt=0.0,
            position_size_pct=0.0,
            quantity_btc=0.0,
            entry_price=0.0,
            stop_loss=0.0,
            validation_passed=False,
            validation_errors=errors,
            calculation_details={}
        )

    def recalculate_for_partial_fill(
        self,
        original_position: PositionResult,
        filled_quantity: float,
        filled_price: float
    ) -> PositionResult:
        """
        部分成交后重新计算仓位
        """
        fill_ratio = filled_quantity / original_position.quantity_btc

        return PositionResult(
            notional_usdt=original_position.notional_usdt * fill_ratio,
            leverage=original_position.leverage,
            margin_usdt=original_position.margin_usdt * fill_ratio,
            risk_amount_usdt=original_position.risk_amount_usdt * fill_ratio,
            position_size_pct=original_position.position_size_pct * fill_ratio,
            quantity_btc=filled_quantity,
            entry_price=filled_price,
            stop_loss=original_position.stop_loss,
            validation_passed=original_position.validation_passed,
            validation_errors=original_position.validation_errors,
            calculation_details={
                **original_position.calculation_details,
                "partial_fill": True,
                "fill_ratio": fill_ratio
            }
        )
