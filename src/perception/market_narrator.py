"""
K线叙事化转换器 - 将原始市场数据转化为交易员视角的语言描述
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class CandlePattern:
    """蜡烛形态识别结果"""
    name: str
    strength: str  # strong/medium/weak
    description: str


class MarketNarrator:
    """市场叙事生成器"""

    def __init__(self):
        self.volume_ma_period = 20

    def narrate_klines(self, df: pd.DataFrame, timeframe: str) -> str:
        """
        将K线数据转化为自然语言描述

        Args:
            df: OHLCV DataFrame
            timeframe: 时间周期标识 (15m/1h/4h/1d)

        Returns:
            自然语言行情描述
        """
        if len(df) < 10:
            return f"{timeframe}数据不足，无法分析"

        narratives = []

        # 1. 近期K线形态
        recent = df.tail(10)
        candles = self._analyze_candle_sequence(recent)
        narratives.append(f"【{timeframe}形态】{candles}")

        # 2. 成交量分析
        volume_narrative = self._analyze_volume(recent)
        narratives.append(volume_narrative)

        # 3. 关键蜡烛形态
        patterns = self._identify_candle_patterns(df.iloc[-1])
        if patterns:
            pattern_desc = "，".join([p.description for p in patterns])
            narratives.append(f"【关键信号】{pattern_desc}")

        # 4. 价格位置
        position = self._analyze_price_position(df)
        narratives.append(position)

        return "；".join(narratives)

    def narrate_market_structure(self, multi_tf_data: Dict[str, pd.DataFrame]) -> str:
        """
        多周期结构综合描述

        Args:
            multi_tf_data: {'15m': df, '1h': df, '4h': df, '1d': df}

        Returns:
            多周期结构综合描述
        """
        narratives = []

        # 日线趋势（最高级别）
        if "1d" in multi_tf_data and len(multi_tf_data["1d"]) >= 20:
            daily = multi_tf_data["1d"]
            daily_trend = self._determine_trend(daily.tail(20))
            narratives.append(f"日线级别处于{daily_trend}结构")

        # 4小时结构
        if "4h" in multi_tf_data and len(multi_tf_data["4h"]) >= 20:
            h4 = multi_tf_data["4h"]
            h4_trend = self._determine_trend(h4.tail(20))
            narratives.append(f"4小时呈现{h4_trend}特征")

        # 1小时结构
        if "1h" in multi_tf_data and len(multi_tf_data["1h"]) >= 20:
            h1 = multi_tf_data["1h"]
            h1_trend = self._determine_trend(h1.tail(20))
            narratives.append(f"1小时级别{h1_trend}")

        # 15分钟短期
        if "15m" in multi_tf_data and len(multi_tf_data["15m"]) >= 10:
            m15 = multi_tf_data["15m"]
            recent_price = m15["close"].iloc[-1]
            prev_price = m15["close"].iloc[-10]
            change = (recent_price - prev_price) / prev_price * 100

            if abs(change) < 0.5:
                short_desc = "窄幅震荡整理"
            elif change > 0:
                short_desc = f"短线上涨{change:.2f}%"
            else:
                short_desc = f"短线下跌{abs(change):.2f}%"

            narratives.append(f"15分钟{short_desc}")

        # 多周期一致性判断
        consistency = self._analyze_timeframe_consistency(multi_tf_data)
        if consistency:
            narratives.append(consistency)

        return "。".join(narratives)

    def narrate_funding_sentiment(self, funding_rate: float, trend: str) -> str:
        """
        资金费率情绪描述

        Args:
            funding_rate: 当前资金费率
            trend: 趋势 (rising/falling/stable)

        Returns:
            情绪描述
        """
        rate_pct = funding_rate * 100

        if funding_rate > 0.001:  # > 0.1%
            sentiment = "多头情绪过热，空头资金费率补贴较高"
            if trend == "rising":
                sentiment += "，且费率持续上升，多头拥挤风险增加"
            elif trend == "falling":
                sentiment += "，但费率开始回落，多头情绪有所降温"
        elif funding_rate < -0.001:  # < -0.1%
            sentiment = "空头情绪过热，多头获得资金补贴"
            if trend == "falling":
                sentiment += "，费率持续走低，空头拥挤风险增加"
            elif trend == "rising":
                sentiment += "，费率开始回升，空头情绪有所缓解"
        else:
            sentiment = "资金费率处于中性区间，多空情绪相对平衡"
            if trend == "rising":
                sentiment += "，费率小幅上升"
            elif trend == "falling":
                sentiment += "，费率小幅下降"

        return f"资金费率{rate_pct:.4f}%：{sentiment}"

    def narrate_oi_change(self, oi_current: float, oi_change_pct: float) -> str:
        """
        持仓量变化描述

        Args:
            oi_current: 当前持仓量
            oi_change_pct: 24h变化百分比

        Returns:
            持仓量变化描述
        """
        if abs(oi_change_pct) < 1:
            return f"持仓量基本持平，市场参与度稳定"

        direction = "增加" if oi_change_pct > 0 else "减少"

        if abs(oi_change_pct) > 5:
            magnitude = "大幅"
        elif abs(oi_change_pct) > 2:
            magnitude = "明显"
        else:
            magnitude = "小幅"

        if oi_change_pct > 5:
            implication = "新资金入场积极，趋势可能延续"
        elif oi_change_pct > 2:
            implication = "资金流入，市场关注度提升"
        elif oi_change_pct < -5:
            implication = "资金离场明显，趋势可能衰竭"
        elif oi_change_pct < -2:
            implication = "持仓减少，市场观望情绪浓厚"
        else:
            implication = ""

        result = f"持仓量{magnitude}{direction}{abs(oi_change_pct):.2f}%"
        if implication:
            result += f"，{implication}"

        return result

    def compose_full_narrative(self, market_data: dict) -> dict:
        """
        生成完整盘前分析叙事

        Args:
            market_data: data_fetcher返回的完整市场数据

        Returns:
            {
                "market_narrative": "完整行情叙事",
                "market_type": "trend_up|trend_down|consolidation|breakout_imminent",
                "key_support": [price1, price2],
                "key_resistance": [price1, price2],
                "sentiment": "bullish|bearish|neutral|extreme_greed|extreme_fear",
                "summary": "一句话核心结论",
                "confidence": "high|medium|low"
            }
        """
        narratives = []

        # 1. 多周期结构叙事
        multi_tf = market_data.get("multi_tf_klines", {})
        if multi_tf:
            structure = self.narrate_market_structure(multi_tf)
            narratives.append(structure)

        # 2. 资金费率叙事
        funding = self.narrate_funding_sentiment(
            market_data.get("funding_rate", 0),
            market_data.get("funding_trend", "stable")
        )
        narratives.append(funding)

        # 3. 持仓量叙事
        oi = self.narrate_oi_change(
            market_data.get("open_interest", 0),
            market_data.get("oi_change_24h", 0)
        )
        narratives.append(oi)

        # 4. 爆仓数据
        long_liq = market_data.get("long_liquidations", 0)
        short_liq = market_data.get("short_liquidations", 0)
        if long_liq > 0 or short_liq > 0:
            if long_liq > short_liq * 2:
                liq_narrative = f"24h多头爆仓${long_liq:.1f}M，空头力量占优"
            elif short_liq > long_liq * 2:
                liq_narrative = f"24h空头爆仓${short_liq:.1f}M，多头力量占优"
            else:
                liq_narrative = f"24h爆仓多空均衡（多${long_liq:.1f}M/空${short_liq:.1f}M）"
            narratives.append(liq_narrative)

        # 5. 订单簿压力
        ob = market_data.get("orderbook", {})
        if ob:
            depth_ratio = ob.get("depth_ratio", 1.0)
            spread_pct = ob.get("spread_pct", 0) * 100

            if depth_ratio > 1.5:
                ob_desc = f"买盘深度明显强于卖盘（{depth_ratio:.2f}倍），下方支撑较强"
            elif depth_ratio < 0.67:
                ob_desc = f"卖盘深度明显强于买盘（{1/depth_ratio:.2f}倍），上方压力较大"
            else:
                ob_desc = "买卖盘深度相对均衡"

            if spread_pct > 0.1:
                ob_desc += f"，但价差较大（{spread_pct:.3f}%），流动性一般"
            else:
                ob_desc += f"，价差正常（{spread_pct:.3f}%）"

            narratives.append(f"【订单簿】{ob_desc}")

        # 生成核心结论
        market_type, sentiment, summary = self._generate_summary(
            market_data, narratives
        )

        # 计算关键支撑压力（简化版）
        current_price = market_data.get("current_price", 0)
        key_support, key_resistance = self._calculate_key_levels(market_data)

        full_narrative = "。".join(narratives)

        return {
            "market_narrative": full_narrative,
            "market_type": market_type,
            "key_supports": key_support, "key_support": key_support,
            "key_resistances": key_resistance, "key_resistance": key_resistance,
            "sentiment": sentiment,
            "summary": summary,
            "confidence": self._assess_confidence(market_data, narratives)
        }

    # ============ 辅助方法 ============

    def _analyze_candle_sequence(self, df: pd.DataFrame) -> str:
        """分析连续K线形态"""
        closes = df["close"].values
        opens = df["open"].values

        # 判断连续同色
        colors = ["红" if c >= o else "绿" for c, o in zip(closes, opens)]

        consecutive_same = 1
        for i in range(len(colors) - 2, -1, -1):
            if colors[i] == colors[i + 1]:
                consecutive_same += 1
            else:
                break

        recent_color = colors[-1]
        recent_change = (closes[-1] - closes[-consecutive_same]) / closes[-consecutive_same] * 100

        if consecutive_same >= 3:
            return f"连续{consecutive_same}根{recent_color}K线，累计{'上涨' if recent_color == '红' else '下跌'}{abs(recent_change):.2f}%"
        else:
            return f"近期K线交替，处于整理状态"

    def _analyze_volume(self, df: pd.DataFrame) -> str:
        """分析成交量"""
        recent_vol = df["volume"].tail(5).mean()
        hist_vol = df["volume"].tail(self.volume_ma_period).mean()

        if hist_vol == 0:
            return "【成交量】数据不足"

        ratio = recent_vol / hist_vol

        if ratio > 2.0:
            return f"【成交量】近期放量，为20日均量的{ratio:.1f}倍，资金异动明显"
        elif ratio > 1.5:
            return f"【成交量】成交量放大，为20日均量的{ratio:.1f}倍"
        elif ratio < 0.5:
            return f"【成交量】成交量萎缩，为20日均量的{ratio:.1f}倍，市场观望"
        else:
            return f"【成交量】成交量正常，为20日均量的{ratio:.1f}倍"

    def _identify_candle_patterns(self, candle: pd.Series) -> List[CandlePattern]:
        """识别单根K线形态"""
        patterns = []

        open_p = candle["open"]
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]

        body = abs(close - open_p)
        upper_shadow = high - max(open_p, close)
        lower_shadow = min(open_p, close) - low
        total_range = high - low

        if total_range == 0:
            return patterns

        # 十字星
        if body / total_range < 0.1:
            patterns.append(CandlePattern(
                name="doji",
                strength="medium",
                description="出现十字星，多空力量暂时均衡"
            ))

        # 锤头/吊颈线
        elif lower_shadow > body * 2 and upper_shadow < body * 0.5:
            if close > open_p:
                patterns.append(CandlePattern(
                    name="hammer",
                    strength="strong" if lower_shadow > body * 3 else "medium",
                    description="出现锤头形态，下方买盘支撑明显"
                ))
            else:
                patterns.append(CandlePattern(
                    name="hanging_man",
                    strength="medium",
                    description="出现吊颈线，需警惕反转风险"
                ))

        # 流星线
        elif upper_shadow > body * 2 and lower_shadow < body * 0.5:
            patterns.append(CandlePattern(
                name="shooting_star",
                strength="medium",
                description="出现流星线，上方抛压较重"
            ))

        return patterns

    def _analyze_price_position(self, df: pd.DataFrame) -> str:
        """分析价格位置"""
        current = df["close"].iloc[-1]
        high_20 = df["high"].tail(20).max()
        low_20 = df["low"].tail(20).min()

        range_size = high_20 - low_20
        if range_size == 0:
            return "【位置】价格处于区间中部"

        position = (current - low_20) / range_size

        if position > 0.8:
            return f"【位置】价格接近20日高点，处于区间上沿（{position*100:.1f}%位置）"
        elif position < 0.2:
            return f"【位置】价格接近20日低点，处于区间下沿（{position*100:.1f}%位置）"
        else:
            return f"【位置】价格处于区间中部（{position*100:.1f}%位置）"

    def _determine_trend(self, df: pd.DataFrame) -> str:
        """判断趋势"""
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values

        # 简单趋势判断
        hh = highs[-1] > highs[-5:].max()
        hl = lows[-1] > lows[-5:].mean()
        lh = highs[-1] < highs[-5:].mean()
        ll = lows[-1] < lows[-5:].min()

        if hh and hl:
            return "上升趋势"
        elif lh and ll:
            return "下降趋势"
        else:
            # 检查是否震荡
            range_pct = (highs.max() - lows.min()) / closes.mean() * 100
            if range_pct < 5:
                return "窄幅震荡"
            else:
                return "宽幅震荡"

    def _analyze_timeframe_consistency(self, multi_tf: Dict[str, pd.DataFrame]) -> str:
        """分析多周期一致性"""
        trends = {}
        for tf, df in multi_tf.items():
            if len(df) >= 10:
                trends[tf] = self._determine_trend(df.tail(20))

        if len(trends) < 2:
            return ""

        up_count = sum(1 for t in trends.values() if "上升" in t)
        down_count = sum(1 for t in trends.values() if "下降" in t)
        total = len(trends)

        if up_count == total:
            return "【多周期共振】各周期均呈上升趋势，多头共振"
        elif down_count == total:
            return "【多周期共振】各周期均呈下降趋势，空头共振"
        elif up_count > down_count:
            return "【多周期分歧】大周期偏空，小周期偏多，存在背离"
        elif down_count > up_count:
            return "【多周期分歧】大周期偏多，小周期偏空，存在背离"
        else:
            return "【多周期分歧】各周期信号混乱，方向不明"

    def _generate_summary(self, market_data: dict, narratives: list) -> Tuple[str, str, str]:
        """生成核心结论"""
        price_change = market_data.get("price_change_24h", 0)
        funding = market_data.get("funding_rate", 0)

        # 判断市场类型
        if price_change > 5:
            market_type = "trend_up"
            sentiment = "extreme_greed" if funding > 0.001 else "bullish"
        elif price_change < -5:
            market_type = "trend_down"
            sentiment = "extreme_fear" if funding < -0.001 else "bearish"
        elif abs(price_change) < 2:
            market_type = "consolidation"
            sentiment = "neutral"
        else:
            market_type = "breakout_imminent"
            sentiment = "bullish" if price_change > 0 else "bearish"

        # 生成一句话总结
        direction = "上涨" if price_change > 0 else "下跌"
        summary = f"24h{direction}{abs(price_change):.2f}%，{sentiment}情绪，处于{market_type}状态"

        return market_type, sentiment, summary

    def _calculate_key_levels(self, market_data: dict) -> Tuple[List[float], List[float]]:
        """计算关键支撑压力位（简化版）"""
        current = market_data.get("current_price", 0)

        # 基于整数位和当前价格计算
        # 实际实现中应该基于历史高低点、成交密集区等
        support_1 = round(current * 0.95 / 1000) * 1000
        support_2 = round(current * 0.90 / 1000) * 1000
        resistance_1 = round(current * 1.05 / 1000) * 1000
        resistance_2 = round(current * 1.10 / 1000) * 1000

        return [support_1, support_2], [resistance_1, resistance_2]

    def _assess_confidence(self, market_data: dict, narratives: list) -> str:
        """评估置信度"""
        # 基于数据完整性和一致性评估
        score = 0

        # 数据完整性
        if market_data.get("multi_tf_klines"):
            score += 1
        if market_data.get("funding_rate") is not None:
            score += 1
        if market_data.get("orderbook"):
            score += 1

        if score >= 3:
            return "high"
        elif score >= 2:
            return "medium"
        else:
            return "low"
