"""
Phase 5 单元测试
测试自我迭代引擎各模块功能
"""

import unittest
import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evolution.meta_analyzer import MetaAnalyzer, PerformanceMetrics
from evolution.prompt_optimizer import PromptOptimizer, generate_optimization_prompt
from evolution.distill_exporter import DistillExporter, CoTValidator
from memory.trade_logger import TradeLogger, TradeLog


class TestMetaAnalyzer(unittest.TestCase):
    """测试元分析器"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_trades.db")
        self.logger = TradeLogger(self.db_path)
        self.analyzer = MetaAnalyzer(self.logger)

        # 创建测试数据
        self._create_test_trades()

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass

    def _create_test_trades(self):
        """创建测试交易数据"""
        outcomes = ["win", "win", "loss", "win", "loss"]
        directions = ["long", "long", "short", "long", "short"]

        for i, (outcome, direction) in enumerate(zip(outcomes, directions)):
            trade = TradeLog(
                trade_id=f"meta-test-{i}",
                entry_time=datetime.utcnow().isoformat() + "Z",
                direction=direction,
                entry_price=62000,
                quantity=0.1,
                margin_usdt=1000,
                leverage=10,
                market_type="trend_up" if i % 2 == 0 else "range"
            )
            self.logger.log_trade_entry(trade)
            self.logger.log_trade_exit(
                trade_id=f"meta-test-{i}",
                exit_price=64000 if outcome == "win" else 60000,
                exit_time=datetime.utcnow().isoformat() + "Z",
                outcome=outcome,
                pnl_usdt=200 if outcome == "win" else -200,
                pnl_pct=20 if outcome == "win" else -20,
                attribution={"win_reason": "judgment_correct"} if outcome == "win" else {"loss_reason": "A"}
            )

    def test_overall_performance(self):
        """测试整体绩效计算"""
        trades = self.logger.get_recent_trades(100)
        perf = self.analyzer._calculate_overall_performance(trades)

        self.assertIsInstance(perf, PerformanceMetrics)
        self.assertEqual(perf.total_trades, 5)
        self.assertEqual(perf.win_count, 3)
        self.assertEqual(perf.loss_count, 2)

    def test_regime_performance(self):
        """测试行情类型表现"""
        trades = self.logger.get_recent_trades(100)
        regime_perf = self.analyzer._analyze_regime_performance(trades)

        self.assertIn("trend_up", regime_perf)
        self.assertIn("range", regime_perf)

    def test_identify_biases(self):
        """测试偏差识别"""
        trades = self.logger.get_recent_trades(100)
        biases = self.analyzer._identify_biases(trades)

        # 有3个long，2个short，做多倾向应该大于0.5
        self.assertGreater(biases.long_bias_score, 0.5)

    def test_full_analysis(self):
        """测试完整分析"""
        report = self.analyzer.analyze()

        self.assertIsNotNone(report.overall_performance)
        self.assertIsNotNone(report.regime_performance)
        self.assertIsNotNone(report.biases)
        self.assertIsInstance(report.chain_of_thought, str)


class TestPromptOptimizer(unittest.TestCase):
    """测试提示词优化器"""

    def setUp(self):
        self.optimizer = PromptOptimizer()

    def test_identify_issues(self):
        """测试问题识别"""
        meta_result = {
            "prompt_optimization_suggestions": [
                {
                    "target": "judgment_layer",
                    "issue": "过度做多倾向",
                    "suggestion": "增加空头视角"
                }
            ]
        }
        perf_data = {"win_rate": 35}

        issues = self.optimizer._identify_issues(meta_result, perf_data)

        self.assertTrue(len(issues) > 0)
        self.assertIn("过度做多", issues[0])

    def test_generate_changes(self):
        """测试生成修改方案"""
        issues = ["过度做多倾向", "胜率低于40%"]
        changes = self.optimizer._generate_changes("current prompt", issues)

        self.assertTrue(len(changes) > 0)
        self.assertIn("type", changes[0])

    def test_generate_optimization_prompt(self):
        """测试生成优化提示"""
        prompt = generate_optimization_prompt(
            current_prompt="test prompt",
            prompt_id="judgment_v1",
            performance_data={"win_rate": 40},
            identified_issues=["issue1", "issue2"]
        )

        self.assertIn("test prompt", prompt)
        self.assertIn("issue1", prompt)


class TestDistillExporter(unittest.TestCase):
    """测试蒸馏导出器"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.exporter = DistillExporter(self.temp_dir)

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass

    def test_calculate_quality_score(self):
        """测试质量分数计算"""
        entry = {
            "chain_of_thought": "包含失效条件和风险收益分析",
            "decision": {
                "stop_loss": 60000,
                "entry_zone": [62000],
                "risk_reward_ratio": 2.5
            }
        }

        score = self.exporter._calculate_quality_score(entry)

        self.assertGreater(score, 0)
        self.assertLessEqual(score, 1)

    def test_cot_validator(self):
        """测试CoT验证器"""
        validator = CoTValidator()

        cot = """
        分析行情，发现支撑在60000。
        设置止损在59500，失效条件是跌破支撑。
        风险收益比2.5:1。
        """

        decision = {
            "action": "long",
            "stop_loss": 59500,
            "entry_zone": [62000],
            "risk_reward_ratio": 2.5,
            "confidence": 0.7
        }

        result = validator.validate(cot, decision)

        self.assertIn("passed", result)
        self.assertIn("quality_score", result)


if __name__ == "__main__":
    unittest.main()
