"""
交易复盘引擎 - Phase 4 核心
对每笔交易进行归因分析，提炼经验规律
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .trade_logger import TradeLog


class LossReason(Enum):
    """亏损原因分类"""
    DIRECTION_WRONG = "A"  # 判断错误（方向错）
    ENTRY_WRONG = "B"  # 入场位置错误
    STOP_WRONG = "C"  # 止损设置不合理
    EXECUTION_DISCIPLINE = "D"  # 执行纪律问题
    MARKET_EXTREME = "E"  # 市场极端情况


class WinReason(Enum):
    """盈利原因分类"""
    JUDGMENT_CORRECT = "judgment_correct"  # 判断正确
    EXECUTION_CORRECT = "execution_correct"  # 执行正确
    MARKET_LUCK = "market_luck"  # 市场配合（运气）
    COMBINED = "combined"  # 综合


@dataclass
class TradeReview:
    """交易复盘结果"""
    trade_id: str
    timestamp: str

    # 复盘分析
    original_judgment: str = ""
    result_analysis: str = ""

    # 归因分类
    outcome: str = ""  # win/loss
    win_reason: str = ""
    loss_reason: str = ""

    # 行情模式
    market_pattern: str = ""
    historical_performance_on_pattern: str = ""

    # 经验提炼
    experience_rule: str = ""
    rule_trigger_condition: str = ""
    rule_exceptions: str = ""

    # 行动建议
    action_suggestion: str = ""

    # 完整思维链
    chain_of_thought: str = ""


def generate_review_prompt(trade: TradeLog) -> str:
    """
    生成复盘提示词

    Args:
        trade: 交易记录

    Returns:
        提示词文本
    """
    return f"""
【交易复盘任务】

【交易基本信息】
- 交易ID: {trade.trade_id}
- 方向: {trade.direction}
- 入场时间: {trade.entry_time}
- 出场时间: {trade.exit_time}
- 入场价格: {trade.entry_price}
- 出场价格: {trade.exit_price}
- 盈亏: {trade.pnl_usdt} USDT ({trade.pnl_pct}%)
- 结果: {trade.outcome}
- 持仓时间: {trade.holding_period_hours}小时

【市场背景】
- 市场类型: {trade.market_type}
- 行情描述: {trade.market_narrative}

【入场时的判断】
{trade.decision_cot}

【复盘原则】
- 盈利的交易也可能是错误的（判断错但运气好）
- 亏损的交易也可能是正确的（判断对但被噪声止损）
- 关注过程，而不只是结果

【复盘步骤】（每步完整展开）

【Step 1：还原当时的判断逻辑】
  - 入场时，你基于什么判断做了这个决策？
  - 这个判断在当时的信息条件下是否合理？

【Step 2：结果分析】
  - 实际走势是否如预期？
  - 如果是，哪个分析要素判断最准确？
  - 如果否，哪个判断出了问题？

【Step 3：归因分类】
  盈利原因分类：判断正确 / 执行正确 / 市场配合（运气）/ 综合
  亏损原因分类：
    A. 判断错误（方向错）
    B. 入场位置错误（逻辑对但进早了/进晚了）
    C. 止损设置不合理（太紧/太松）
    D. 执行纪律问题（没按计划执行）
    E. 市场极端情况（黑天鹅/流动性不足）

【Step 4：行情模式识别】
  - 这次的行情属于什么类型？（趋势延续/假突破/震荡反转等）
  - 你在这类行情中的历史表现如何？
  - 这是否是你的能力圈范围内的交易？

【Step 5：经验提炼】
  - 提炼一条可以加入「经验库」的规律（30字以内）
  - 这条规律对应的触发条件是什么？
  - 这条规律的适用范围和例外情况是什么？

【Step 6：行动建议】
  - 下次遇到类似情况，具体应该做什么不同的处理？
  - 是否需要调整某个判断标准？

【输出格式】
{{
    "original_judgment": "还原的当时判断逻辑",
    "result_analysis": "结果分析",
    "outcome": "win|loss",
    "win_reason": "judgment_correct|execution_correct|market_luck|combined",
    "loss_reason": "A|B|C|D|E",
    "market_pattern": "行情模式",
    "historical_performance_on_pattern": "历史表现",
    "experience_rule": "提炼的经验规律（30字以内）",
    "rule_trigger_condition": "触发条件",
    "rule_exceptions": "例外情况",
    "action_suggestion": "行动建议",
    "chain_of_thought": "完整复盘推理过程"
}}
"""


def parse_review_response(response_text: str) -> TradeReview:
    """
    解析复盘响应
    """
    try:
        data = json.loads(response_text)

        return TradeReview(
            trade_id="",  # 由上层填充
            timestamp=datetime.utcnow().isoformat() + "Z",
            original_judgment=data.get("original_judgment", ""),
            result_analysis=data.get("result_analysis", ""),
            outcome=data.get("outcome", ""),
            win_reason=data.get("win_reason", ""),
            loss_reason=data.get("loss_reason", ""),
            market_pattern=data.get("market_pattern", ""),
            historical_performance_on_pattern=data.get("historical_performance_on_pattern", ""),
            experience_rule=data.get("experience_rule", ""),
            rule_trigger_condition=data.get("rule_trigger_condition", ""),
            rule_exceptions=data.get("rule_exceptions", ""),
            action_suggestion=data.get("action_suggestion", ""),
            chain_of_thought=data.get("chain_of_thought", "")
        )
    except json.JSONDecodeError:
        # 解析失败返回空复盘
        return TradeReview(
            trade_id="",
            timestamp=datetime.utcnow().isoformat() + "Z",
            chain_of_thought=response_text
        )


class ReviewEngine:
    """
    复盘引擎
    自动触发交易复盘流程
    """

    def __init__(self, trade_logger):
        self.trade_logger = trade_logger

    def review_trade(self, trade_id: str, llm_client=None) -> TradeReview:
        """
        复盘单笔交易

        Args:
            trade_id: 交易ID
            llm_client: LLM客户端（可选，用于自动复盘）

        Returns:
            TradeReview对象
        """
        # 获取交易记录
        trade = self.trade_logger.get_trade(trade_id)
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")

        # 生成复盘提示词
        prompt = generate_review_prompt(trade)

        # 如果有LLM客户端，自动执行复盘
        if llm_client:
            # 这里应该调用LLM
            # response = llm_client.call(prompt)
            # review = parse_review_response(response)
            pass
        else:
            # 返回待复盘的占位
            review = TradeReview(
                trade_id=trade_id,
                timestamp=datetime.utcnow().isoformat() + "Z",
                chain_of_thought=prompt
            )

        review.trade_id = trade_id
        return review

    def batch_review(
        self,
        outcome_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[TradeReview]:
        """
        批量复盘

        Args:
            outcome_filter: 结果筛选 win/loss
            limit: 数量限制

        Returns:
            复盘结果列表
        """
        if outcome_filter:
            trades = self.trade_logger.get_trades_by_outcome(outcome_filter, limit)
        else:
            trades = self.trade_logger.get_recent_trades(limit)

        reviews = []
        for trade in trades:
            review = self.review_trade(trade.trade_id)
            reviews.append(review)

        return reviews

    def generate_weekly_report(self) -> Dict:
        """
        生成周度复盘报告
        """
        stats = self.trade_logger.get_statistics()
        rules = self.trade_logger.get_experience_rules()

        # 获取本周交易
        # TODO: 实现按周筛选

        return {
            "period": "weekly",
            "statistics": stats,
            "experience_rules": rules,
            "key_findings": self._generate_key_findings(stats),
            "improvement_suggestions": self._generate_improvements(stats)
        }

    def _generate_key_findings(self, stats: Dict) -> List[str]:
        """生成关键发现"""
        findings = []

        if stats["total_trades"] > 0:
            if stats["win_rate"] > 60:
                findings.append(f"胜率{stats['win_rate']}%表现良好")
            elif stats["win_rate"] < 40:
                findings.append(f"胜率{stats['win_rate']}%偏低，需要检查判断逻辑")

            if stats["avg_pnl_pct"] > 0:
                findings.append(f"平均盈亏{stats['avg_pnl_pct']}%为正")
            else:
                findings.append(f"平均盈亏{stats['avg_pnl_pct']}%为负")

        return findings

    def _generate_improvements(self, stats: Dict) -> List[str]:
        """生成改进建议"""
        suggestions = []

        if stats["total_trades"] > 0:
            if stats["win_rate"] < 50:
                suggestions.append("建议减少交易频率，提高入场标准")

            # 按市场类型分析
            for market_stat in stats.get("market_stats", []):
                if market_stat["avg_pnl_pct"] < -2:
                    suggestions.append(
                        f"在{market_stat['market_type']}行情中表现较差，建议回避或调整策略"
                    )

        return suggestions
