"""
风控管理器 - Phase 3 硬规则层
6条硬风控规则，代码层强制执行，LLM输出仅为"建议"
"""

import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskCheckResult:
    """风控检查结果"""
    passed: bool
    risk_level: RiskLevel
    violations: List[str]
    warnings: List[str]
    action: str  # allow/reject/pause
    details: Dict = field(default_factory=dict)


@dataclass
class AccountState:
    """账户状态"""
    account_id: str
    balance_usdt: float
    equity_usdt: float
    margin_used: float
    margin_ratio: float
    daily_pnl: float
    daily_pnl_pct: float
    total_pnl: float
    consecutive_losses: int
    max_drawdown_pct: float
    last_trade_time: Optional[datetime] = None


class RiskManager:
    """
    风控管理器
    硬规则不可覆盖，Phase 3的6条风控规则
    """

    def __init__(self, config_path: Optional[str] = None):
        # 默认风控参数
        self.rules = {
            "max_loss_per_trade_pct": 2.0,      # 单笔最大亏损 2%
            "max_loss_per_day_pct": 5.0,        # 单日最大亏损 5%
            "max_leverage": 10,                  # 最大杠杆 10x
            "max_position_per_direction_pct": 30,  # 单一方向最大仓位 30%
            "max_consecutive_losses": 3,         # 连续亏损次数 3次
            "max_drawdown_pct": 15.0             # 最大回撤 15%
        }

        # 加载配置文件
        if config_path:
            self._load_config(config_path)

        # 交易历史
        self.trade_history: List[Dict] = []
        self.daily_stats: Dict = {}

    def _load_config(self, config_path: str):
        """加载风控配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.rules.update(config.get("risk_rules", {}))
        except Exception as e:
            print(f"Warning: Could not load risk config: {e}")

    def check_all(
        self,
        decision: Dict,
        account_state: AccountState,
        market_context: Optional[Dict] = None
    ) -> RiskCheckResult:
        """
        执行全部风控检查
        """
        violations = []
        warnings = []
        details = {}

        # 1. 单笔亏损检查
        passed, msg = self._check_single_trade_loss(decision, account_state)
        details["single_trade_loss"] = {"passed": passed, "message": msg}
        if not passed:
            violations.append(msg)

        # 2. 单日亏损检查
        passed, msg = self._check_daily_loss(account_state)
        details["daily_loss"] = {"passed": passed, "message": msg}
        if not passed:
            violations.append(msg)

        # 3. 杠杆检查
        passed, msg = self._check_leverage(decision)
        details["leverage"] = {"passed": passed, "message": msg}
        if not passed:
            violations.append(msg)

        # 4. 仓位限制检查
        passed, msg = self._check_position_limit(decision, account_state)
        details["position_limit"] = {"passed": passed, "message": msg}
        if not passed:
            violations.append(msg)

        # 5. 连续亏损检查
        passed, msg, action = self._check_consecutive_losses(account_state)
        details["consecutive_losses"] = {"passed": passed, "message": msg, "action": action}
        if not passed:
            violations.append(msg)

        # 6. 最大回撤检查
        passed, msg = self._check_max_drawdown(account_state)
        details["max_drawdown"] = {"passed": passed, "message": msg}
        if not passed:
            violations.append(msg)

        # 确定风险等级
        risk_level = self._determine_risk_level(len(violations), account_state)

        # 确定行动
        if len(violations) > 0:
            action = "reject"
        elif account_state.consecutive_losses >= 2:
            action = "pause"
        else:
            action = "allow"

        return RiskCheckResult(
            passed=len(violations) == 0,
            risk_level=risk_level,
            violations=violations,
            warnings=warnings,
            action=action,
            details=details
        )

    def _check_single_trade_loss(
        self,
        decision: Dict,
        account_state: AccountState
    ) -> Tuple[bool, str]:
        """
        规则1: 单笔最大亏损 账户净值 2%
        """
        risk_amount = decision.get("risk_amount_usdt", 0)
        max_loss = account_state.equity_usdt * self.rules["max_loss_per_trade_pct"] / 100

        if risk_amount > max_loss * 1.05:  # 5%容差
            return False, f"单笔风险金额{risk_amount:.2f}USDT超过限制{max_loss:.2f}USDT ({self.rules['max_loss_per_trade_pct']}%净值)"

        return True, "Passed"

    def _check_daily_loss(self, account_state: AccountState) -> Tuple[bool, str]:
        """
        规则2: 单日最大亏损 账户净值 5%
        """
        daily_loss_limit = account_state.equity_usdt * self.rules["max_loss_per_day_pct"] / 100

        if abs(account_state.daily_pnl) > daily_loss_limit and account_state.daily_pnl < 0:
            return False, f"当日亏损已达{abs(account_state.daily_pnl):.2f}USDT，超过限制{daily_loss_limit:.2f}USDT"

        return True, "Passed"

    def _check_leverage(self, decision: Dict) -> Tuple[bool, str]:
        """
        规则3: 最大杠杆倍数 10x
        """
        leverage = decision.get("leverage", 1)

        if leverage > self.rules["max_leverage"]:
            return False, f"杠杆{leverage}x超过最大限制{self.rules['max_leverage']}x"

        return True, "Passed"

    def _check_position_limit(
        self,
        decision: Dict,
        account_state: AccountState
    ) -> Tuple[bool, str]:
        """
        规则4: 单一方向最大仓位 账户净值 30%
        """
        position_size = decision.get("margin_usdt", 0)
        max_position = account_state.equity_usdt * self.rules["max_position_per_direction_pct"] / 100

        # 检查当前已用保证金
        current_margin = account_state.margin_used
        new_total = current_margin + position_size

        if new_total > max_position:
            return False, f"仓位占用{new_total:.2f}USDT将超过限制{max_position:.2f}USDT ({self.rules['max_position_per_direction_pct']}%净值)"

        return True, "Passed"

    def _check_consecutive_losses(
        self,
        account_state: AccountState
    ) -> Tuple[bool, str, str]:
        """
        规则5: 连续亏损次数 3次
        触发动作: 降低仓位50%，等待复盘
        """
        if account_state.consecutive_losses >= self.rules["max_consecutive_losses"]:
            return (
                False,
                f"连续亏损{account_state.consecutive_losses}次，触发风控暂停",
                "pause_and_review"
            )

        if account_state.consecutive_losses >= 2:
            return (
                True,
                f"连续亏损{account_state.consecutive_losses}次，建议降低仓位",
                "reduce_position"
            )

        return True, "Passed", "allow"

    def _check_max_drawdown(self, account_state: AccountState) -> Tuple[bool, str]:
        """
        规则6: 最大回撤 账户净值 15%
        触发动作: 停止交易，人工介入
        """
        if account_state.max_drawdown_pct >= self.rules["max_drawdown_pct"]:
            return (
                False,
                f"最大回撤{account_state.max_drawdown_pct:.2f}%超过限制{self.rules['max_drawdown_pct']}%，停止交易等待人工介入"
            )

        if account_state.max_drawdown_pct >= self.rules["max_drawdown_pct"] * 0.8:
            return (
                True,
                f"警告：回撤已达{account_state.max_drawdown_pct:.2f}%，接近{self.rules['max_drawdown_pct']}%限制"
            )

        return True, "Passed"

    def _determine_risk_level(
        self,
        violation_count: int,
        account_state: AccountState
    ) -> RiskLevel:
        """确定风险等级"""
        if violation_count >= 2:
            return RiskLevel.CRITICAL
        elif violation_count == 1:
            return RiskLevel.HIGH
        elif account_state.consecutive_losses >= 2:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def record_trade(self, trade: Dict):
        """记录交易用于统计"""
        self.trade_history.append({
            **trade,
            "timestamp": datetime.utcnow().isoformat()
        })

        # 更新连续亏损计数
        if trade.get("pnl", 0) < 0:
            # 这里简化处理，实际应该基于账户状态
            pass

    def get_risk_summary(self, account_state: AccountState) -> Dict:
        """获取风险摘要"""
        return {
            "rules": self.rules,
            "current_state": {
                "daily_pnl_pct": account_state.daily_pnl_pct,
                "consecutive_losses": account_state.consecutive_losses,
                "max_drawdown_pct": account_state.max_drawdown_pct,
                "margin_ratio": account_state.margin_ratio
            },
            "risk_level": self._determine_risk_level(0, account_state).value,
            "available_risk": self.rules["max_loss_per_trade_pct"],  # 剩余可用风险额度
            "available_position_pct": self.rules["max_position_per_direction_pct"]  # 剩余可用仓位
        }

    def assert_hard_rules(self, decision: Dict, account_state: AccountState):
        """
        硬规则断言 - 使用异常机制确保不可覆盖
        """
        # 单笔亏损
        risk_amount = decision.get("risk_amount_usdt", 0)
        max_loss = account_state.equity_usdt * self.rules["max_loss_per_trade_pct"] / 100
        assert risk_amount <= max_loss * 1.05, f"单笔亏损超限: {risk_amount} > {max_loss}"

        # 杠杆
        leverage = decision.get("leverage", 1)
        assert leverage <= self.rules["max_leverage"], f"杠杆超限: {leverage} > {self.rules['max_leverage']}"

        # 单日亏损
        daily_loss_limit = account_state.equity_usdt * self.rules["max_loss_per_day_pct"] / 100
        assert abs(account_state.daily_pnl) <= daily_loss_limit, f"单日亏损超限"

        # 最大回撤
        assert account_state.max_drawdown_pct < self.rules["max_drawdown_pct"], f"回撤超限"
