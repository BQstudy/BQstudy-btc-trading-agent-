"""
多角色辩论引擎 - Phase 2 主观判断引擎核心
实现5角色辩论：Bull/Bear/Neutral/Risk Officer/Judge
参考五大风险消解指南：风险4（辩论共识幻觉）
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DebateResult:
    """辩论结果数据结构"""
    call_id: str
    timestamp: str
    phase: str = "judgment"

    # 多角色辩论原文
    bull_case: Dict = field(default_factory=dict)
    bear_case: Dict = field(default_factory=dict)
    neutral_critique: str = ""
    risk_assessment: str = ""

    # 裁判最终判断
    final_judgment: Dict = field(default_factory=dict)

    # 辩论质量指标
    debate_diversity_score: float = 0.0
    anchor_compliance_score: float = 0.0
    contradiction_detected: bool = False
    contradiction_resolution: str = ""

    # 原始数据
    market_narrative: str = ""
    regime_flags: Dict = field(default_factory=dict)
    perception_output: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "call_id": self.call_id,
            "timestamp": self.timestamp,
            "phase": self.phase,
            "debate_cot": {
                "bull_full_text": self.bull_case.get("reasoning", ""),
                "bear_full_text": self.bear_case.get("reasoning", ""),
                "neutral_full_text": self.neutral_critique,
                "risk_full_text": self.risk_assessment,
                "judge_reasoning": self.final_judgment.get("reasoning", "")
            },
            "judgment_output": {
                "bias": self.final_judgment.get("bias", "neutral"),
                "strength": self.final_judgment.get("strength", "weak"),
                "confidence": self.final_judgment.get("confidence", 0.5),
                "key_levels": self.final_judgment.get("key_levels", {}),
                "invalidation_condition": self.final_judgment.get("key_invalidation", "")
            },
            "debate_metrics": {
                "diversity_score": self.debate_diversity_score,
                "anchor_compliance_score": self.anchor_compliance_score,
                "contradiction_detected": self.contradiction_detected
            }
        }


class DebateValidator:
    """
    辩论质量监控 - 防止共识幻觉
    参考五大风险消解指南风险4
    """

    def __init__(self):
        self.jaccard_threshold = 0.6  # 相似度阈值，超过则触发重试
        self.min_contradiction_words = 5  # 最小矛盾词数

    def calculate_jaccard_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的Jaccard相似度
        用于检测角色是否在重复同质化内容
        """
        # 分词
        words1 = set(re.findall(r'\w+', text1.lower()))
        words2 = set(re.findall(r'\w+', text2.lower()))

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def validate_debate_diversity(
        self,
        bull_text: str,
        bear_text: str,
        neutral_text: str
    ) -> Tuple[bool, Dict]:
        """
        验证辩论多样性
        返回：(是否通过, 详细指标)
        """
        # 计算角色间相似度
        bull_bear_sim = self.calculate_jaccard_similarity(bull_text, bear_text)
        bull_neutral_sim = self.calculate_jaccard_similarity(bull_text, neutral_text)
        bear_neutral_sim = self.calculate_jaccard_similarity(bear_text, neutral_text)

        avg_similarity = (bull_bear_sim + bull_neutral_sim + bear_neutral_sim) / 3
        max_similarity = max(bull_bear_sim, bull_neutral_sim, bear_neutral_sim)

        # 检查是否通过
        passed = max_similarity < self.jaccard_threshold

        return passed, {
            "bull_bear_similarity": round(bull_bear_sim, 3),
            "bull_neutral_similarity": round(bull_neutral_sim, 3),
            "bear_neutral_similarity": round(bear_neutral_sim, 3),
            "avg_similarity": round(avg_similarity, 3),
            "max_similarity": round(max_similarity, 3),
            "passed": passed,
            "threshold": self.jaccard_threshold
        }

    def detect_contradictions(self, bull_text: str, bear_text: str) -> Tuple[bool, List[str]]:
        """
        检测多空观点中的矛盾点
        """
        contradictions = []

        # 提取关键判断词
        bullish_indicators = [
            r"上涨", r"做多", r"多头", r"突破", r"看涨", r"买入",
            r"支撑", r"低多", r"看涨", r"上将", r"做多"
        ]
        bearish_indicators = [
            r"下跌", r"做空", r"空头", r"跌破", r"看跌", r"卖出",
            r"压力", r"高空", r"看跌", r"下探", r"做空"
        ]

        bull_has_bullish = any(re.search(p, bull_text) for p in bullish_indicators)
        bear_has_bearish = any(re.search(p, bear_text) for p in bearish_indicators)

        # 检查是否在同一价格/方向上存在矛盾
        if bull_has_bullish and bear_has_bearish:
            # 检查价格水平
            price_pattern = r'(\d{4,6})'
            bull_prices = re.findall(price_pattern, bull_text)
            bear_prices = re.findall(price_pattern, bear_text)

            # 检查趋势判断
            trend_indicators = [
                (r"突破", r"跌破"),
                (r"上涨", r"下跌"),
                (r"上涨", r"下跌"),
                (r"新高", r"新低"),
                (r"上行", r"下行")
            ]

            for bull_ind, bear_ind in trend_indicators:
                if re.search(bull_ind, bull_text) and re.search(bear_ind, bear_text):
                    contradictions.append(f"{bull_ind} vs {bear_ind}")

        return len(contradictions) > 0, contradictions

    def check_anchor_compliance(
        self,
        debate_text: str,
        regime_flags: Dict
    ) -> Tuple[float, List[str]]:
        """
        检查LLM是否遵循事实锚点
        返回：(合规分数, 未合规项列表)
        """
        violations = []

        # 检查趋势锚点
        if regime_flags.get("is_trending") is not None:
            if regime_flags["is_trending"]:
                trend_direction = regime_flags.get("trend_direction", "")
                if "趋势" in debate_text or "trend" in debate_text.lower():
                    # 检查是否提到了趋势方向
                    if trend_direction == "up" and "上涨" not in debate_text and "上涨" not in debate_text:
                        # 可能没有正确引用趋势
                        pass
            else:
                # 无趋势但提到了趋势延续
                if "趋势延续" in debate_text or "趋势继续" in debate_text:
                    violations.append("trend_invalidated")

        # 检查资金费率锚点
        funding_state = regime_flags.get("funding_state", "neutral")
        if funding_state == "overheated" and "过热" not in debate_text:
            violations.append("funding_not_mentioned")
        elif funding_state == "extreme_negative" and "负费率" not in debate_text:
            violations.append("funding_not_mentioned")

        # 检查OI背离锚点
        oi_state = regime_flags.get("oi_state", "neutral")
        if oi_state == "diverging":
            if "背离" not in debate_text and "背离" not in debate_text.lower():
                violations.append("oi_divergence_not_mentioned")

        score = 1.0 - (len(violations) * 0.25)  # 每项违规扣0.25
        score = max(0.0, score)

        return score, violations


class DebateEngine:
    """
    多角色辩论引擎
    模拟真实交易员脑中多个"声音"博弈的过程
    """

    def __init__(self):
        self.validator = DebateValidator()

        # 角色差异化配置 - 参考五大风险消解指南
        self.role_configs = {
            "bull": {
                "temperature": 0.8,
                "top_p": 0.9,
                "description": "激进多头，寻找所有做多理由"
            },
            "bear": {
                "temperature": 0.9,
                "top_p": 0.9,
                "description": "谨慎空头，强调风险"
            },
            "neutral": {
                "temperature": 0.7,
                "top_p": 0.8,
                "description": "中性观察者，发现逻辑漏洞"
            },
            "risk": {
                "temperature": 0.6,
                "top_p": 0.7,
                "description": "风控官，关注最坏情况"
            },
            "judge": {
                "temperature": 0.5,  # 最低温度，最理性
                "top_p": 0.7,
                "description": "裁判，综合权衡给出判断"
            }
        }

    def generate_user_message(
        self,
        perception_output: Dict,
        regime_flags: Dict,
        market_data: Dict
    ) -> str:
        """
        生成用户消息模板
        """
        # 格式化事实锚点
        flags_text = self._format_regime_flags(regime_flags)

        # 提取感知层输出
        narrative = perception_output.get("market_narrative", "")
        sentiment = perception_output.get("sentiment", "neutral")
        market_type = perception_output.get("market_type", "unknown")

        user_message = f"""
【当前市场背景】
{narrative}

【感知层判断】
- 市场类型：{market_type}
- 情绪倾向：{sentiment}
- 关键支撑：{perception_output.get('key_support', [])}
- 关键压力：{perception_output.get('key_resistance', [])}

【客观事实锚点】（系统计算，不可否定）
{flags_text}

【你的任务】
同时扮演以下5个角色，对当前市场进行辩论分析：

1. 激进多头：假设自己重仓做多，找所有支持上涨的证据
2. 谨慎空头：假设自己重仓做空，找所有支持下跌的证据
3. 中性观察者：指出上面两个角色的逻辑漏洞和过度解读
4. 风控官：只问一个问题——如果判断错了，最坏的情况是什么
5. 最终裁判：综合以上发言，给出最终判断

【重要约束】
- 每个角色的推理必须完整展开
- 裁判必须明确回应Bull和Bear的核心矛盾
- 若事实锚点冲突，必须下调confidence
- 禁止脱离锚点构建纯叙事推演
"""
        return user_message

    def _format_regime_flags(self, flags) -> str:
        """格式化事实锚点 - 支持Dict或RegimeFlags对象"""
        # 处理dataclass对象
        if hasattr(flags, 'is_trending'):
            lines = [
                f"- 趋势有效性：{flags.is_trending} ({flags.trend_direction})",
                f"- 波动率状态：{flags.vol_regime}",
                f"- 资金情绪：{flags.funding_state}",
                f"- 持仓量状态：{flags.oi_state}",
                f"- 流动性：{flags.liquidity_state}"
            ]
        else:
            # 处理Dict
            lines = [
                f"- 趋势有效性：{flags.get('is_trending', False)} ({flags.get('trend_direction', 'none')})",
                f"- 波动率状态：{flags.get('vol_regime', 'normal')}",
                f"- 资金情绪：{flags.get('funding_state', 'neutral')}",
                f"- 持仓量状态：{flags.get('oi_state', 'neutral')}",
                f"- 流动性：{flags.get('liquidity_state', 'unknown')}"
            ]
        return "\n".join(lines)

    def parse_debate_response(self, response_text: str) -> DebateResult:
        """
        解析LLM返回的辩论结果
        尝试从JSON或文本中提取结构化数据
        """
        result = DebateResult(
            call_id="",  # 由上层填充
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        # 尝试解析JSON
        try:
            data = json.loads(response_text)

            # 提取各角色内容
            if "bull_case" in data:
                result.bull_case = data["bull_case"]
            if "bear_case" in data:
                result.bear_case = data["bear_case"]
            if "neutral_critique" in data:
                result.neutral_critique = data["neutral_critique"]
            if "risk_assessment" in data:
                result.risk_assessment = data["risk_assessment"]
            if "final_judgment" in data:
                result.final_judgment = data["final_judgment"]

        except json.JSONDecodeError:
            # JSON解析失败，尝试从文本中提取
            result = self._parse_text_response(response_text)

        return result

    def _parse_text_response(self, text: str) -> DebateResult:
        """从文本中解析辩论结果"""
        result = DebateResult(
            call_id="",
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        # 提取各角色发言
        sections = {
            "bull_case": ["激进多头", "多头", "Bull"],
            "bear_case": ["谨慎空头", "空头", "Bear"],
            "neutral_critique": ["中性", "Neutral"],
            "risk_assessment": ["风控", "Risk"],
            "final_judgment": ["最终裁判", "裁判", "Judge"]
        }

        current_role = None
        content = {}

        for line in text.split("\n"):
            for role, keywords in sections.items():
                if any(kw in line for kw in keywords):
                    if current_role and current_role in content:
                        content[current_role] += line + "\n"
                    current_role = role
                    break

            if current_role:
                content[current_role] = content.get(current_role, "") + line + "\n"

        # 填充结果
        if "bull_case" in content:
            result.bull_case = {"reasoning": content["bull_case"].strip()}
        if "bear_case" in content:
            result.bear_case = {"reasoning": content["bear_case"].strip()}
        if "neutral_critique" in content:
            result.neutral_critique = content["neutral_critique"].strip()
        if "risk_assessment" in content:
            result.risk_assessment = content["risk_assessment"].strip()
        if "final_judgment" in content:
            result.final_judgment = {"reasoning": content["final_judgment"].strip()}

        # 尝试提取结构化字段
        result.final_judgment = self._extract_structured_judgment(text, result.final_judgment)

        return result

    def _extract_structured_judgment(self, text: str, base: Dict) -> Dict:
        """从文本中提取结构化判断"""
        result = base.copy()

        # 提取bias
        if "看涨" in text or "做多" in text or "上涨" in text:
            result["bias"] = "bullish"
        elif "看跌" in text or "做空" in text or "下跌" in text:
            result["bias"] = "bearish"
        else:
            result["bias"] = "neutral"

        # 提取confidence
        confidence_match = re.search(r'confidence[:：]\s*([0-9.]+)', text, re.IGNORECASE)
        if confidence_match:
            result["confidence"] = float(confidence_match.group(1))

        # 提取strength
        if "强" in text:
            result["strength"] = "strong"
        elif "弱" in text:
            result["strength"] = "weak"
        else:
            result["strength"] = "moderate"

        return result

    def validate_and_grade(
        self,
        result: DebateResult,
        regime_flags: Dict
    ) -> DebateResult:
        """
        验证辩论质量并打分
        """
        # 获取各角色文本
        bull_text = result.bull_case.get("reasoning", "")
        bear_text = result.bear_case.get("reasoning", "")
        neutral_text = result.neutral_critique or ""
        risk_text = result.risk_assessment or ""
        judge_text = result.final_judgment.get("reasoning", "")

        # 1. 辩论多样性检查
        diversity_passed, diversity_metrics = self.validator.validate_debate_diversity(
            bull_text, bear_text, neutral_text
        )
        result.debate_diversity_score = 1.0 - diversity_metrics["max_similarity"]

        # 2. 矛盾检测
        has_contradiction, contradictions = self.validator.detect_contradictions(
            bull_text, bear_text
        )
        result.contradiction_detected = has_contradiction

        # 3. 锚点合规检查
        full_debate_text = bull_text + bear_text + judge_text
        anchor_score, violations = self.validator.check_anchor_compliance(
            full_debate_text, regime_flags
        )
        result.anchor_compliance_score = anchor_score

        # 4. 生成矛盾解决说明
        if has_contradiction:
            result.contradiction_resolution = self._generate_contradiction_resolution(
                result.final_judgment, regime_flags
            )

        return result

    def _generate_contradiction_resolution(
        self,
        judgment: Dict,
        regime_flags: Dict
    ) -> str:
        """生成矛盾解决说明"""
        resolution = "裁判已识别多空矛盾，"

        confidence = judgment.get("confidence", 0.5)
        bias = judgment.get("bias", "neutral")

        # 基于锚点状态给出理由
        funding_state = regime_flags.get("funding_state", "neutral")
        oi_state = regime_flags.get("oi_state", "neutral")

        if funding_state == "overheated" and bias == "bullish":
            resolution += "但考虑到资金费率过热，下调置信度。"
        elif oi_state == "diverging" and bias == "bullish":
            resolution += "但考虑到OI背离，趋势存疑。"
        else:
            resolution += f"最终偏向{bias}，置信度{confidence}。"

        return resolution
