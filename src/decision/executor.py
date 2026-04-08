"""
订单执行器 - Phase 3 执行层
解决五大风险消解指南：风险3（执行缺流动性）
包含流动性感知、滑点保护、部分成交处理、OCO订单
"""

import time
import uuid
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    LIMIT_POST_ONLY = "limit_post_only"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"
    OCO = "oco"  # One Cancels Other


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ExecutionMode(Enum):
    """执行模式"""
    DIRECT = "direct"  # 直接执行
    TWAP = "twap"  # 时间加权平均
    ICEBERG = "iceberg"  # 冰山订单


@dataclass
class OrderParams:
    """订单参数"""
    symbol: str
    side: str  # buy/sell
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None

    # 高级参数
    reduce_only: bool = False
    post_only: bool = False

    # OCO参数
    oco_orders: Optional[List[Dict]] = None


@dataclass
class OrderResult:
    """订单执行结果"""
    order_id: str
    status: OrderStatus
    filled_quantity: float
    filled_price: float
    average_price: float
    commission: float

    # 详细信息
    message: str
    raw_response: Optional[Dict] = None


@dataclass
class ExecutionPlan:
    """执行计划"""
    order_type: OrderType
    execution_mode: ExecutionMode

    # 滑点保护
    slippage_tolerance: float = 0.003  # 0.3%
    max_slippage: float = 0.005  # 0.5%

    # 执行参数
    time_horizon: str = "immediate"  # immediate/15m/1h
    split_orders: int = 1  # 分单数量

    # OCO参数
    oco_params: Optional[Dict] = None

    # 风险管理
    max_slippage_action: str = "cancel"  # cancel/retry/accept


class SlippageGuard:
    """
    滑点保护器
    实际成交价偏离计划价超过阈值时自动处理
    """

    def __init__(self, tolerance: float = 0.003, max_slippage: float = 0.005):
        self.tolerance = tolerance  # 可接受滑点
        self.max_slippage = max_slippage  # 最大容忍滑点

    def check_slippage(
        self,
        expected_price: float,
        actual_price: float,
        side: str
    ) -> Tuple[bool, str]:
        """
        检查滑点是否在可接受范围

        Returns:
            (是否通过, 消息)
        """
        if side.lower() == "buy":
            # 买入时，实际价格不应高于预期
            slippage = (actual_price - expected_price) / expected_price
        else:
            # 卖出时，实际价格不应低于预期
            slippage = (expected_price - actual_price) / expected_price

        if slippage > self.max_slippage:
            return False, f"滑点{slippage*100:.2f}%超过最大容忍{self.max_slippage*100:.2f}%，订单已取消"

        if slippage > self.tolerance:
            return False, f"滑点{slippage*100:.2f}%超过容忍{self.tolerance*100:.2f}%，建议重试"

        return True, f"滑点{slippage*100:.3f}%在范围内"

    def calculate_adjusted_price(
        self,
        base_price: float,
        side: str,
        safety_margin: float = 0.001
    ) -> float:
        """计算调整后的价格（预留安全边际）"""
        if side.lower() == "buy":
            return base_price * (1 + safety_margin)
        else:
            return base_price * (1 - safety_margin)


class PartialFillHandler:
    """
    部分成交处理器
    状态机跟踪订单执行过程
    """

    def __init__(self):
        self.state = OrderStatus.PENDING

    def handle_partial_fill(
        self,
        original_order: OrderParams,
        filled_qty: float,
        remaining_qty: float,
        current_price: float
    ) -> Dict:
        """
        处理部分成交

        Returns:
            处理决策（继续/取消/调整）
        """
        fill_ratio = filled_qty / original_order.quantity

        # 状态更新
        if fill_ratio >= 0.5:
            self.state = OrderStatus.PARTIALLY_FILLED
            # 大部分成交，可以考虑取消剩余
            decision = {
                "action": "consider_cancel",
                "reason": "已成交超过50%",
                "filled_ratio": fill_ratio
            }
        else:
            self.state = OrderStatus.PARTIALLY_FILLED
            # 继续等待成交
            decision = {
                "action": "continue",
                "reason": "等待剩余成交",
                "filled_ratio": fill_ratio
            }

        # 重新计算仓位
        # 如果部分成交，需要重新评估风险
        if decision["action"] == "continue" and remaining_qty > 0:
            # 检查时间或价格条件是否仍然有效
            decision["remaining_valid"] = True

        return decision


class OrderRouter:
    """
    流动性感知订单路由器
    根据市场状态动态选择执行策略
    """

    def __init__(self):
        self.slippage_guard = SlippageGuard()
        self.partial_handler = PartialFillHandler()

        # 流动性阈值
        self.min_depth_ratio = 3.0  # 深度至少是订单金额的3倍
        self.max_spread_pct = 0.001  # 最大价差0.1%

    def route_order(
        self,
        decision: Dict,
        orderbook: Optional[Dict] = None
    ) -> ExecutionPlan:
        """
        根据市场状态路由订单

        Args:
            decision: 决策输出（包含entry_zone, stop_loss, notional_usdt等）
            orderbook: 订单簿数据

        Returns:
            ExecutionPlan对象
        """
        # 默认参数
        notional = decision.get("notional_usdt", 0)
        entry_zone = decision.get("entry_zone", [])
        side = decision.get("side", "buy")

        # 默认计划
        plan = ExecutionPlan(
            order_type=OrderType.LIMIT,
            execution_mode=ExecutionMode.DIRECT,
            slippage_tolerance=0.003,
            max_slippage=0.005,
            time_horizon="immediate",
            split_orders=1,
            max_slippage_action="cancel"
        )

        # 如果没有订单簿数据，使用保守策略
        if not orderbook:
            plan.order_type = OrderType.LIMIT_POST_ONLY
            return plan

        # 分析流动性
        depth_usdt = orderbook.get("bid_depth_usdt", 0) if side == "buy" else orderbook.get("ask_depth_usdt", 0)
        spread_pct = orderbook.get("spread_pct", 0)
        depth_ratio = depth_usdt / notional if notional > 0 else 0

        # 流动性不足时
        if depth_ratio < self.min_depth_ratio or spread_pct > self.max_spread_pct:
            # 保守执行：使用限价+只挂单
            plan.order_type = OrderType.LIMIT_POST_ONLY
            plan.execution_mode = ExecutionMode.TWAP
            plan.time_horizon = "15m"  # 15分钟TWAP窗口

            # 如果流动性极差
            if depth_ratio < 1.5:
                plan.split_orders = 5  # 分5单执行

        # 生成OCO参数（止盈止损）
        if decision.get("targets") and decision.get("stop_loss"):
            plan.oco_params = self._build_oco_params(decision)

        return plan

    def _build_oco_params(self, decision: Dict) -> Dict:
        """构建OCO订单参数"""
        targets = decision.get("targets", [])
        stop_loss = decision.get("stop_loss")

        oco = {
            "stop_loss": stop_loss,
            "take_profit_1": targets[0]["price"] if len(targets) > 0 else None,
            "take_profit_2": targets[1]["price"] if len(targets) > 1 else None,
            "stop_trigger": "last_price"  # 使用最新价触发
        }

        return oco


class ExchangeExecutor:
    """
    交易所执行器
    封装交易所API调用
    """

    def __init__(self, exchange_id: str = "binance"):
        self.exchange_id = exchange_id
        self.router = OrderRouter()
        self.order_tracker: Dict[str, OrderStatus] = {}

    def route_order(
        self,
        decision: Dict,
        orderbook: Optional[Dict] = None
    ) -> ExecutionPlan:
        """
        根据市场状态路由订单

        Args:
            decision: 决策输出
            orderbook: 订单簿数据

        Returns:
            ExecutionPlan对象
        """
        # 委托给router处理
        return self.router.route_order(decision, orderbook)

    def execute(
        self,
        decision: Dict,
        account_state: Dict,
        orderbook: Optional[Dict] = None
    ) -> OrderResult:
        """
        执行订单

        Args:
            decision: 决策输出
            account_state: 账户状态
            orderbook: 订单簿数据

        Returns:
            OrderResult对象
        """
        # 1. 路由订单
        plan = self.router.route_order(decision, orderbook)

        # 2. 构建订单参数
        order_params = self._build_order_params(decision, plan)

        # 3. 执行订单
        result = self._submit_order(order_params, decision.get("side", "buy"))

        # 4. 处理部分成交
        if result.status == OrderStatus.PARTIALLY_FILLED:
            self._handle_partial(result, order_params)

        # 5. 检查滑点
        if result.status == OrderStatus.FILLED:
            slippage_ok, msg = self.router.slippage_guard.check_slippage(
                order_params.price or 0,
                result.average_price,
                order_params.side
            )
            result.message += f" | {msg}"

        return result

    def _build_order_params(self, decision: Dict, plan: ExecutionPlan) -> OrderParams:
        """构建订单参数"""
        entry_zone = decision.get("entry_zone", [])
        side = decision.get("side", "buy")

        # 使用区间中点作为限价
        if len(entry_zone) >= 2:
            price = (entry_zone[0] + entry_zone[1]) / 2
        elif len(entry_zone) == 1:
            price = entry_zone[0]
        else:
            price = None

        return OrderParams(
            symbol=decision.get("symbol", "BTC/USDT:USDT"),
            side=side,
            order_type=plan.order_type,
            quantity=decision.get("quantity_btc", 0),
            price=price,
            stop_price=decision.get("stop_loss"),
            reduce_only=False,
            post_only=plan.order_type == OrderType.LIMIT_POST_ONLY
        )

    def _submit_order(
        self,
        params: OrderParams,
        side: str
    ) -> OrderResult:
        """
        提交订单到交易所
        实际实现需要接入ccxt或交易所SDK
        """
        order_id = str(uuid.uuid4())

        # 这里应该调用实际的交易所API
        # 模拟返回
        return OrderResult(
            order_id=order_id,
            status=OrderStatus.FILLED,
            filled_quantity=params.quantity,
            filled_price=params.price or 0,
            average_price=params.price or 0,
            commission=params.quantity * (params.price or 0) * 0.0004,
            message="订单已成交",
            raw_response=None
        )

    def _handle_partial(self, result: OrderResult, params: OrderParams):
        """处理部分成交"""
        decision = self.router.partial_handler.handle_partial_fill(
            params,
            result.filled_quantity,
            params.quantity - result.filled_quantity,
            result.average_price
        )

        if decision["action"] == "consider_cancel":
            # 取消剩余订单
            self.cancel_order(result.order_id)

    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        # 实现取消逻辑
        self.order_tracker[order_id] = OrderStatus.CANCELED
        return True

    def get_order_status(self, order_id: str) -> OrderStatus:
        """查询订单状态"""
        return self.order_tracker.get(order_id, OrderStatus.UNKNOWN)

    def cancel_all_orders(self, symbol: str) -> int:
        """取消所有挂单"""
        # 实现批量取消
        return 0
