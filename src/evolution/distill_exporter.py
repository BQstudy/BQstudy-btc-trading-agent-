"""
蒸馏数据导出器 - Phase 5
将积累的完整思维链日志导出为蒸馏训练数据集
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class DistillationEntry:
    """蒸馏数据条目"""
    prompt: str  # 感知层输入 + 系统提示词
    completion: str  # 完整CoT推理 + 最终决策

    # 元数据
    metadata: Dict

    # 质量标签
    quality_score: float  # 0-1
    human_quality_label: Optional[str]  # excellent/good/poor


class DistillExporter:
    """
    蒸馏数据导出器
    将CoT日志转换为蒸馏训练格式
    """

    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.output_dir = Path("data/distillation")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_dataset(
        self,
        min_confidence: float = 0.6,
        min_quality_score: float = 0.6,
        balance_classes: bool = True,
        output_file: str = "distillation_dataset.jsonl"
    ) -> str:
        """
        导出蒸馏数据集

        Args:
            min_confidence: 最小置信度过滤
            min_quality_score: 最小质量分数
            balance_classes: 是否平衡正负样本
            output_file: 输出文件名

        Returns:
            输出文件路径
        """
        # 收集所有日志
        all_entries = []

        # 从各阶段收集
        for phase in ["perception", "judgment", "decision", "review"]:
            phase_entries = self._load_phase_logs(phase)
            filtered = self._filter_entries(
                phase_entries,
                min_confidence,
                min_quality_score
            )
            all_entries.extend(filtered)

        # 平衡正负样本
        if balance_classes:
            all_entries = self._balance_dataset(all_entries)

        # 导出
        output_path = self.output_dir / output_file

        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in all_entries:
                f.write(json.dumps({
                    "prompt": entry.prompt,
                    "completion": entry.completion,
                    "metadata": entry.metadata
                }, ensure_ascii=False) + "\n")

        # 生成统计
        self._generate_statistics(all_entries, output_path)

        return str(output_path)

    def _load_phase_logs(self, phase: str) -> List[Dict]:
        """加载某阶段的日志"""
        phase_dir = self.logs_dir / f"cot_{phase}"

        if not phase_dir.exists():
            return []

        entries = []

        for log_file in phase_dir.glob("*.jsonl"):
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue

        return entries

    def _filter_entries(
        self,
        entries: List[Dict],
        min_confidence: float,
        min_quality_score: float
    ) -> List[DistillationEntry]:
        """过滤条目"""
        filtered = []

        for entry in entries:
            # 检查置信度
            decision = entry.get("decision", {})
            confidence = decision.get("confidence", 0)

            if confidence < min_confidence:
                continue

            # 检查质量
            quality_score = self._calculate_quality_score(entry)
            if quality_score < min_quality_score:
                continue

            # 转换为蒸馏条目
            distill_entry = self._convert_to_distill_entry(entry, quality_score)
            if distill_entry:
                filtered.append(distill_entry)

        return filtered

    def _calculate_quality_score(self, entry: Dict) -> float:
        """计算质量分数"""
        score = 0.0
        checks = []

        # 1. 步骤完整性
        cot = entry.get("chain_of_thought", "")
        checks.append("失效条件" in cot or "invalidation" in cot.lower())
        checks.append("风险收益" in cot or "risk_reward" in cot.lower())
        checks.append("入场" in cot)

        # 2. 数值有效性
        decision = entry.get("decision", {})
        if decision.get("stop_loss") and decision.get("entry_zone"):
            checks.append(True)
        else:
            checks.append(False)

        # 3. 逻辑一致性
        checks.append("可能涨也可能跌" not in cot)
        checks.append("事后看" not in cot)

        # 计算分数
        score = sum(checks) / len(checks) if checks else 0

        return score

    def _convert_to_distill_entry(
        self,
        entry: Dict,
        quality_score: float
    ) -> Optional[DistillationEntry]:
        """转换为蒸馏条目"""
        phase = entry.get("phase", "")
        prompt = entry.get("prompt", "")
        cot = entry.get("chain_of_thought", "")
        decision = entry.get("decision", {})

        # 构建completion
        completion = f"{cot}\n\n最终决策: {json.dumps(decision, ensure_ascii=False)}"

        # 元数据
        metadata = {
            "phase": phase,
            "market_type": entry.get("market_context", {}).get("market_type", ""),
            "trade_outcome": entry.get("trade_outcome", ""),
            "pnl_pct": entry.get("trade_outcome", {}).get("pnl_pct", 0) if isinstance(entry.get("trade_outcome"), dict) else 0,
            "confidence": decision.get("confidence", 0),
            "quality_score": quality_score
        }

        return DistillationEntry(
            prompt=prompt,
            completion=completion,
            metadata=metadata,
            quality_score=quality_score,
            human_quality_label=None
        )

    def _balance_dataset(self, entries: List[DistillationEntry]) -> List[DistillationEntry]:
        """平衡正负样本"""
        # 分类
        wins = [e for e in entries if e.metadata.get("trade_outcome") == "win"]
        losses = [e for e in entries if e.metadata.get("trade_outcome") == "loss"]
        others = [e for e in entries if e.metadata.get("trade_outcome") not in ["win", "loss"]]

        # 平衡
        min_count = min(len(wins), len(losses))

        balanced = wins[:min_count] + losses[:min_count] + others

        return balanced

    def _generate_statistics(
        self,
        entries: List[DistillationEntry],
        output_path: Path
    ):
        """生成统计信息"""
        stats = {
            "total_entries": len(entries),
            "by_phase": {},
            "by_outcome": {},
            "avg_quality_score": 0,
            "avg_confidence": 0
        }

        quality_scores = []
        confidences = []

        for entry in entries:
            phase = entry.metadata.get("phase", "unknown")
            outcome = entry.metadata.get("trade_outcome", "unknown")

            stats["by_phase"][phase] = stats["by_phase"].get(phase, 0) + 1
            stats["by_outcome"][outcome] = stats["by_outcome"].get(outcome, 0) + 1

            quality_scores.append(entry.quality_score)
            confidences.append(entry.metadata.get("confidence", 0))

        if quality_scores:
            stats["avg_quality_score"] = sum(quality_scores) / len(quality_scores)
        if confidences:
            stats["avg_confidence"] = sum(confidences) / len(confidences)

        # 保存统计
        stats_path = output_path.with_suffix('.stats.json')
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        return stats

    def add_human_label(
        self,
        entry_id: str,
        label: str  # excellent/good/poor
    ):
        """
        添加人工质量标签

        Args:
            entry_id: 条目ID
            label: 质量标签
        """
        # 实现人工标注接口
        pass

    def export_for_human_review(
        self,
        sample_size: int = 100,
        output_file: str = "for_human_review.jsonl"
    ) -> str:
        """
        导出高质量CoT供人工审核

        Args:
            sample_size: 样本数量
            output_file: 输出文件名

        Returns:
            输出文件路径
        """
        # 收集高质量条目
        all_entries = []

        for phase in ["perception", "judgment", "decision"]:
            phase_entries = self._load_phase_logs(phase)
            for entry in phase_entries:
                score = self._calculate_quality_score(entry)
                if score >= 0.8:  # 高质量
                    distill_entry = self._convert_to_distill_entry(entry, score)
                    if distill_entry:
                        all_entries.append(distill_entry)

        # 随机采样
        import random
        random.shuffle(all_entries)
        samples = all_entries[:sample_size]

        # 导出
        output_path = self.output_dir / output_file

        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in samples:
                f.write(json.dumps({
                    "id": hash(entry.prompt) % 1000000,  # 简单ID
                    "prompt": entry.prompt,
                    "completion": entry.completion,
                    "metadata": entry.metadata,
                    "human_label": None  # 待标注
                }, ensure_ascii=False) + "\n")

        return str(output_path)


class CoTValidator:
    """
    CoT质量校验器
    参考五大风险消解指南：风险5（长CoT低质量）
    """

    def __init__(self):
        self.min_steps = 3  # 最少推理步骤
        self.max_repetition = 0.3  # 最大重复比例

    def validate(self, cot: str, decision: Dict) -> Dict:
        """
        验证CoT质量

        Returns:
            验证结果
        """
        checks = {
            # 1. 步骤完整性
            "has_invalidation": "失效条件" in cot or "invalidation" in cot.lower(),
            "has_risk_reward": "风险收益" in cot or "risk_reward" in cot.lower(),
            "has_entry_logic": "入场" in cot and ("支撑" in cot or "压力" in cot),

            # 2. 数值有效性
            "stop_beyond_entry": self._check_stop_validity(decision),
            "rr_ratio_valid": decision.get("risk_reward_ratio", 0) >= 2.0,

            # 3. 逻辑一致性
            "no_hedging": not any(word in cot for word in ["也许", "可能涨也可能跌", "不好说"]),
            "no_hindsight": "果然" not in cot and "正如预期" not in cot,

            # 4. 置信度校准
            "confidence_action_aligned": (
                decision.get("confidence", 0) < 0.4 and decision.get("action") == "no_trade"
            ) or decision.get("confidence", 0) >= 0.4
        }

        # 计算质量分数
        score = sum(checks.values()) / len(checks)

        return {
            "passed": score >= 0.75,
            "details": checks,
            "quality_score": round(score, 2),
            "failed_reasons": [k for k, v in checks.items() if not v]
        }

    def _check_stop_validity(self, decision: Dict) -> bool:
        """检查止损有效性"""
        action = decision.get("action", "")
        stop = decision.get("stop_loss", 0)
        entry_zone = decision.get("entry_zone", [])

        if not entry_zone or not stop:
            return False

        if action == "long":
            return stop < min(entry_zone)
        elif action == "short":
            return stop > max(entry_zone)

        return True
