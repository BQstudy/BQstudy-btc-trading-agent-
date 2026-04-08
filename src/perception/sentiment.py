"""
情绪指标采集与事实锚点计算
包含RegimeFlags模块，将客观市场状态注入LLM推理
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RegimeFlags:
    """
    市场状态事实锚点 - 由代码计算，作为LLM推理的前提约束
    参考五大核心风险消解指南：风险2（叙事无锚点）
    """
    # 趋势状态
    is_trending: bool  # 是否处于有效趋势
    trend_direction: str  # up/down/none

    # 波动率状态
    vol_regime: str  # high/normal/low
    is_low_volatility: bool
    is_high_volatility: bool

    # 资金费率状态
    funding_state: str  # neutral/overheated/reversal_risk/extreme_negative
    is_extreme_funding: bool

    # 持仓量状态
    oi_state: str  # confirming/diverging/neutral

    # 流动性状态
    liquidity_state: str  # good/adequate/poor
    is_low_liquidity: bool

    # 综合状态
    market_regime: str  # trend_up/trend_down/range/breakout/uncertain

    # 原始数值（供参考）
    raw_values: Dict


class SentimentAnalyzer:
    """情绪分析与事实锚点计算"""

    def __init__(self):
        self.atr_period = 14
        self.volatility_threshold_high = 0.03  # 3%日波动
        self.volatility_threshold_low = 0.01   # 1%日波动
        self.funding_threshold = 0.001  # 0.1%

    def calculate_regime_flags(
        self,
        multi_tf_data: Dict[str, pd.DataFrame],
        funding_rate: float,
        oi_change_pct: float,
        orderbook: Optional[dict] = None
    ) -> RegimeFlags:
        """
        计算市场状态事实锚点

        Args:
            multi_tf_data: 多周期K线数据
            funding_rate: 当前资金费率
            oi_change_pct: 持仓量变化百分比
            orderbook: 订单簿数据

        Returns:
            RegimeFlags对象
        """
        # 1. 趋势判断
        is_trending, trend_direction = self._detect_trend(multi_tf_data)

        # 2. 波动率判断
        vol_regime, is_low_vol, is_high_vol = self._analyze_volatility(multi_tf_data)

        # 3. 资金费率判断
        funding_state, is_extreme = self._analyze_funding(funding_rate)

        # 4. 持仓量判断
        oi_state = self._analyze_oi(multi_tf_data, oi_change_pct)

        # 5. 流动性判断
        liquidity_state, is_low_liq = self._analyze_liquidity(orderbook)

        # 6. 综合市场状态
        market_regime = self._determine_market_regime(
            is_trending, trend_direction, vol_regime, funding_state, oi_state
        )

        # 收集原始数值
        raw_values = {
            "atr_1h": self._calculate_atr(multi_tf_data.get("1h", pd.DataFrame()), 14),
            "atr_4h": self._calculate_atr(multi_tf_data.get("4h", pd.DataFrame()), 14),
            "funding_rate": funding_rate,
            "oi_change_pct": oi_change_pct,
            "spread_pct": orderbook.get("spread_pct", 0) if orderbook else 0,
            "depth_ratio": orderbook.get("depth_ratio", 1.0) if orderbook else 1.0
        }

        return RegimeFlags(
            is_trending=is_trending,
            trend_direction=trend_direction,
            vol_regime=vol_regime,
            is_low_volatility=is_low_vol,
            is_high_volatility=is_high_vol,
            funding_state=funding_state,
            is_extreme_funding=is_extreme,
            oi_state=oi_state,
            liquidity_state=liquidity_state,
            is_low_liquidity=is_low_liq,
            market_regime=market_regime,
            raw_values=raw_values
        )

    def format_flags_for_prompt(self, flags: RegimeFlags) -> str:
        """
        将事实锚点格式化为Prompt文本
        注入LLM推理的前提约束
        """
        lines = [
            "【客观事实锚点（系统计算，不可主观否定）】",
            f"- 趋势有效性：{'有效' if flags.is_trending else '无效'} ({flags.trend_direction})",
            f"- 波动率状态：{flags.vol_regime} ({'低波动' if flags.is_low_volatility else '高波动' if flags.is_high_volatility else '正常'})",
            f"- 资金情绪状态：{flags.funding_state} ({'极端' if flags.is_extreme_funding else '正常'})",
            f"- 持仓量变化：{flags.oi_state}",
            f"- 流动性状态：{flags.liquidity_state}",
            f"- 综合市场状态：{flags.market_regime}",
            "",
            "【强制约束】",
            "你的判断必须与上述事实锚点逻辑自洽。若价格形态暗示上涨，但资金费率过热且持仓量背离，",
            "你必须明确说明'多头动能存疑'，并下调confidence。禁止脱离锚点构建纯叙事推演。",
            "",
            "【冲突处理】",
            "若你发现事实锚点之间存在矛盾（如趋势有效但波动率低），",
            "请优先信任波动率与资金状态，并在reasoning中说明'趋势质量存疑'。"
        ]

        return "\n".join(lines)

    def calculate_sentiment_score(
        self,
        flags: RegimeFlags,
        price_change_24h: float
    ) -> Dict:
        """
        计算综合情绪分数
        返回结构化的情绪指标
        """
        # 多头信号计数
        bull_signals = 0
        bear_signals = 0

        # 趋势信号
        if flags.is_trending:
            if flags.trend_direction == "up":
                bull_signals += 2
            else:
                bear_signals += 2

        # 资金费率信号
        if flags.funding_state == "overheated":
            bear_signals += 1  # 过热可能反转
        elif flags.funding_state == "extreme_negative":
            bull_signals += 1
        elif flags.funding_state == "reversal_risk":
            bear_signals += 1

        # 持仓量信号
        if flags.oi_state == "confirming":
            if price_change_24h > 0:
                bull_signals += 1
            else:
                bear_signals += 1
        elif flags.oi_state == "diverging":
            if price_change_24h > 0:
                bear_signals += 1  # 上涨但OI下降，背离
            else:
                bull_signals += 1

        # 波动率信号
        if flags.is_high_volatility:
            # 高波动时，顺势
            if price_change_24h > 0:
                bull_signals += 1
            else:
                bear_signals += 1

        total_signals = bull_signals + bear_signals
        if total_signals == 0:
            sentiment_score = 0.5
        else:
            sentiment_score = bull_signals / total_signals

        # 确定情绪标签
        if sentiment_score > 0.7:
            sentiment_label = "bullish"
        elif sentiment_score < 0.3:
            sentiment_label = "bearish"
        else:
            sentiment_label = "neutral"

        # 考虑极端情况
        if flags.is_extreme_funding and sentiment_label == "bullish":
            sentiment_label = "extreme_greed"
        elif flags.is_extreme_funding and sentiment_label == "bearish":
            sentiment_label = "extreme_fear"

        return {
            "sentiment_score": round(sentiment_score, 2),
            "sentiment_label": sentiment_label,
            "bull_signals": bull_signals,
            "bear_signals": bear_signals,
            "confidence": self._calculate_sentiment_confidence(flags)
        }

    # ============ 辅助方法 ============

    def _detect_trend(self, multi_tf_data: Dict[str, pd.DataFrame]) -> tuple[bool, str]:
        """检测趋势状态"""
        if "4h" not in multi_tf_data or len(multi_tf_data["4h"]) < 20:
            return False, "none"

        df = multi_tf_data["4h"]
        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values

        # 计算20周期趋势
        if len(closes) < 20:
            return False, "none"

        recent_20 = closes[-20:]
        slope = (recent_20[-1] - recent_20[0]) / recent_20[0]

        # 判断高低点结构
        higher_highs = highs[-1] > highs[-10:].max()
        higher_lows = lows[-1] > lows[-10:].mean()
        lower_highs = highs[-1] < highs[-10:].mean()
        lower_lows = lows[-1] < lows[-10:].min()

        # 趋势有效性判断
        if abs(slope) < 0.02:  # 2%以内的波动视为震荡
            return False, "none"

        if higher_highs and higher_lows and slope > 0:
            return True, "up"
        elif lower_highs and lower_lows and slope < 0:
            return True, "down"

        return False, "none"

    def _analyze_volatility(
        self,
        multi_tf_data: Dict[str, pd.DataFrame]
    ) -> tuple[str, bool, bool]:
        """分析波动率状态"""
        if "1h" not in multi_tf_data or len(multi_tf_data["1h"]) < 24:
            return "normal", False, False

        df = multi_tf_data["1h"]
        atr = self._calculate_atr(df, 14)
        current_price = df["close"].iloc[-1]

        if current_price == 0:
            return "normal", False, False

        atr_pct = atr / current_price

        if atr_pct > self.volatility_threshold_high:
            return "high", False, True
        elif atr_pct < self.volatility_threshold_low:
            return "low", True, False
        else:
            return "normal", False, False

    def _analyze_funding(self, funding_rate: float) -> tuple[str, bool]:
        """分析资金费率状态"""
        if funding_rate > 0.003:  # > 0.3%
            return "extreme_overheated", True
        elif funding_rate > 0.001:  # > 0.1%
            return "overheated", True
        elif funding_rate < -0.003:  # < -0.3%
            return "extreme_negative", True
        elif funding_rate < -0.001:  # < -0.1%
            return "reversal_risk", True
        else:
            return "neutral", False

    def _analyze_oi(
        self,
        multi_tf_data: Dict[str, pd.DataFrame],
        oi_change_pct: float
    ) -> str:
        """分析持仓量状态"""
        if "1h" not in multi_tf_data or len(multi_tf_data["1h"]) < 5:
            return "neutral"

        df = multi_tf_data["1h"]
        recent_change = (df["close"].iloc[-1] - df["close"].iloc[-5]) / df["close"].iloc[-5] * 100

        # 价格与OI同向 = 确认
        # 价格与OI反向 = 背离
        if abs(oi_change_pct) < 1 or abs(recent_change) < 0.5:
            return "neutral"

        if (recent_change > 0 and oi_change_pct > 0) or (recent_change < 0 and oi_change_pct < 0):
            return "confirming"
        else:
            return "diverging"

    def _analyze_liquidity(
        self,
        orderbook: Optional[dict]
    ) -> tuple[str, bool]:
        """分析流动性状态"""
        if not orderbook:
            return "unknown", False

        spread_pct = orderbook.get("spread_pct", 0)
        depth_ratio = orderbook.get("depth_ratio", 1.0)

        # 价差判断
        if spread_pct > 0.002:  # > 0.2%
            return "poor", True
        elif spread_pct > 0.001:  # > 0.1%
            return "adequate", False

        # 深度判断
        if depth_ratio < 0.5 or depth_ratio > 2.0:
            return "adequate", False

        return "good", False

    def _determine_market_regime(
        self,
        is_trending: bool,
        trend_direction: str,
        vol_regime: str,
        funding_state: str,
        oi_state: str
    ) -> str:
        """确定综合市场状态"""
        if not is_trending:
            if vol_regime == "low":
                return "range"  # 窄幅震荡
            else:
                return "uncertain"  # 方向不明

        if is_trending:
            if trend_direction == "up":
                if funding_state == "overheated" or oi_state == "diverging":
                    return "trend_up_exhausted"  # 上涨衰竭
                return "trend_up"
            else:
                if funding_state == "extreme_negative":
                    return "trend_down_exhausted"
                return "trend_down"

        return "uncertain"

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """计算ATR（平均真实波幅）"""
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

        if len(tr_list) < period:
            return 0.0

        return np.mean(tr_list[-period:])

    def _calculate_sentiment_confidence(self, flags: RegimeFlags) -> str:
        """计算情绪判断置信度"""
        # 锚点一致性判断
        conflicts = 0

        if flags.is_trending and flags.is_low_volatility:
            conflicts += 1  # 趋势但低波动，存疑

        if flags.funding_state in ["overheated", "extreme_overheated"] and flags.oi_state == "confirming":
            conflicts += 1  # 费率过热但OI确认，矛盾

        if flags.is_high_volatility and not flags.is_trending:
            conflicts += 1  # 高波动但无趋势，震荡

        if conflicts == 0:
            return "high"
        elif conflicts == 1:
            return "medium"
        else:
            return "low"
