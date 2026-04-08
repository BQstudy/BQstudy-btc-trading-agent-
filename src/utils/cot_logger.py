"""
思维链日志记录器 - 贯穿所有阶段使用
记录每次LLM调用的完整推理过程，用于后续知识蒸馏
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class CoTLogger:
    """思维链日志记录器"""

    def __init__(self, base_log_dir: str = "logs"):
        self.base_log_dir = Path(base_log_dir)
        self.base_log_dir.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        phase: str,
        chain_of_thought: str,
        decision: dict,
        market_context: Optional[dict] = None,
        prompt: Optional[str] = None,
        execution_result: Optional[dict] = None,
        trade_outcome: Optional[dict] = None
    ) -> str:
        """
        记录一次完整的思维链日志

        Args:
            phase: 阶段名称 (perception/judgment/decision/review)
            chain_of_thought: LLM完整推理原文
            decision: 结构化决策输出
            market_context: 行情快照
            prompt: 完整系统提示词+用户消息
            execution_result: 执行结果
            trade_outcome: 交易结束后回填

        Returns:
            call_id: 本次调用的唯一标识
        """
        call_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"

        log_entry = {
            "call_id": call_id,
            "timestamp": timestamp,
            "phase": phase,
            "market_context": market_context,
            "prompt": prompt,
            "chain_of_thought": chain_of_thought,
            "decision": decision,
            "execution_result": execution_result,
            "trade_outcome": trade_outcome
        }

        # 移除None值
        log_entry = {k: v for k, v in log_entry.items() if v is not None}

        self._save_log(phase, log_entry)
        return call_id

    def _save_log(self, phase: str, entry: dict):
        """保存日志到对应阶段的日志目录"""
        log_dir = self.base_log_dir / f"cot_{phase}"
        log_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = log_dir / f"{date_str}.jsonl"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def update_trade_outcome(self, call_id: str, phase: str, outcome: dict):
        """
        交易结束后回填结果

        Args:
            call_id: 原始调用的ID
            phase: 阶段名称
            outcome: 交易结果数据
        """
        log_dir = self.base_log_dir / f"cot_{phase}"
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = log_dir / f"{date_str}.jsonl"

        if not log_file.exists():
            return

        # 读取所有日志
        logs = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                logs.append(json.loads(line.strip()))

        # 找到对应call_id并更新
        updated = False
        for log in logs:
            if log.get("call_id") == call_id:
                log["trade_outcome"] = outcome
                updated = True
                break

        if updated:
            # 写回文件
            with open(log_file, "w", encoding="utf-8") as f:
                for log in logs:
                    f.write(json.dumps(log, ensure_ascii=False) + "\n")


class LLMClient:
    """统一LLM调用接口（简化版，后续可扩展）"""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        self.logger = CoTLogger()

    def call_with_cot_logging(
        self,
        phase: str,
        system_prompt: str,
        user_message: str,
        market_context: Optional[dict] = None,
        enable_thinking: bool = True
    ) -> tuple[str, str, str]:
        """
        调用LLM并记录思维链

        Returns:
            (call_id, thinking_text, response_text)
        """
        call_id = str(uuid.uuid4())

        # 这里实际调用Anthropic API
        # 简化版本，实际使用时需要接入anthropic库
        # response = anthropic.Anthropic().messages.create(...)

        # 返回结构供上层填充
        return call_id, "", ""
