"""
Phase 3 单元测试
测试决策执行层各模块功能
"""

import unittest
import sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from decision.position_calculator import PositionCalculator, PositionResult
from decision.risk_manager import RiskManager, AccountState, RiskLevel
from decision.executor import OrderRouter, SlippageGuard
from decision.decision_engine import DecisionEngine


class TestPositionCalculator(unittest.TestCase):
    """测试仓位计算器"""

    def setUp(self):
        self.calculator = PositionCalculator()

    def test_basic_calculation(self):
        """测试基础仓位计算"""
        # 使用更大的止损距离来降低仓位占比
        result = self.calculator.calculate_position_size(
            account_usdt=10000,
            entry_zone=[62000, 62500],
            stop_loss=60000,  # 更大的止损距离
            risk_pct=0.01,
            leverage_cap=10,
            confidence=0.7
        )

        self.assertIsInstance(result, PositionResult)
        self.assertTrue(result.validation_passed)
        self.assertGreater(result.notional_usdt, 0)
        self.assertGreater(result.margin_usdt, 0)

    def test_decimal_precision(self):
        """测试Decimal精度"""
        result = self.calculator.calculate_position_size(
            account_usdt=1000.123456,
            entry_zone=[60000.123, 60100.456],
            stop_loss=59500.789,
            risk_pct=0.015,
            leverage_cap=5
        )

        # 验证精度
        self.assertEqual(round(result.margin_usdt, 2), result.margin_usdt)
        self.assertEqual(round(result.notional_usdt, 2), result.notional_usdt)

    def test_confidence_adjustment(self):
        """测试置信度调整"""
        # 高置信度
        result_high = self.calculator.calculate_position_size(
            account_usdt=10000,
            entry_zone=[62000],
            stop_loss=61000,
            risk_pct=0.01,
            confidence=0.9  # > 0.8
        )

        # 低置信度
        result_low = self.calculator.calculate_position_size(
            account_usdt=10000,
            entry_zone=[62000],
            stop_loss=61000,
            risk_pct=0.01,
            confidence=0.4  # < 0.5
        )

        # 高置信度仓位应该更大
        self.assertGreater(result_high.margin_usdt, result_low.margin_usdt)

    def test_validation_errors(self):
        """测试验证错误"""
        # 止损等于入场价
        result = self.calculator.calculate_position_size(
            account_usdt=10000,
            entry_zone=[62000],
            stop_loss=62000,  # 相同
            risk_pct=0.01
        )

        self.assertFalse(result.validation_passed)
        self.assertTrue(len(result.validation_errors) > 0)

    def test_calculate_targets(self):
        """测试目标计算"""
        targets = self.calculator.calculate_targets(
            entry_price=62000,
            stop_loss=61000,
            risk_reward_ratios=[1.5, 2.5, 3.5]
        )

        self.assertEqual(len(targets), 3)
        self.assertIn("price", targets[0])
        self.assertIn("size_pct", targets[0])
        self.assertIn("risk_reward_ratio", targets[0])

    def test_risk_metrics(self):
        """测试风险指标"""
        position = self.calculator.calculate_position_size(
            account_usdt=10000,
            entry_zone=[62000],
            stop_loss=61000,
            risk_pct=0.01,
            leverage_cap=10
        )

        metrics = self.calculator.calculate_risk_metrics(position, 10000)

        self.assertIn("max_loss_pct", metrics)
        self.assertIn("liquidation_price", metrics)
        self.assertIn("safety_margin", metrics)


class TestRiskManager(unittest.TestCase):
    """测试风控管理器"""

    def setUp(self):
        self.risk_manager = RiskManager()

    def test_single_trade_loss_check(self):
        """测试单笔亏损检查"""
        account = AccountState(
            account_id="test",
            balance_usdt=10000,
            equity_usdt=10000,
            margin_used=0,
            margin_ratio=1.0,
            daily_pnl=0,
            daily_pnl_pct=0,
            total_pnl=0,
            consecutive_losses=0,
            max_drawdown_pct=0
        )

        decision = {"risk_amount_usdt": 150}  # 1.5%，应该通过
        passed, msg = self.risk_manager._check_single_trade_loss(decision, account)
        self.assertTrue(passed)

        decision = {"risk_amount_usdt": 300}  # 3%，应该失败
        passed, msg = self.risk_manager._check_single_trade_loss(decision, account)
        self.assertFalse(passed)

    def test_leverage_check(self):
        """测试杠杆检查"""
        decision = {"leverage": 8}  # 应该通过
        passed, msg = self.risk_manager._check_leverage(decision)
        self.assertTrue(passed)

        decision = {"leverage": 15}  # 应该失败
        passed, msg = self.risk_manager._check_leverage(decision)
        self.assertFalse(passed)

    def test_consecutive_losses(self):
        """测试连续亏损检查"""
        account = AccountState(
            account_id="test",
            balance_usdt=10000,
            equity_usdt=10000,
            margin_used=0,
            margin_ratio=1.0,
            daily_pnl=0,
            daily_pnl_pct=0,
            total_pnl=0,
            consecutive_losses=3,  # 达到限制
            max_drawdown_pct=0
        )

        passed, msg, action = self.risk_manager._check_consecutive_losses(account)
        self.assertFalse(passed)
        self.assertEqual(action, "pause_and_review")

    def test_max_drawdown(self):
        """测试最大回撤检查"""
        account = AccountState(
            account_id="test",
            balance_usdt=8500,
            equity_usdt=8500,
            margin_used=0,
            margin_ratio=1.0,
            daily_pnl=0,
            daily_pnl_pct=0,
            total_pnl=-1500,
            consecutive_losses=0,
            max_drawdown_pct=15  # 达到限制
        )

        passed, msg = self.risk_manager._check_max_drawdown(account)
        self.assertFalse(passed)

    def test_full_check(self):
        """测试完整风控检查"""
        account = AccountState(
            account_id="test",
            balance_usdt=10000,
            equity_usdt=10000,
            margin_used=0,
            margin_ratio=1.0,
            daily_pnl=0,
            daily_pnl_pct=0,
            total_pnl=0,
            consecutive_losses=0,
            max_drawdown_pct=0
        )

        decision = {
            "risk_amount_usdt": 100,  # 1%
            "leverage": 5,
            "margin_usdt": 500
        }

        result = self.risk_manager.check_all(decision, account)

        self.assertTrue(result.passed)
        self.assertEqual(result.risk_level, RiskLevel.LOW)
        self.assertEqual(result.action, "allow")


class TestExecutor(unittest.TestCase):
    """测试执行器"""

    def setUp(self):
        self.router = OrderRouter()
        self.guard = SlippageGuard()

    def test_slippage_check(self):
        """测试滑点检查"""
        # 正常滑点
        ok, msg = self.guard.check_slippage(62000, 62100, "buy")
        self.assertTrue(ok)

        # 滑点过大
        ok, msg = self.guard.check_slippage(62000, 65000, "buy")
        self.assertFalse(ok)

    def test_route_order_liquid(self):
        """测试流动性充足时的路由"""
        decision = {
            "notional_usdt": 1000,
            "entry_zone": [62000],
            "targets": [{"price": 63000}],
            "stop_loss": 61000
        }

        orderbook = {
            "bid_depth_usdt": 50000,  # 深度充足
            "spread_pct": 0.0005  # 0.05%价差
        }

        plan = self.router.route_order(decision, orderbook)

        self.assertIsNotNone(plan)
        self.assertLess(plan.slippage_tolerance, 0.01)

    def test_route_order_illiquid(self):
        """测试流动性不足时的路由"""
        decision = {
            "notional_usdt": 10000,
            "entry_zone": [62000]
        }

        orderbook = {
            "bid_depth_usdt": 5000,  # 深度不足
            "spread_pct": 0.002  # 0.2%价差
        }

        plan = self.router.route_order(decision, orderbook)

        # 应该使用保守策略
        self.assertIsNotNone(plan)


class TestDecisionEngine(unittest.TestCase):
    """测试决策引擎"""

    def setUp(self):
        self.engine = DecisionEngine()

    def test_no_trade_low_confidence(self):
        """测试低置信度不交易"""
        judgment = {
            "final_judgment": {
                "bias": "bullish",
                "confidence": 0.3  # 低置信度
            }
        }

        account = AccountState(
            account_id="test",
            balance_usdt=10000,
            equity_usdt=10000,
            margin_used=0,
            margin_ratio=1.0,
            daily_pnl=0,
            daily_pnl_pct=0,
            total_pnl=0,
            consecutive_losses=0,
            max_drawdown_pct=0
        )

        decision = self.engine.make_decision(
            judgment_result=judgment,
            perception_output={},
            account_state=account,
            market_data={"current_price": 62000}
        )

        self.assertEqual(decision.action, "no_trade")
        self.assertIn("置信度", decision.reason_for_no_trade)

    def test_entry_zone_determination(self):
        """测试入场区间确定"""
        perception = {
            "key_support": [60000, 58000],
            "key_resistance": [64000, 66000]
        }

        judgment = {
            "final_judgment": {"bias": "bullish"}
        }

        market = {"current_price": 62000}

        entry_zone = self.engine._determine_entry_zone(perception, judgment, market)

        self.assertEqual(len(entry_zone), 2)
        self.assertLess(entry_zone[0], entry_zone[1])

    def test_stop_loss_determination(self):
        """测试止损确定"""
        perception = {
            "key_support": [60000, 58000]
        }

        entry_zone = [62000, 62500]

        stop = self.engine._determine_stop_loss(perception, {}, entry_zone, "long")

        self.assertLess(stop, entry_zone[0])  # 止损在入场价下方


if __name__ == "__main__":
    unittest.main()
