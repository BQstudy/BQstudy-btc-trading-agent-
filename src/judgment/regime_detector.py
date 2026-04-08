"""
行情性质判断模块
判断当前行情是趋势/震荡/突破，以及方向
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum


class MarketRegime(Enum):
    """市场状态枚举"""
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE = "range"
    BREAKOUT_IMMINENT = "breakout_imminent"
    BREAKOUT_FALSE = "breakout_false"
    UNCERTAIN = "uncertain"


@dataclass
class RegimeAnalysis:
    """行情性质分析结果"""
    regime: MarketRegime
    trend_strength: float  # 0-1
    range_bound: bool
    breakout_probability: float  # 0-1
    volatility_regime: str  # high/normal/low

    # 关键判断依据
    trend_evidence: List[str]
    range_evidence: List[str]
    breakout_signals: List[str]

    # 失效条件
    invalidation_condition: str


class RegimeDetector:
    """
    行情性质检测器
    判断当前是趋势行情、震荡行情还是突破前夜
    """

    def __init__(self):
        self.lookback_periods = {
            "short": 10,
            "medium": 20,
            "long": 50
        }
        self.adx_threshold = 25  # ADX趋势强度阈值
        self.range_threshold = 0.05  # 5%范围视为震荡

    def analyze(self, multi_tf_data: Dict[str, pd.DataFrame]) -> RegimeAnalysis:
        """
        综合分析行情性质
        """
        if "4h" not in multi_tf_data or len(multi_tf_data["4h"]) < 20:
            return self._create_uncertain_analysis("数据不足")

        df_4h = multi_tf_data["4h"]
        df_1h = multi_tf_data.get("1h", df_4h)

        # 1. 趋势检测
        is_trending, trend_direction, trend_strength = self._detect_trend(df_4h)

        # 2. 震荡检测
        is_ranging, range_metrics = self._detect_range(df_4h)

        # 3. 突破信号检测
        breakout_signals = self._detect_breakout_signals(multi_tf_data)

        # 4. 波动率状态
        vol_regime = self._analyze_volatility_regime(df_4h)

        # 5. 综合判断
        regime = self._determine_regime(
            is_trending, trend_direction, trend_strength,
            is_ranging, breakout_signals
        )

        # 6. 收集证据
        trend_evidence = self._collect_trend_evidence(df_4h, trend_direction, trend_strength)
        range_evidence = self._collect_range_evidence(df_4h, range_metrics)

        # 7. 计算突破概率
        breakout_prob = self._calculate_breakout_probability(
            regime, breakout_signals, vol_regime
        )

        # 8. 生成失效条件
        invalidation = self._generate_invalidation_condition(regime, df_4h)

        return RegimeAnalysis(
            regime=regime,
            trend_strength=trend_strength,
            range_bound=is_ranging,
            breakout_probability=breakout_prob,
            volatility_regime=vol_regime,
            trend_evidence=trend_evidence,
            range_evidence=range_evidence,
            breakout_signals=breakout_signals,
            invalidation_condition=invalidation
        )

    def _detect_trend(self, df: pd.DataFrame) -> Tuple[bool, str, float]:
        """
        检测趋势
        返回：(是否趋势, 方向, 强度0-1)
        """
        if len(df) < 20:
            return False, "none", 0.0

        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values

        # 计算ADX
        adx = self._calculate_adx(df)
        is_trending = adx > self.adx_threshold

        # 判断方向
        ema20 = pd.Series(closes).ewm(span=20).mean().values
        ema50 = pd.Series(closes).ewm(span=50).mean().values if len(closes) >= 50 else ema20

        if closes[-1] > ema20[-1] > ema50[-1]:
            direction = "up"
        elif closes[-1] < ema20[-1] < ema50[-1]:
            direction = "down"
        else:
            direction = "none"

        # 计算趋势强度
        # 基于ADX和均线排列
        adx_strength = min(adx / 50, 1.0)  # 归一化到0-1

        # 检查高低点结构
        recent_highs = highs[-20:]
        recent_lows = lows[-20:]

        if direction == "up":
            hh = recent_highs[-1] >= np.max(recent_highs[:-5])
            hl = recent_lows[-1] >= np.mean(recent_lows[:-5])
            structure_strength = 1.0 if hh and hl else 0.5
        elif direction == "down":
            lh = recent_highs[-1] <= np.mean(recent_highs[:-5])
            ll = recent_lows[-1] <= np.min(recent_lows[:-5])
            structure_strength = 1.0 if lh and ll else 0.5
        else:
            structure_strength = 0.0

        strength = (adx_strength + structure_strength) / 2

        return is_trending, direction, strength

    def _detect_range(self, df: pd.DataFrame) -> Tuple[bool, Dict]:
        """
        检测震荡区间
        """
        if len(df) < 20:
            return False, {}

        highs = df["high"].values[-20:]
        lows = df["low"].values[-20:]
        closes = df["close"].values[-20:]

        range_high = np.max(highs)
        range_low = np.min(lows)
        range_size = range_high - range_low
        range_pct = range_size / np.mean(closes)

        # Bollinger Band收缩检测
        bb_width = self._calculate_bb_width(df)
        is_squeezing = bb_width < 0.1  # 布林带收缩

        is_ranging = range_pct < self.range_threshold or is_squeezing

        metrics = {
            "range_high": range_high,
            "range_low": range_low,
            "range_pct": range_pct,
            "bb_width": bb_width,
            "is_squeezing": is_squeezing
        }

        return is_ranging, metrics

    def _detect_breakout_signals(self, multi_tf_data: Dict[str, pd.DataFrame]) -> List[str]:
        """
        检测突破信号
        """
        signals = []

        # 检查各周期
        for tf, df in multi_tf_data.items():
            if len(df) < 10:
                continue

            highs = df["high"].values
            lows = df["low"].values
            closes = df["close"].values
            volumes = df["volume"].values if "volume" in df.columns else None

            # 价格接近区间边界
            recent_high = np.max(highs[-20:-1])
            recent_low = np.min(lows[-20:-1])
            current = closes[-1]

            # 接近上沿
            if current > recent_high * 0.995:
                signals.append(f"{tf}_near_resistance")

                # 放量突破
                if volumes is not None and len(volumes) > 5:
                    vol_avg = np.mean(volumes[-5:-1])
                    if volumes[-1] > vol_avg * 1.5:
                        signals.append(f"{tf}_volume_breakout_up")

            # 接近下沿
            if current < recent_low * 1.005:
                signals.append(f"{tf}_near_support")

                if volumes is not None and len(volumes) > 5:
                    vol_avg = np.mean(volumes[-5:-1])
                    if volumes[-1] > vol_avg * 1.5:
                        signals.append(f"{tf}_volume_breakout_down")

            # 布林带收缩后突破
            bb_width = self._calculate_bb_width(df.tail(20))
            if bb_width < 0.08:  # 极度收缩
                signals.append(f"{tf}_bb_squeeze")

        return signals

    def _analyze_volatility_regime(self, df: pd.DataFrame) -> str:
        """分析波动率状态"""
        if len(df) < 20:
            return "normal"

        atr = self._calculate_atr(df, 14)
        current_price = df["close"].iloc[-1]

        if current_price == 0:
            return "normal"

        atr_pct = atr / current_price

        if atr_pct > 0.03:
            return "high"
        elif atr_pct < 0.01:
            return "low"
        else:
            return "normal"

    def _determine_regime(
        self,
        is_trending: bool,
        trend_direction: str,
        trend_strength: float,
        is_ranging: bool,
        breakout_signals: List[str]
    ) -> MarketRegime:
        """确定市场状态"""
        # 突破信号优先
        has_breakout_up = any("breakout_up" in s for s in breakout_signals)
        has_breakout_down = any("breakout_down" in s for s in breakout_signals)
        has_squeeze = any("squeeze" in s for s in breakout_signals)

        if has_breakout_up:
            return MarketRegime.BREAKOUT_IMMINENT if has_squeeze else MarketRegime.TREND_UP
        if has_breakout_down:
            return MarketRegime.BREAKOUT_IMMINENT if has_squeeze else MarketRegime.TREND_DOWN

        # 趋势判断
        if is_trending and trend_strength > 0.5:
            if trend_direction == "up":
                return MarketRegime.TREND_UP
            elif trend_direction == "down":
                return MarketRegime.TREND_DOWN

        # 震荡判断
        if is_ranging:
            return MarketRegime.RANGE

        # 突破前夜判断
        if has_squeeze:
            return MarketRegime.BREAKOUT_IMMINENT

        return MarketRegime.UNCERTAIN

    def _collect_trend_evidence(self, df: pd.DataFrame, direction: str, strength: float) -> List[str]:
        """收集趋势证据"""
        evidence = []

        if strength > 0.7:
            evidence.append(f"趋势强度强（{strength:.2f}）")
        elif strength > 0.4:
            evidence.append(f"趋势强度中等（{strength:.2f}）")

        closes = df["close"].values[-20:]
        price_change = (closes[-1] - closes[0]) / closes[0] * 100

        if direction == "up":
            evidence.append(f"20周期上涨{price_change:.2f}%")
        elif direction == "down":
            evidence.append(f"20周期下跌{abs(price_change):.2f}%")

        return evidence

    def _collect_range_evidence(self, df: pd.DataFrame, metrics: Dict) -> List[str]:
        """收集震荡证据"""
        evidence = []

        if "range_pct" in metrics:
            evidence.append(f"区间幅度{metrics['range_pct']*100:.2f}%")

        if metrics.get("is_squeezing"):
            evidence.append("布林带收缩，波动率压缩")

        return evidence

    def _calculate_breakout_probability(
        self,
        regime: MarketRegime,
        signals: List[str],
        vol_regime: str
    ) -> float:
        """计算突破概率"""
        base_prob = 0.3  # 基础概率

        # 根据状态调整
        if regime == MarketRegime.BREAKOUT_IMMINENT:
            base_prob = 0.7
        elif regime == MarketRegime.RANGE:
            base_prob = 0.4

        # 信号加成
        if any("squeeze" in s for s in signals):
            base_prob += 0.15
        if any("volume" in s for s in signals):
            base_prob += 0.1

        # 波动率调整
        if vol_regime == "low":
            base_prob += 0.1  # 低波动后容易突破
        elif vol_regime == "high":
            base_prob -= 0.1  # 高波动时突破可能已发生

        return min(max(base_prob, 0.0), 1.0)

    def _generate_invalidation_condition(self, regime: MarketRegime, df: pd.DataFrame) -> str:
        """生成判断失效条件"""
        if regime == MarketRegime.TREND_UP:
            return "价格跌破前低或ADX降至25以下"
        elif regime == MarketRegime.TREND_DOWN:
            return "价格突破前高或ADX降至25以下"
        elif regime == MarketRegime.RANGE:
            return "价格突破区间边界且伴随放量"
        elif regime == MarketRegime.BREAKOUT_IMMINENT:
            return "突破失败并回到原区间"
        else:
            return "出现明确趋势信号"

    def _create_uncertain_analysis(self, reason: str) -> RegimeAnalysis:
        """创建不确定分析结果"""
        return RegimeAnalysis(
            regime=MarketRegime.UNCERTAIN,
            trend_strength=0.0,
            range_bound=False,
            breakout_probability=0.0,
            volatility_regime="unknown",
            trend_evidence=[],
            range_evidence=[],
            breakout_signals=[],
            invalidation_condition=reason
        )

    # ============ 技术指标计算 ============

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """计算ADX（平均趋向指数）"""
        if len(df) < period + 1:
            return 0.0

        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values

        # +DM和-DM
        plus_dm = []
        minus_dm = []
        tr_list = []

        for i in range(1, len(df)):
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]

            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0)

            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0)

            # 真实波幅
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            tr_list.append(max(tr1, tr2, tr3))

        # 平滑
        if len(tr_list) < period:
            return 0.0

        atr = np.mean(tr_list[-period:])
        plus_di = 100 * np.mean(plus_dm[-period:]) / atr if atr > 0 else 0
        minus_di = 100 * np.mean(minus_dm[-period:]) / atr if atr > 0 else 0

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0

        return dx

    def _calculate_bb_width(self, df: pd.DataFrame, period: int = 20) -> float:
        """计算布林带宽度"""
        if len(df) < period:
            return 1.0

        closes = df["close"].values[-period:]
        sma = np.mean(closes)
        std = np.std(closes)

        if sma == 0:
            return 1.0

        return (2 * std) / sma

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """计算ATR"""
        if len(df) < period + 1:
            return 0.0

        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values

        tr_list = []
        for i in range(1, len(df)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            tr_list.append(max(tr1, tr2, tr3))

        return np.mean(tr_list[-period:])
