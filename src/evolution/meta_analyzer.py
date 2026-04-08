"""
元认知分析引擎 - Phase 5 核心
分析Agent的判断模式，识别系统性偏差
"""

import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import statistics


@dataclass
class PerformanceMetrics:
    """绩效指标"""
    total_trades: int
    win_count: int
    loss_count: int
    win_rate: float
    avg_pnl_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float
    max_consecutive_wins: int
    max_consecutive_losses: int


@dataclass
class BiasAnalysis:
    """偏差分析"""
    long_bias_score: float  # 做多倾向分数
    early_entry_bias: bool  # 入场过早倾向
    stop_tightness: str  # 止损设置倾向 tight/normal/loose
    time_zone_weakness: List[str]  # 表现差的时间段


@dataclass
class MetaAnalysisReport:
    """元分析报告"""
    period: str
    generated_at: str

    # 整体绩效
    overall_performance: PerformanceMetrics

    # 行情类型适配性
    regime_performance: Dict[str, PerformanceMetrics]

    # 系统性偏差
    biases: BiasAnalysis

    # 高价值决策特征
    high_value_patterns: List[str]
    loss_patterns: List[str]

    # 提示词优化建议
    prompt_optimization_suggestions: List[Dict]

    # 风格漂移检测
    style_drift_detected: bool
    style_drift_details: str

    # 完整思维链
    chain_of_thought: str


class MetaAnalyzer:
    """
    元认知分析器
    分析Agent的判断模式而非行情本身
    """

    def __init__(self, trade_logger):
        self.trade_logger = trade_logger

    def analyze(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> MetaAnalysisReport:
        """
        执行元分析

        Args:
            start_date: 开始日期 (ISO格式)
            end_date: 结束日期 (ISO格式)

        Returns:
            MetaAnalysisReport对象
        """
        # 获取交易记录
        trades = self.trade_logger.get_recent_trades(limit=1000)

        # 过滤日期
        if start_date or end_date:
            trades = self._filter_by_date(trades, start_date, end_date)

        if not trades:
            return self._create_empty_report("无交易记录")

        # 1. 整体绩效分析
        overall = self._calculate_overall_performance(trades)

        # 2. 行情类型适配性
        regime_perf = self._analyze_regime_performance(trades)

        # 3. 系统性偏差识别
        biases = self._identify_biases(trades)

        # 4. 高价值决策特征
        high_value, loss_patterns = self._extract_patterns(trades)

        # 5. 提示词优化建议
        suggestions = self._generate_prompt_suggestions(trades, biases, regime_perf)

        # 6. 风格漂移检测
        drift_detected, drift_details = self._detect_style_drift(trades)

        # 7. 生成思维链
        cot = self._generate_analysis_cot(
            overall, regime_perf, biases, high_value, loss_patterns
        )

        return MetaAnalysisReport(
            period=f"{start_date or 'all'} to {end_date or 'now'}",
            generated_at=datetime.utcnow().isoformat() + "Z",
            overall_performance=overall,
            regime_performance=regime_perf,
            biases=biases,
            high_value_patterns=high_value,
            loss_patterns=loss_patterns,
            prompt_optimization_suggestions=suggestions,
            style_drift_detected=drift_detected,
            style_drift_details=drift_details,
            chain_of_thought=cot
        )

    def _filter_by_date(
        self,
        trades: List,
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> List:
        """按日期过滤交易"""
        filtered = []
        for trade in trades:
            entry_time = trade.entry_time
            if start_date and entry_time < start_date:
                continue
            if end_date and entry_time > end_date:
                continue
            filtered.append(trade)
        return filtered

    def _calculate_overall_performance(self, trades: List) -> PerformanceMetrics:
        """计算整体绩效"""
        closed_trades = [t for t in trades if t.outcome and t.outcome != "open"]

        if not closed_trades:
            return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

        total = len(closed_trades)
        wins = [t for t in closed_trades if t.outcome == "win"]
        losses = [t for t in closed_trades if t.outcome == "loss"]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = win_count / total * 100 if total > 0 else 0

        pnl_values = [t.pnl_pct for t in closed_trades]
        avg_pnl = statistics.mean(pnl_values) if pnl_values else 0

        win_pnl = [t.pnl_pct for t in wins]
        loss_pnl = [t.pnl_pct for t in losses]

        avg_win = statistics.mean(win_pnl) if win_pnl else 0
        avg_loss = statistics.mean(loss_pnl) if loss_pnl else 0

        # 盈亏比
        total_wins = sum(win_pnl)
        total_losses = abs(sum(loss_pnl))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # 连续赢亏
        max_consec_wins, max_consec_losses = self._calculate_consecutive(closed_trades)

        return PerformanceMetrics(
            total_trades=total,
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate,
            avg_pnl_pct=avg_pnl,
            avg_win_pct=avg_win,
            avg_loss_pct=avg_loss,
            profit_factor=profit_factor,
            max_consecutive_wins=max_consec_wins,
            max_consecutive_losses=max_consec_losses
        )

    def _calculate_consecutive(self, trades: List) -> Tuple[int, int]:
        """计算最大连续赢亏"""
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for trade in trades:
            if trade.outcome == "win":
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif trade.outcome == "loss":
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        return max_wins, max_losses

    def _analyze_regime_performance(self, trades: List) -> Dict[str, PerformanceMetrics]:
        """分析不同行情类型的表现"""
        regime_trades = defaultdict(list)

        for trade in trades:
            if trade.market_type:
                regime_trades[trade.market_type].append(trade)

        regime_perf = {}
        for regime, regime_trade_list in regime_trades.items():
            regime_perf[regime] = self._calculate_overall_performance(regime_trade_list)

        return regime_perf

    def _identify_biases(self, trades: List) -> BiasAnalysis:
        """识别系统性偏差"""
        closed_trades = [t for t in trades if t.outcome and t.outcome != "open"]

        if not closed_trades:
            return BiasAnalysis(0.5, False, "normal", [])

        # 1. 多空倾向
        long_trades = [t for t in closed_trades if t.direction == "long"]
        short_trades = [t for t in closed_trades if t.direction == "short"]

        long_count = len(long_trades)
        short_count = len(short_trades)
        total = long_count + short_count

        if total > 0:
            long_bias = long_count / total
        else:
            long_bias = 0.5

        # 2. 入场过早检测
        # 简化：检查持仓时间过短且亏损的交易
        early_losses = [
            t for t in closed_trades
            if t.outcome == "loss"
            and t.holding_period_hours < 1  # 持仓小于1小时
        ]
        early_entry_bias = len(early_losses) > len(closed_trades) * 0.2  # 超过20%

        # 3. 止损设置分析
        # 简化：检查止损被扫后价格反转的情况
        stop_analysis = "normal"  # 需要更详细的数据

        # 4. 时间段弱点
        time_zone_weakness = []
        # 简化实现，实际可以按小时分析

        return BiasAnalysis(
            long_bias_score=long_bias,
            early_entry_bias=early_entry_bias,
            stop_tightness=stop_analysis,
            time_zone_weakness=time_zone_weakness
        )

    def _extract_patterns(self, trades: List) -> Tuple[List[str], List[str]]:
        """提取高价值和亏损模式"""
        closed_trades = [t for t in trades if t.outcome and t.outcome != "open"]

        # 盈利最大的交易
        wins = [t for t in closed_trades if t.outcome == "win"]
        wins.sort(key=lambda x: x.pnl_pct, reverse=True)

        # 亏损最大的交易
        losses = [t for t in closed_trades if t.outcome == "loss"]
        losses.sort(key=lambda x: x.pnl_pct)

        high_value_patterns = []
        loss_patterns = []

        # 分析盈利交易的共同特征
        if wins:
            top_wins = wins[:5]
            market_types = set(t.market_type for t in top_wins)
            if len(market_types) == 1:
                high_value_patterns.append(f"在{list(market_types)[0]}行情中表现优异")

            # 检查经验规则
            rules = [t.experience_rule for t in top_wins if t.experience_rule]
            if rules:
                high_value_patterns.append(f"高价值交易的经验: {rules[0]}")

        # 分析亏损交易的共同特征
        if losses:
            top_losses = losses[:5]
            market_types = set(t.market_type for t in top_losses)
            if len(market_types) == 1:
                loss_patterns.append(f"在{list(market_types)[0]}行情中表现较差")

            # 检查归因
            loss_reasons = []
            for t in top_losses:
                if t.attribution and "loss_reason" in t.attribution:
                    loss_reasons.append(t.attribution["loss_reason"])

            if loss_reasons:
                from collections import Counter
                most_common = Counter(loss_reasons).most_common(1)[0]
                loss_patterns.append(f"主要亏损原因: {most_common[0]} ({most_common[1]}次)")

        return high_value_patterns, loss_patterns

    def _generate_prompt_suggestions(
        self,
        trades: List,
        biases: BiasAnalysis,
        regime_perf: Dict[str, PerformanceMetrics]
    ) -> List[Dict]:
        """生成提示词优化建议"""
        suggestions = []

        # 1. 多空倾向修正
        if biases.long_bias_score > 0.7:
            suggestions.append({
                "target": "judgment_layer",
                "issue": "过度做多倾向",
                "suggestion": "在判断层提示词中增加'空头视角'权重",
                "expected_impact": "减少多头偏见，提高空头判断质量"
            })
        elif biases.long_bias_score < 0.3:
            suggestions.append({
                "target": "judgment_layer",
                "issue": "过度做空倾向",
                "suggestion": "在判断层提示词中增加'多头视角'权重",
                "expected_impact": "减少空头偏见，提高多头判断质量"
            })

        # 2. 入场时机修正
        if biases.early_entry_bias:
            suggestions.append({
                "target": "decision_layer",
                "issue": "入场过早",
                "suggestion": "在决策层增加'等待确认'步骤，要求至少2个确认信号",
                "expected_impact": "减少过早入场导致的亏损"
            })

        # 3. 行情类型适配
        for regime, perf in regime_perf.items():
            if perf.total_trades >= 5 and perf.win_rate < 40:
                suggestions.append({
                    "target": "perception_layer",
                    "issue": f"在{regime}行情中表现差",
                    "suggestion": f"在感知层增加{regime}识别难度，或建议回避",
                    "expected_impact": f"减少在{regime}行情中的错误交易"
                })

        return suggestions

    def _detect_style_drift(self, trades: List) -> Tuple[bool, str]:
        """检测风格漂移"""
        if len(trades) < 20:
            return False, "交易数量不足，无法检测风格漂移"

        # 分前半段和后半段比较
        mid = len(trades) // 2
        first_half = trades[:mid]
        second_half = trades[mid:]

        first_perf = self._calculate_overall_performance(first_half)
        second_perf = self._calculate_overall_performance(second_half)

        # 比较胜率
        win_rate_diff = abs(first_perf.win_rate - second_perf.win_rate)

        # 比较多空倾向
        first_long_ratio = len([t for t in first_half if t.direction == "long"]) / len(first_half) if first_half else 0.5
        second_long_ratio = len([t for t in second_half if t.direction == "long"]) / len(second_half) if second_half else 0.5
        long_ratio_diff = abs(first_long_ratio - second_long_ratio)

        drift_detected = win_rate_diff > 20 or long_ratio_diff > 0.3

        if drift_detected:
            details = f"胜率变化: {first_perf.win_rate:.1f}% -> {second_perf.win_rate:.1f}%, "
            details += f"做多倾向变化: {first_long_ratio:.2f} -> {second_long_ratio:.2f}"
        else:
            details = "风格稳定，无明显漂移"

        return drift_detected, details

    def _generate_analysis_cot(
        self,
        overall: PerformanceMetrics,
        regime_perf: Dict[str, PerformanceMetrics],
        biases: BiasAnalysis,
        high_value: List[str],
        loss_patterns: List[str]
    ) -> str:
        """生成分析思维链"""
        lines = [
            "【维度一：行情类型适配性】",
            f"- 整体胜率: {overall.win_rate:.1f}%",
            f"- 盈利交易平均收益: {overall.avg_win_pct:.2f}%",
            f"- 亏损交易平均亏损: {overall.avg_loss_pct:.2f}%",
            "- 各行情类型表现:"
        ]

        for regime, perf in regime_perf.items():
            lines.append(f"  * {regime}: 胜率{perf.win_rate:.1f}%, 交易{perf.total_trades}笔")

        lines.extend([
            "",
            "【维度二：系统性偏差识别】",
            f"- 做多倾向分数: {biases.long_bias_score:.2f}",
            f"- 入场过早倾向: {'是' if biases.early_entry_bias else '否'}",
            f"- 止损设置倾向: {biases.stop_tightness}",
            "",
            "【维度三：高价值决策特征】"
        ])

        for pattern in high_value:
            lines.append(f"- {pattern}")

        lines.extend([
            "",
            "【维度四：亏损模式】"
        ])

        for pattern in loss_patterns:
            lines.append(f"- {pattern}")

        return "\n".join(lines)

    def _create_empty_report(self, reason: str) -> MetaAnalysisReport:
        """创建空报告"""
        return MetaAnalysisReport(
            period="",
            generated_at=datetime.utcnow().isoformat() + "Z",
            overall_performance=PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            regime_performance={},
            biases=BiasAnalysis(0.5, False, "normal", []),
            high_value_patterns=[],
            loss_patterns=[],
            prompt_optimization_suggestions=[],
            style_drift_detected=False,
            style_drift_details=reason,
            chain_of_thought=reason
        )
