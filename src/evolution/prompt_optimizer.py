"""
提示词自动优化器 - Phase 5
基于元分析结果自动优化提示词
"""

import json
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class PromptVersion:
    """提示词版本"""
    version: str
    created_at: str
    author: str  # human/evolved
    content: str
    change_reason: str
    expected_impact: str
    performance_baseline: Optional[Dict] = None


@dataclass
class OptimizationProposal:
    """优化提案"""
    prompt_id: str
    current_version: str
    issues_identified: List[str]
    proposed_changes: List[Dict]
    recommended_change: Dict
    risk_assessment: str
    expected_impact: str


class PromptOptimizer:
    """
    提示词优化器
    基于元分析结果提出优化建议
    """

    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = Path(prompts_dir)
        self.version_history: Dict[str, List[PromptVersion]] = {}

    def generate_proposal(
        self,
        current_prompt: str,
        prompt_id: str,
        meta_analysis_result: Dict,
        performance_data: Dict
    ) -> OptimizationProposal:
        """
        生成优化提案

        Args:
            current_prompt: 当前提示词内容
            prompt_id: 提示词ID
            meta_analysis_result: 元分析结果
            performance_data: 绩效数据

        Returns:
            OptimizationProposal对象
        """
        # 分析问题
        issues = self._identify_issues(meta_analysis_result, performance_data)

        # 生成修改方案
        changes = self._generate_changes(current_prompt, issues)

        # 评估风险
        risk = self._assess_risk(changes)

        # 推荐方案
        recommended = self._select_best_change(changes)

        # 生成提案
        proposal = OptimizationProposal(
            prompt_id=prompt_id,
            current_version=self._get_current_version(prompt_id),
            issues_identified=issues,
            proposed_changes=changes,
            recommended_change=recommended,
            risk_assessment=risk,
            expected_impact=recommended.get("expected_impact", "")
        )

        return proposal

    def apply_optimization(
        self,
        proposal: OptimizationProposal,
        approved: bool = False
    ) -> Optional[PromptVersion]:
        """
        应用优化

        Args:
            proposal: 优化提案
            approved: 是否已批准

        Returns:
            新版本PromptVersion（如果批准）
        """
        if not approved:
            return None

        # 获取当前提示词
        prompt_path = self.prompts_dir / f"{proposal.prompt_id}.yaml"
        if not prompt_path.exists():
            return None

        with open(prompt_path, 'r', encoding='utf-8') as f:
            current = yaml.safe_load(f)

        # 应用修改
        new_content = self._apply_change(
            current,
            proposal.recommended_change
        )

        # 创建新版本
        new_version = PromptVersion(
            version=self._increment_version(proposal.current_version),
            created_at=datetime.utcnow().isoformat() + "Z",
            author="evolved",
            content=new_content,
            change_reason=proposal.recommended_change.get("reason", ""),
            expected_impact=proposal.expected_impact,
            performance_baseline=proposal.recommended_change.get("baseline")
        )

        # 保存历史
        if proposal.prompt_id not in self.version_history:
            self.version_history[prompt_id] = []
        self.version_history[proposal.prompt_id].append(new_version)

        # 保存新版本
        with open(prompt_path, 'w', encoding='utf-8') as f:
            yaml.dump(new_content, f, allow_unicode=True)

        return new_version

    def _identify_issues(
        self,
        meta_result: Dict,
        perf_data: Dict
    ) -> List[str]:
        """识别问题"""
        issues = []

        # 从元分析中提取问题
        suggestions = meta_result.get("prompt_optimization_suggestions", [])

        for suggestion in suggestions:
            issues.append(
                f"[{suggestion.get('target', 'unknown')}] "
                f"{suggestion.get('issue', '')}: {suggestion.get('suggestion', '')}"
            )

        # 检查绩效数据
        if perf_data.get("win_rate", 0) < 40:
            issues.append("胜率低于40%，需要检查判断标准")

        if perf_data.get("avg_pnl_pct", 0) < 0:
            issues.append("平均盈亏为负，需要优化入场或出场逻辑")

        return issues

    def _generate_changes(
        self,
        current_prompt: str,
        issues: List[str]
    ) -> List[Dict]:
        """生成修改方案"""
        changes = []

        # 针对每个问题生成方案
        for issue in issues:
            if "过度做多" in issue:
                changes.append({
                    "type": "add_constraint",
                    "location": "judgment_layer",
                    "content": "【强制约束】在给出做多结论前，必须先列举至少2个做空理由并反驳它们",
                    "reason": "解决过度做多倾向",
                    "expected_impact": "提高空头判断质量"
                })

            if "过度做空" in issue:
                changes.append({
                    "type": "add_constraint",
                    "location": "judgment_layer",
                    "content": "【强制约束】在给出做空结论前，必须先列举至少2个做多理由并反驳它们",
                    "reason": "解决过度做空倾向",
                    "expected_impact": "提高多头判断质量"
                })

            if "入场过早" in issue:
                changes.append({
                    "type": "add_step",
                    "location": "decision_layer",
                    "content": "【入场确认】必须等待至少2个确认信号才可入场",
                    "reason": "解决入场过早问题",
                    "expected_impact": "减少假突破被套"
                })

            if "震荡" in issue and "表现差" in issue:
                changes.append({
                    "type": "add_condition",
                    "location": "perception_layer",
                    "content": "【震荡市识别】当识别为震荡市时，默认输出 no_trade",
                    "reason": "提高震荡市表现",
                    "expected_impact": "减少震荡市亏损"
                })

        # 默认保守优化
        if not changes:
            changes.append({
                "type": "minor_refine",
                "location": "general",
                "content": "优化置信度校准逻辑",
                "reason": "保守优化",
                "expected_impact": "提高判断准确性"
            })

        return changes

    def _assess_risk(self, changes: List[Dict]) -> str:
        """评估修改风险"""
        high_risk_count = 0
        medium_risk_count = 0

        for change in changes:
            change_type = change.get("type", "")

            if change_type in ["add_constraint", "add_condition"]:
                high_risk_count += 1
            elif change_type == "add_step":
                medium_risk_count += 1

        if high_risk_count > 2:
            return "HIGH - 大量约束修改可能导致过度保守"
        elif medium_risk_count > 0:
            return "MEDIUM - 中等修改，建议小范围测试"
        else:
            return "LOW - 小范围修改，风险可控"

    def _select_best_change(self, changes: List[Dict]) -> Dict:
        """选择最佳修改"""
        if not changes:
            return {}

        # 按风险排序，选择风险最低的
        changes_with_risk = []
        for change in changes:
            change_type = change.get("type", "")
            if change_type == "minor_refine":
                risk_score = 1
            elif change_type == "add_step":
                risk_score = 2
            else:
                risk_score = 3
            changes_with_risk.append((risk_score, change))

        changes_with_risk.sort(key=lambda x: x[0])
        return changes_with_risk[0][1]

    def _apply_change(
        self,
        current: Dict,
        change: Dict
    ) -> Dict:
        """应用修改到提示词"""
        # 简化实现
        # 实际需要根据change的位置插入内容
        return current

    def _get_current_version(self, prompt_id: str) -> str:
        """获取当前版本号"""
        history = self.version_history.get(prompt_id, [])
        if history:
            return history[-1].version
        return "v1.0"

    def _increment_version(self, current: str) -> str:
        """递增版本号"""
        if current.startswith("v"):
            try:
                num = int(current[1:]) + 1
                return f"v{num}"
            except:
                pass
        return "v2.0"


def generate_optimization_prompt(
    current_prompt: str,
    prompt_id: str,
    performance_data: Dict,
    identified_issues: List[str]
) -> str:
    """
    生成提示词优化的LLM提示

    Args:
        current_prompt: 当前提示词
        prompt_id: 提示词ID
        performance_data: 绩效数据
        identified_issues: 识别的问题

    Returns:
        优化LLM的提示
    """
    prompt = f"""
你是一位专业的提示词工程师，同时深度理解BTC交易。
你的任务是基于过去的表现数据，优化某个具体提示词。

当前提示词ID: {prompt_id}

当前提示词：
```
{current_prompt}
```

该提示词在过去的表现数据：
{json.dumps(performance_data, indent=2)}

主要问题（来自元分析）：
{chr(10).join(f"- {issue}" for issue in identified_issues)}

优化任务：
1. 首先分析当前提示词的哪些部分导致了上述问题
2. 提出2-3个不同方向的修改方案，每个方案说明：
   - 核心修改内容
   - 预期解决哪个问题
   - 可能带来的新风险
3. 给出推荐的修改方案
4. 输出修改后的完整提示词

注意：提示词优化要保守，每次只修改一个核心问题，避免全盘推翻。
修改前后必须能够追踪效果对比。

输出格式：
{{
    "analysis": "问题分析",
    "proposals": [
        {{
            "description": "方案描述",
            "content": "修改内容",
            "risk": "风险评估"
        }}
    ],
    "recommended": {{
        "description": "推荐方案",
        "content": "修改后的完整提示词"
    }}
}}
"""
    return prompt
