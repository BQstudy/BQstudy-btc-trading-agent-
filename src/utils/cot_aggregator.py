"""
CoT聚合推送器
实现每天4次定时推送，汇总推送前所有交易周期的CoT内容
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CycleCoT:
    """单次周期的CoT数据"""
    timestamp: str
    cycle_id: str

    # 实时价格
    current_price: float = 0.0

    # 各周期价格
    timeframe_prices: Dict[str, float] = field(default_factory=dict)

    # Phase 1: 感知
    market_type: str = ""
    sentiment: str = ""
    market_narrative: str = ""

    # Phase 2: 判断
    bias: str = ""
    confidence: float = 0.0
    debate_summary: str = ""

    # Phase 3: 决策
    action: str = ""
    entry_zone: List[float] = field(default_factory=list)
    stop_loss: float = 0.0
    risk_reward: float = 0.0

    # 完整CoT文本
    full_cot_perception: str = ""
    full_cot_judgment: str = ""
    full_cot_decision: str = ""


class CoTAggregator:
    """
    CoT聚合器
    缓存每个周期的CoT，在推送时间点汇总发送
    """

    # 推送时间点: 6:00, 12:00, 18:00, 24:00 (北京时间)
    PUSH_HOURS = [6, 12, 18, 0]  # 0点=24点

    def __init__(self):
        self.cycle_cots: List[CycleCoT] = []
        self.last_push_time: Optional[datetime] = None

    def add_cycle_cot(self, cot: CycleCoT):
        """添加单次周期的CoT"""
        self.cycle_cots.append(cot)

    def should_push_now(self) -> bool:
        """检查是否应该现在推送"""
        now = datetime.now()
        current_hour = now.hour

        # 检查是否到达推送时间点
        # 北京时间0点对应UTC前一天16点
        # 简化判断：每小时检查一次
        if self.last_push_time is None:
            return True

        # 计算上次推送后经过的小时数
        hours_since_last = (now - self.last_push_time).total_seconds() / 3600

        # 如果距离上次推送超过6小时，且当前时间在推送时间点附近
        if hours_since_last >= 6:
            # 检查是否在推送时间窗口（整点前后5分钟）
            if abs(current_hour % 6) < 0.1 or current_hour in [6, 12, 18, 0]:
                return True

        # 首次运行或新的一天，检查是否需要推送
        if self.last_push_time.date() != now.date():
            # 每天至少推送一次
            return True

        return False

    def get_pending_cots(self) -> List[CycleCoT]:
        """获取所有待推送的CoT"""
        return self.cycle_cots

    def clear_after_push(self):
        """推送后清除已发送的CoT"""
        self.last_push_time = datetime.now()
        # 保留最近一个周期作为缓存（用于对比）
        if len(self.cycle_cots) > 1:
            self.cycle_cots = self.cycle_cots[-1:]
        elif len(self.cycle_cots) == 1:
            self.cycle_cots = []

    def format_push_content(self, cots: List[CycleCoT]) -> str:
        """格式化推送内容"""
        if not cots:
            return "暂无待推送的交易周期"

        lines = []

        # 添加时间范围
        if cots:
            start_time = cots[0].timestamp
            end_time = cots[-1].timestamp
            lines.append(f"📊 <b>交易汇总 ({len(cots)}个周期)</b>")
            lines.append(f"⏰ 时间: {start_time[:16]} ~ {end_time[:16]}")
            lines.append("")

        # 汇总统计
        total_trades = sum(1 for cot in cots if cot.action in ["long", "short"])
        total_no_trade = sum(1 for cot in cots if cot.action == "no_trade")

        lines.append(f"📈 <b>交易统计</b>")
        lines.append(f"• 分析周期: {len(cots)}个")
        lines.append(f"• 发出交易: {total_trades}次")
        lines.append(f"• 观望: {total_no_trade}次")
        lines.append("")

        # 当前实时价格
        if cots:
            latest = cots[-1]
            lines.append(f"💰 <b>最新价格</b>")
            lines.append(f"• BTC实时: ${latest.current_price:,.2f}")
            for tf, price in latest.timeframe_prices.items():
                lines.append(f"• {tf}: ${price:,.2f}")
            lines.append("")

        # 每个周期的CoT汇总
        lines.append("📋 <b>各周期CoT汇总</b>")
        lines.append("")

        for i, cot in enumerate(cots):
            lines.append(f"━━━━━ 周期 {i+1} ━━━━━")
            lines.append(f"⏰ {cot.timestamp[11:19]} | 价格: ${cot.current_price:,.2f}")

            # 判断
            bias_emoji = "🟢" if cot.bias == "bullish" else "🔴" if cot.bias == "bearish" else "⚪"
            lines.append(f"{bias_emoji} 方向: {cot.bias} ({cot.confidence:.0%})")

            # 决策
            if cot.action == "no_trade":
                lines.append(f"⏸️ 决策: 不交易")
            else:
                rr_text = f"RR={cot.risk_reward:.1f}" if cot.risk_reward > 0 else ""
                lines.append(f"📌 决策: {cot.action.upper()} | 入场: {cot.entry_zone} | 止损: {cot.stop_loss:,.0f} | {rr_text}")

            # 简短分析
            if cot.debate_summary:
                summary = cot.debate_summary[:100] + "..." if len(cot.debate_summary) > 100 else cot.debate_summary
                lines.append(f"💡 分析: {summary}")

            # 关键价位
            lines.append("")

        # 结尾
        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"⏱️ 推送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(lines)

    def format_key_points(self, cot: CycleCoT) -> str:
        """格式化单次周期的要点化叙述"""
        lines = []

        # 价格
        lines.append(f"💰 价格: ${cot.current_price:,.2f}")

        # 判断
        bias_emoji = "🔴" if cot.bias == "bullish" else "🟢" if cot.bias == "bearish" else "⚪"
        lines.append(f"{bias_emoji} 判断: {cot.bias} ({cot.confidence:.0%})")

        # 决策
        if cot.action != "no_trade":
            rr_text = f"RR={cot.risk_reward:.1f}" if cot.risk_reward > 0 else ""
            lines.append(f"📌 交易: {cot.action.upper()} | 入${cot.entry_zone[0] if cot.entry_zone else 0:,.0f} | 止损${cot.stop_loss:,.0f} | {rr_text}")
        else:
            lines.append(f"⏸️ 观望")

        return "\n".join(lines)
