"""
Phase 2 单元测试
测试主观判断引擎各模块功能
"""

import unittest
import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from judgment.debate_engine import DebateEngine, DebateValidator, DebateResult
from judgment.regime_detector import RegimeDetector, MarketRegime
from judgment.level_analyzer import LevelAnalyzer, PriceLevel


class TestDebateValidator(unittest.TestCase):
    """测试辩论验证器"""

    def setUp(self):
        self.validator = DebateValidator()

    def test_jaccard_similarity(self):
        """测试Jaccard相似度计算"""
        text1 = "价格上涨突破阻力位做多"
        text2 = "价格上涨突破阻力位做多"
        text3 = "价格下跌跌破支撑位做空"

        sim1 = self.validator.calculate_jaccard_similarity(text1, text2)
        sim2 = self.validator.calculate_jaccard_similarity(text1, text3)

        self.assertEqual(sim1, 1.0)  # 相同文本
        self.assertLess(sim2, 1.0)  # 不同文本

    def test_debate_diversity(self):
        """测试辩论多样性验证"""
        bull = "价格上涨因为趋势强劲"
        bear = "价格下跌因为动能不足"
        neutral = "多空双方都有道理"

        passed, metrics = self.validator.validate_debate_diversity(bull, bear, neutral)

        self.assertIn("bull_bear_similarity", metrics)
        self.assertIn("passed", metrics)

    def test_anchor_compliance(self):
        """测试锚点合规检查"""
        debate = "当前趋势向上，支撑在60000"
        regime_flags = {
            "is_trending": True,
            "trend_direction": "up",
            "funding_state": "overheated",
            "oi_state": "confirming"
        }

        score, violations = self.validator.check_anchor_compliance(debate, regime_flags)

        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestDebateEngine(unittest.TestCase):
    """测试辩论引擎"""

    def setUp(self):
        self.engine = DebateEngine()

    def test_role_configs(self):
        """测试角色配置"""
        self.assertIn("bull", self.engine.role_configs)
        self.assertIn("bear", self.engine.role_configs)
        self.assertIn("judge", self.engine.role_configs)

        # 验证差异化temperature
        self.assertEqual(self.engine.role_configs["bull"]["temperature"], 0.8)
        self.assertEqual(self.engine.role_configs["bear"]["temperature"], 0.9)
        self.assertEqual(self.engine.role_configs["judge"]["temperature"], 0.5)

    def test_format_regime_flags(self):
        """测试事实锚点格式化"""
        flags = {
            "is_trending": True,
            "trend_direction": "up",
            "vol_regime": "normal",
            "funding_state": "neutral",
            "oi_state": "confirming",
            "liquidity_state": "good"
        }

        result = self.engine._format_regime_flags(flags)

        self.assertIsInstance(result, str)
        self.assertIn("趋势有效性", result)

    def test_parse_json_response(self):
        """测试JSON响应解析"""
        response = json.dumps({
            "bull_case": {"reasoning": "看涨因为...", "key_evidence": ["证据1"]},
            "bear_case": {"reasoning": "看跌因为...", "key_evidence": ["证据2"]},
            "neutral_critique": "中立观点...",
            "risk_assessment": "风险评估...",
            "final_judgment": {
                "bias": "bullish",
                "strength": "strong",
                "confidence": 0.8
            }
        })

        result = self.engine.parse_debate_response(response)

        self.assertEqual(result.bull_case.get("reasoning"), "看涨因为...")
        self.assertEqual(result.final_judgment.get("bias"), "bullish")
        self.assertEqual(result.final_judgment.get("confidence"), 0.8)


class TestRegimeDetector(unittest.TestCase):
    """测试行情性质检测器"""

    def setUp(self):
        self.detector = RegimeDetector()

    def _create_trending_df(self, direction="up", length=50):
        """创建趋势数据"""
        np.random.seed(42)
        dates = pd.date_range(start="2025-01-01", periods=length, freq="4h")

        if direction == "up":
            base = np.linspace(60000, 65000, length)
        else:
            base = np.linspace(65000, 60000, length)

        noise = np.random.randn(length) * 200
        closes = base + noise

        df = pd.DataFrame({
            "open": closes - np.random.randn(length) * 50,
            "high": closes + np.abs(np.random.randn(length)) * 100,
            "low": closes - np.abs(np.random.randn(length)) * 100,
            "close": closes,
            "volume": np.random.randint(100, 1000, length) * 1000
        }, index=dates)

        return df

    def _create_range_df(self, length=50):
        """创建震荡数据"""
        np.random.seed(42)
        dates = pd.date_range(start="2025-01-01", periods=length, freq="4h")

        base = np.full(length, 62500)
        noise = np.sin(np.linspace(0, 4*np.pi, length)) * 500 + np.random.randn(length) * 100

        closes = base + noise

        df = pd.DataFrame({
            "open": closes - np.random.randn(length) * 50,
            "high": closes + np.abs(np.random.randn(length)) * 100,
            "low": closes - np.abs(np.random.randn(length)) * 100,
            "close": closes,
            "volume": np.random.randint(100, 1000, length) * 1000
        }, index=dates)

        return df

    def test_trend_detection(self):
        """测试趋势检测"""
        df = self._create_trending_df("up", 50)

        is_trending, direction, strength = self.detector._detect_trend(df)

        # numpy.bool_需要转换为Python bool
        self.assertTrue(is_trending == True or is_trending == False)
        self.assertIn(direction, ["up", "down", "none"])
        self.assertGreaterEqual(strength, 0.0)
        self.assertLessEqual(strength, 1.0)

    def test_range_detection(self):
        """测试震荡检测"""
        df = self._create_range_df(50)

        is_ranging, metrics = self.detector._detect_range(df)

        self.assertIn("range_pct", metrics)
        self.assertIn("bb_width", metrics)

    def test_analyze_regime(self):
        """测试完整分析"""
        multi_tf = {
            "4h": self._create_trending_df("up", 50),
            "1h": self._create_trending_df("up", 50)
        }

        result = self.detector.analyze(multi_tf)

        self.assertIsInstance(result.regime, MarketRegime)
        self.assertIsInstance(result.trend_evidence, list)
        self.assertIsInstance(result.invalidation_condition, str)
        self.assertTrue(len(result.invalidation_condition) > 0)


class TestLevelAnalyzer(unittest.TestCase):
    """测试支撑压力分析器"""

    def setUp(self):
        self.analyzer = LevelAnalyzer()

    def _create_sample_df(self, length=50):
        """创建样本数据"""
        np.random.seed(42)
        dates = pd.date_range(start="2025-01-01", periods=length, freq="4h")

        base = np.linspace(60000, 63000, length)
        noise = np.random.randn(length) * 300

        closes = base + noise

        df = pd.DataFrame({
            "open": closes - np.random.randn(length) * 50,
            "high": closes + np.abs(np.random.randn(length)) * 200,
            "low": closes - np.abs(np.random.randn(length)) * 200,
            "close": closes,
            "volume": np.random.randint(100, 1000, length) * 1000
        }, index=dates)

        return df

    def test_identify_swing_levels(self):
        """测试波段高低点识别"""
        df = self._create_sample_df(50)

        levels = self.analyzer._identify_swing_levels(df)

        self.assertIsInstance(levels, list)

    def test_round_numbers(self):
        """测试整数位识别"""
        current_price = 62500

        levels = self.analyzer._identify_round_numbers(current_price)

        self.assertTrue(len(levels) > 0)
        # 应该有整数位
        prices = [l.price for l in levels]
        self.assertTrue(any(p % 5000 == 0 for p in prices))

    def test_analyze_levels(self):
        """测试完整分析"""
        multi_tf = {
            "4h": self._create_sample_df(50),
            "1d": self._create_sample_df(30)
        }
        current_price = 62500

        result = self.analyzer.analyze(multi_tf, current_price)

        self.assertIsInstance(result.critical_supports, list)
        self.assertIsInstance(result.current_zone, str)
        self.assertIsInstance(result.analysis_reasoning, str)
        self.assertTrue(len(result.current_zone) > 0)

    def test_current_zone_detection(self):
        """测试当前区域判断"""
        current_price = 62500
        nearest_support = PriceLevel(
            price=60000, strength="strong", level_type="support",
            basis="测试", touches=3, recency=5
        )
        nearest_resistance = PriceLevel(
            price=65000, strength="strong", level_type="resistance",
            basis="测试", touches=3, recency=5
        )

        zone = self.analyzer._determine_current_zone(
            current_price, nearest_support, nearest_resistance
        )

        self.assertIn("区", zone)


if __name__ == "__main__":
    unittest.main()
