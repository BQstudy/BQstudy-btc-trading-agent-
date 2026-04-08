"""
支撑压力分析模块
识别关键价格结构：支撑、压力、成交密集区
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class PriceLevel:
    """价格水平数据结构"""
    price: float
    strength: str  # strong/medium/weak
    level_type: str  # support/resistance
    basis: str  # 形成原因
    touches: int  # 触及次数
    recency: int  # 最近触及距离（周期数）


@dataclass
class LevelAnalysis:
    """支撑压力分析结果"""
    critical_supports: List[PriceLevel]
    critical_resistances: List[PriceLevel]
    nearest_support: Optional[PriceLevel]
    nearest_resistance: Optional[PriceLevel]
    current_zone: str  # 支撑区/压力区/中性区/突破区
    volume_profile: Dict  # 成交量分布
    analysis_reasoning: str


class LevelAnalyzer:
    """
    支撑压力分析器
    识别当前最重要的支撑和压力位
    """

    def __init__(self):
        self.lookback_periods = [20, 50, 100]
        self.round_number_interval = 5000  # 整数位间隔
        self.min_touches = 2  # 最小触及次数
        self.touch_threshold_pct = 0.005  # 0.5%范围内视为触及

    def analyze(self, multi_tf_data: Dict[str, pd.DataFrame], current_price: float) -> LevelAnalysis:
        """
        综合分析支撑压力
        """
        if "4h" not in multi_tf_data or len(multi_tf_data["4h"]) < 20:
            return self._create_empty_analysis("数据不足")

        df_4h = multi_tf_data["4h"]
        df_1d = multi_tf_data.get("1d", df_4h)

        # 1. 历史高低点
        swing_levels = self._identify_swing_levels(df_4h)

        # 2. 成交密集区（Volume Profile）
        volume_nodes = self._calculate_volume_profile(df_4h)

        # 3. 整数关卡
        round_numbers = self._identify_round_numbers(current_price)

        # 4. 趋势线接触点
        trendline_levels = self._identify_trendline_levels(df_4h, current_price)

        # 5. 合并并排序
        all_levels = self._merge_levels(
            swing_levels, volume_nodes, round_numbers, trendline_levels,
            current_price
        )

        # 6. 分类支撑压力
        supports, resistances = self._classify_levels(all_levels, current_price)

        # 7. 找出最近的
        nearest_support = self._find_nearest(supports, current_price, "below")
        nearest_resistance = self._find_nearest(resistances, current_price, "above")

        # 8. 确定当前区域
        current_zone = self._determine_current_zone(
            current_price, nearest_support, nearest_resistance
        )

        # 9. 生成分析理由
        reasoning = self._generate_reasoning(
            supports, resistances, current_zone, volume_nodes
        )

        return LevelAnalysis(
            critical_supports=supports[:5],  # 最多5个
            critical_resistances=resistances[:5],
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            current_zone=current_zone,
            volume_profile=volume_nodes,
            analysis_reasoning=reasoning
        )

    def _identify_swing_levels(self, df: pd.DataFrame) -> List[PriceLevel]:
        """
        识别波段高低点
        """
        if len(df) < 20:
            return []

        highs = df["high"].values
        lows = df["low"].values

        levels = []

        # 简单的高低点检测（3周期极值）
        for i in range(2, len(df) - 2):
            # 局部高点
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                levels.append({
                    "price": highs[i],
                    "type": "swing_high",
                    "index": i
                })

            # 局部低点
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                levels.append({
                    "price": lows[i],
                    "type": "swing_low",
                    "index": i
                })

        # 聚类相近的水平
        return self._cluster_levels(levels, len(df))

    def _calculate_volume_profile(self, df: pd.DataFrame, num_bins: int = 20) -> Dict:
        """
        计算成交量分布（Volume Profile）
        """
        if len(df) < 20 or "volume" not in df.columns:
            return {}

        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        volumes = df["volume"].values

        price_min = np.min(lows)
        price_max = np.max(highs)
        bin_size = (price_max - price_min) / num_bins

        # 每个价格区间的成交量
        volume_by_price = defaultdict(float)

        for i in range(len(df)):
            # 简化：将成交量分配给收盘价所在区间
            price = closes[i]
            vol = volumes[i]
            bin_idx = int((price - price_min) / bin_size)
            bin_idx = max(0, min(bin_idx, num_bins - 1))
            volume_by_price[bin_idx] += vol

        # 找出高成交量节点（POC）
        if volume_by_price:
            max_vol_bin = max(volume_by_price.items(), key=lambda x: x[1])
            poc_price = price_min + (max_vol_bin[0] + 0.5) * bin_size

            # 价值区间（70%成交量）
            sorted_bins = sorted(volume_by_price.items(), key=lambda x: x[1], reverse=True)
            cum_vol = 0
            total_vol = sum(volume_by_price.values())
            value_bins = []

            for bin_idx, vol in sorted_bins:
                cum_vol += vol
                value_bins.append(bin_idx)
                if cum_vol >= total_vol * 0.7:
                    break

            value_low = price_min + min(value_bins) * bin_size
            value_high = price_min + (max(value_bins) + 1) * bin_size

            return {
                "poc": poc_price,
                "value_area_low": value_low,
                "value_area_high": value_high,
                "volume_by_price": dict(volume_by_price)
            }

        return {}

    def _identify_round_numbers(self, current_price: float) -> List[PriceLevel]:
        """
        识别整数心理关卡
        """
        levels = []

        # 基于当前价格生成附近的整数位
        base = int(current_price / self.round_number_interval) * self.round_number_interval

        for offset in [-2, -1, 0, 1, 2]:
            price = base + offset * self.round_number_interval
            if price > 0:
                strength = "strong" if offset == 0 else "medium"
                level_type = "support" if price < current_price else "resistance"

                levels.append(PriceLevel(
                    price=price,
                    strength=strength,
                    level_type=level_type,
                    basis="整数心理关卡",
                    touches=0,
                    recency=0
                ))

        return levels

    def _identify_trendline_levels(self, df: pd.DataFrame, current_price: float) -> List[PriceLevel]:
        """
        识别趋势线接触点
        """
        if len(df) < 20:
            return []

        levels = []
        highs = df["high"].values
        lows = df["low"].values

        # 简单趋势线：连接最近两个高点/低点
        # 上升趋势线（连接低点）
        if len(lows) >= 10:
            recent_lows_idx = np.argsort(lows[-10:])[:3] + len(lows) - 10
            if len(recent_lows_idx) >= 2:
                # 拟合趋势线
                x = recent_lows_idx
                y = lows[recent_lows_idx]
                slope, intercept = np.polyfit(x, y, 1)

                # 当前价格在趋势线上的投影
                trendline_price = slope * (len(df) - 1) + intercept

                if abs(trendline_price - current_price) / current_price < 0.02:
                    levels.append(PriceLevel(
                        price=trendline_price,
                        strength="medium",
                        level_type="support" if slope > 0 else "resistance",
                        basis="上升趋势线接触点",
                        touches=len(recent_lows_idx),
                        recency=0
                    ))

        return levels

    def _cluster_levels(
        self,
        raw_levels: List[Dict],
        total_length: int,
        cluster_threshold_pct: float = 0.01
    ) -> List[PriceLevel]:
        """
        聚类相近的价格水平
        """
        if not raw_levels:
            return []

        # 按价格排序
        sorted_levels = sorted(raw_levels, key=lambda x: x["price"])

        clusters = []
        current_cluster = [sorted_levels[0]]

        for level in sorted_levels[1:]:
            # 检查是否在同一聚类
            cluster_avg = np.mean([l["price"] for l in current_cluster])
            if abs(level["price"] - cluster_avg) / cluster_avg < cluster_threshold_pct:
                current_cluster.append(level)
            else:
                # 保存当前聚类
                clusters.append(self._create_level_from_cluster(current_cluster, total_length))
                current_cluster = [level]

        # 保存最后一个聚类
        if current_cluster:
            clusters.append(self._create_level_from_cluster(current_cluster, total_length))

        return clusters

    def _create_level_from_cluster(self, cluster: List[Dict], total_length: int) -> PriceLevel:
        """从聚类创建价格水平"""
        avg_price = np.mean([l["price"] for l in cluster])

        # 判断类型
        high_count = sum(1 for l in cluster if l.get("type") == "swing_high")
        low_count = sum(1 for l in cluster if l.get("type") == "swing_low")

        if high_count > low_count:
            level_type = "resistance"
            basis = "前期高点密集区"
        elif low_count > high_count:
            level_type = "support"
            basis = "前期低点密集区"
        else:
            level_type = "neutral"
            basis = "成交密集区"

        # 计算强度
        touches = len(cluster)
        if touches >= 4:
            strength = "strong"
        elif touches >= 2:
            strength = "medium"
        else:
            strength = "weak"

        # 计算最近触及
        recent_indices = [l.get("index", 0) for l in cluster]
        recency = total_length - max(recent_indices) if recent_indices else total_length

        return PriceLevel(
            price=avg_price,
            strength=strength,
            level_type=level_type,
            basis=basis,
            touches=touches,
            recency=recency
        )

    def _merge_levels(
        self,
        swing_levels: List[PriceLevel],
        volume_nodes: Dict,
        round_numbers: List[PriceLevel],
        trendline_levels: List[PriceLevel],
        current_price: float
    ) -> List[PriceLevel]:
        """合并所有来源的水平"""
        all_levels = []

        # 添加波段高低点
        all_levels.extend(swing_levels)

        # 添加成交量节点
        if volume_nodes:
            poc = volume_nodes.get("poc")
            if poc:
                all_levels.append(PriceLevel(
                    price=poc,
                    strength="strong",
                    level_type="neutral",
                    basis="成交量最大节点(POC)",
                    touches=0,
                    recency=0
                ))

            val = volume_nodes.get("value_area_low")
            vah = volume_nodes.get("value_area_high")
            if val:
                all_levels.append(PriceLevel(
                    price=val,
                    strength="medium",
                    level_type="support",
                    basis="价值区间下沿",
                    touches=0,
                    recency=0
                ))
            if vah:
                all_levels.append(PriceLevel(
                    price=vah,
                    strength="medium",
                    level_type="resistance",
                    basis="价值区间上沿",
                    touches=0,
                    recency=0
                ))

        # 添加整数位
        all_levels.extend(round_numbers)

        # 添加趋势线
        all_levels.extend(trendline_levels)

        # 去重并排序
        return self._deduplicate_levels(all_levels)

    def _deduplicate_levels(self, levels: List[PriceLevel]) -> List[PriceLevel]:
        """去重并排序价格水平"""
        if not levels:
            return []

        # 按价格聚类
        sorted_levels = sorted(levels, key=lambda x: x.price)

        result = []
        current_cluster = [sorted_levels[0]]

        for level in sorted_levels[1:]:
            cluster_avg = np.mean([l.price for l in current_cluster])
            if abs(level.price - cluster_avg) / cluster_avg < self.touch_threshold_pct:
                current_cluster.append(level)
            else:
                # 合并聚类
                merged = self._merge_cluster(current_cluster)
                result.append(merged)
                current_cluster = [level]

        # 处理最后一个聚类
        if current_cluster:
            merged = self._merge_cluster(current_cluster)
            result.append(merged)

        return sorted(result, key=lambda x: x.price)

    def _merge_cluster(self, cluster: List[PriceLevel]) -> PriceLevel:
        """合并同一聚类中的水平"""
        avg_price = np.mean([l.price for l in cluster])

        # 选择最强的
        strength_order = {"strong": 3, "medium": 2, "weak": 1}
        strongest = max(cluster, key=lambda x: strength_order.get(x.strength, 0))

        # 合并理由
        bases = [l.basis for l in cluster]
        merged_basis = " + ".join(set(bases))

        # 合并触及次数
        total_touches = sum(l.touches for l in cluster)
        min_recency = min(l.recency for l in cluster)

        return PriceLevel(
            price=avg_price,
            strength=strongest.strength,
            level_type=strongest.level_type,
            basis=merged_basis,
            touches=total_touches,
            recency=min_recency
        )

    def _classify_levels(
        self,
        levels: List[PriceLevel],
        current_price: float
    ) -> Tuple[List[PriceLevel], List[PriceLevel]]:
        """将水平分类为支撑或压力"""
        supports = []
        resistances = []

        for level in levels:
            if level.price < current_price * 0.995:  # 低于当前价
                # 转为支撑
                support_level = PriceLevel(
                    price=level.price,
                    strength=level.strength,
                    level_type="support",
                    basis=level.basis,
                    touches=level.touches,
                    recency=level.recency
                )
                supports.append(support_level)
            elif level.price > current_price * 1.005:  # 高于当前价
                # 转为压力
                resistance_level = PriceLevel(
                    price=level.price,
                    strength=level.strength,
                    level_type="resistance",
                    basis=level.basis,
                    touches=level.touches,
                    recency=level.recency
                )
                resistances.append(resistance_level)

        # 按强度排序
        strength_order = {"strong": 3, "medium": 2, "weak": 1}
        supports.sort(key=lambda x: (strength_order.get(x.strength, 0), -x.recency), reverse=True)
        resistances.sort(key=lambda x: (strength_order.get(x.strength, 0), -x.recency), reverse=True)

        return supports, resistances

    def _find_nearest(
        self,
        levels: List[PriceLevel],
        current_price: float,
        direction: str
    ) -> Optional[PriceLevel]:
        """找出最近的水平"""
        if not levels:
            return None

        if direction == "below":
            # 找低于当前价的最近水平
            valid_levels = [l for l in levels if l.price < current_price]
            if valid_levels:
                return max(valid_levels, key=lambda x: x.price)
        else:
            # 找高于当前价的最近水平
            valid_levels = [l for l in levels if l.price > current_price]
            if valid_levels:
                return min(valid_levels, key=lambda x: x.price)

        return None

    def _determine_current_zone(
        self,
        current_price: float,
        nearest_support: Optional[PriceLevel],
        nearest_resistance: Optional[PriceLevel]
    ) -> str:
        """确定当前价格区域"""
        if not nearest_support and not nearest_resistance:
            return "中性区"

        # 计算到支撑和压力的距离
        dist_to_support = current_price - nearest_support.price if nearest_support else float('inf')
        dist_to_resistance = nearest_resistance.price - current_price if nearest_resistance else float('inf')

        # 归一化
        if nearest_support:
            support_range = current_price - nearest_support.price
        if nearest_resistance:
            resistance_range = nearest_resistance.price - current_price

        # 判断区域
        if dist_to_support < dist_to_resistance * 0.3:
            return "支撑区"
        elif dist_to_resistance < dist_to_support * 0.3:
            return "压力区"
        elif dist_to_support < current_price * 0.01 and dist_to_resistance > current_price * 0.02:
            return "突破区"  # 接近突破压力
        elif dist_to_resistance < current_price * 0.01 and dist_to_support > current_price * 0.02:
            return "跌破区"  # 接近跌破支撑
        else:
            return "中性区"

    def _generate_reasoning(
        self,
        supports: List[PriceLevel],
        resistances: List[PriceLevel],
        current_zone: str,
        volume_nodes: Dict
    ) -> str:
        """生成分析理由"""
        reasoning_parts = []

        # 支撑分析
        if supports:
            strongest_support = supports[0]
            reasoning_parts.append(
                f"最强支撑在{strongest_support.price:.0f}（{strongest_support.basis}，"
                f"触及{strongest_support.touches}次）"
            )

        # 压力分析
        if resistances:
            strongest_resistance = resistances[0]
            reasoning_parts.append(
                f"最强压力在{strongest_resistance.price:.0f}（{strongest_resistance.basis}，"
                f"触及{strongest_resistance.touches}次）"
            )

        # 成交量分布
        if volume_nodes:
            poc = volume_nodes.get("poc")
            if poc:
                reasoning_parts.append(f"成交密集区(POC)在{poc:.0f}")

        # 当前区域
        reasoning_parts.append(f"当前处于{current_zone}")

        return "。".join(reasoning_parts)

    def _create_empty_analysis(self, reason: str) -> LevelAnalysis:
        """创建空分析结果"""
        return LevelAnalysis(
            critical_supports=[],
            critical_resistances=[],
            nearest_support=None,
            nearest_resistance=None,
            current_zone="unknown",
            volume_profile={},
            analysis_reasoning=reason
        )
