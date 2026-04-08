"""
Phase 1 单元测试
测试市场感知层各模块功能
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from perception.market_narrator import MarketNarrator, CandlePattern
from perception.sentiment import SentimentAnalyzer, RegimeFlags


class TestMarketNarrator(unittest.TestCase):
    """测试市场叙事生成器"""

    def setUp(self):
        self.narrator = MarketNarrator()

    def _create_sample_df(self, trend="up", length=50):
        """创建模拟K线数据"""
        np.random.seed(42)
        dates = pd.date_range(start="2025-01-01", periods=length, freq="1h")

        if trend == "up":
            base = np.linspace(60000, 65000, length)
        elif trend == "down":
            base = np.linspace(65000, 60000, length)
        else:  # sideways
            base = np.full(length, 62500) + np.sin(np.linspace(0, 4*np.pi, length)) * 1000

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

    def test_narrate_klines_basic(self):
        """测试基础K线叙事"""
        df = self._create_sample_df("up", 50)
        narrative = self.narrator.narrate_klines(df, "1h")

        self.assertIsInstance(narrative, str)
        self.assertTrue(len(narrative) > 0)
        self.assertIn("1h", narrative)

    def test_narrate_market_structure(self):
        """测试多周期结构描述"""
        multi_tf = {
            "15m": self._create_sample_df("up", 100),
            "1h": self._create_sample_df("up", 50),
            "4h": self._create_sample_df("up", 30),
            "1d": self._create_sample_df("up", 20)
        }

        narrative = self.narrator.narrate_market_structure(multi_tf)

        self.assertIsInstance(narrative, str)
        self.assertTrue(len(narrative) > 0)

    def test_narrate_funding_sentiment(self):
        """测试资金费率情绪描述"""
        # 正常费率
        result1 = self.narrator.narrate_funding_sentiment(0.0001, "stable")
        self.assertIn("中性", result1)

        # 过热费率
        result2 = self.narrator.narrate_funding_sentiment(0.0015, "rising")
        self.assertIn("过热", result2)

        # 负费率
        result3 = self.narrator.narrate_funding_sentiment(-0.002, "falling")
        self.assertIn("空头", result3)

    def test_narrate_oi_change(self):
        """测试持仓量变化描述"""
        # 大幅增加
        result1 = self.narrator.narrate_oi_change(1000000, 8)
        self.assertIn("大幅", result1)

        # 小幅减少
        result2 = self.narrator.narrate_oi_change(1000000, -1.5)
        self.assertIn("小幅", result2)

        # 基本持平
        result3 = self.narrator.narrate_oi_change(1000000, 0.3)
        self.assertIn("持平", result3)

    def test_compose_full_narrative(self):
        """测试完整叙事生成"""
        market_data = {
            "current_price": 62500,
            "price_change_24h": 2.5,
            "dist_to_high": -5.0,
            "dist_to_low": 8.0,
            "multi_tf_klines": {
                "1h": self._create_sample_df("up", 50)
            },
            "funding_rate": 0.0005,
            "funding_trend": "stable",
            "open_interest": 1000000,
            "oi_change_24h": 3.5,
            "long_liquidations": 10.5,
            "short_liquidations": 5.2,
            "orderbook": {
                "spread_pct": 0.0005,
                "depth_ratio": 1.2
            }
        }

        result = self.narrator.compose_full_narrative(market_data)

        self.assertIn("market_narrative", result)
        self.assertIn("market_type", result)
        self.assertIn("sentiment", result)
        self.assertIn("summary", result)
        self.assertIsInstance(result["key_support"], list)
        self.assertIsInstance(result["key_resistance"], list)


class TestSentimentAnalyzer(unittest.TestCase):
    """测试情绪分析器"""

    def setUp(self):
        self.analyzer = SentimentAnalyzer()

    def _create_sample_df(self, volatility="normal", length=50):
        """创建模拟K线数据"""
        np.random.seed(42)
        dates = pd.date_range(start="2025-01-01", periods=length, freq="1h")

        if volatility == "high":
            noise = np.random.randn(length) * 500
        elif volatility == "low":
            noise = np.random.randn(length) * 50
        else:
            noise = np.random.randn(length) * 200

        base = np.linspace(60000, 62000, length)
        closes = base + noise

        df = pd.DataFrame({
            "open": closes - np.random.randn(length) * 50,
            "high": closes + np.abs(np.random.randn(length)) * 100,
            "low": closes - np.abs(np.random.randn(length)) * 100,
            "close": closes,
            "volume": np.random.randint(100, 1000, length) * 1000
        }, index=dates)

        return df

    def test_calculate_regime_flags(self):
        """测试事实锚点计算"""
        multi_tf = {
            "1h": self._create_sample_df("normal", 50),
            "4h": self._create_sample_df("normal", 30)
        }

        flags = self.analyzer.calculate_regime_flags(
            multi_tf_data=multi_tf,
            funding_rate=0.0005,
            oi_change_pct=3.0,
            orderbook={"spread_pct": 0.0005, "depth_ratio": 1.2}
        )

        self.assertIsInstance(flags, RegimeFlags)
        self.assertIn(flags.vol_regime, ["high", "normal", "low"])
        self.assertIn(flags.funding_state, ["neutral", "overheated", "extreme_overheated", "reversal_risk", "extreme_negative"])
        self.assertIn(flags.oi_state, ["confirming", "diverging", "neutral"])

    def test_format_flags_for_prompt(self):
        """测试事实锚点格式化"""
        flags = RegimeFlags(
            is_trending=True,
            trend_direction="up",
            vol_regime="normal",
            is_low_volatility=False,
            is_high_volatility=False,
            funding_state="neutral",
            is_extreme_funding=False,
            oi_state="confirming",
            liquidity_state="good",
            is_low_liquidity=False,
            market_regime="trend_up",
            raw_values={}
        )

        prompt_text = self.analyzer.format_flags_for_prompt(flags)

        self.assertIsInstance(prompt_text, str)
        self.assertIn("事实锚点", prompt_text)
        self.assertIn("强制约束", prompt_text)

    def test_calculate_sentiment_score(self):
        """测试情绪分数计算"""
        flags = RegimeFlags(
            is_trending=True,
            trend_direction="up",
            vol_regime="normal",
            is_low_volatility=False,
            is_high_volatility=False,
            funding_state="neutral",
            is_extreme_funding=False,
            oi_state="confirming",
            liquidity_state="good",
            is_low_liquidity=False,
            market_regime="trend_up",
            raw_values={}
        )

        result = self.analyzer.calculate_sentiment_score(flags, 2.5)

        self.assertIn("sentiment_score", result)
        self.assertIn("sentiment_label", result)
        self.assertGreaterEqual(result["sentiment_score"], 0)
        self.assertLessEqual(result["sentiment_score"], 1)

    def test_extreme_funding_detection(self):
        """测试极端费率检测"""
        # 过热费率
        state, is_extreme = self.analyzer._analyze_funding(0.002)
        self.assertTrue(is_extreme)
        self.assertIn("overheated", state)

        # 极端负费率
        state, is_extreme = self.analyzer._analyze_funding(-0.004)
        self.assertTrue(is_extreme)

        # 正常费率
        state, is_extreme = self.analyzer._analyze_funding(0.0003)
        self.assertFalse(is_extreme)
        self.assertEqual(state, "neutral")


class TestCandlePattern(unittest.TestCase):
    """测试蜡烛形态识别"""

    def setUp(self):
        self.narrator = MarketNarrator()

    def test_doji_recognition(self):
        """测试十字星识别"""
        # 创建十字星数据
        candle = pd.Series({
            "open": 62000,
            "high": 62100,
            "low": 61900,
            "close": 62010  # 几乎等于open
        })

        patterns = self.narrator._identify_candle_patterns(candle)

        pattern_names = [p.name for p in patterns]
        self.assertIn("doji", pattern_names)

    def test_hammer_recognition(self):
        """测试锤头识别"""
        # 创建锤头数据
        candle = pd.Series({
            "open": 62000,
            "high": 62050,
            "low": 61800,  # 长下影
            "close": 62080  # 上涨收盘
        })

        patterns = self.narrator._identify_candle_patterns(candle)

        pattern_names = [p.name for p in patterns]
        self.assertIn("hammer", pattern_names)


if __name__ == "__main__":
    unittest.main()
