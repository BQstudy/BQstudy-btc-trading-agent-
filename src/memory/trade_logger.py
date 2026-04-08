"""
交易日志记录器 - Phase 4 记忆系统核心
记录每笔交易的完整信息，用于后续复盘和经验积累
"""

import json
import sqlite3
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
import uuid


@dataclass
class TradeLog:
    """交易日志数据结构"""
    # 唯一标识
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # 时间信息
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    holding_period_hours: float = 0.0

    # 交易方向
    direction: str = ""  # long/short

    # 价格信息
    entry_price: float = 0.0
    exit_price: float = 0.0

    # 仓位信息
    quantity: float = 0.0
    margin_usdt: float = 0.0
    leverage: int = 1

    # 结果
    pnl_usdt: float = 0.0
    pnl_pct: float = 0.0
    outcome: str = ""  # win/loss/breakeven

    # 归因
    attribution: Dict = field(default_factory=dict)
    experience_rule: str = ""

    # 决策上下文（关联到决策阶段的日志）
    decision_call_id: str = ""
    judgment_call_id: str = ""
    perception_call_id: str = ""

    # 完整思维链（用于向量检索）
    perception_cot: str = ""
    judgment_cot: str = ""
    decision_cot: str = ""

    # 市场背景
    market_type: str = ""
    market_narrative: str = ""
    entry_regime_flags: Dict = field(default_factory=dict)

    # 元数据
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class TradeLogger:
    """
    交易日志记录器
    使用SQLite存储结构化数据，同时保留完整CoT
    """

    def __init__(self, db_path: str = "data/trades.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                entry_time TEXT,
                exit_time TEXT,
                holding_period_hours REAL,
                direction TEXT,
                entry_price REAL,
                exit_price REAL,
                quantity REAL,
                margin_usdt REAL,
                leverage INTEGER,
                pnl_usdt REAL,
                pnl_pct REAL,
                outcome TEXT,
                attribution TEXT,
                experience_rule TEXT,
                decision_call_id TEXT,
                judgment_call_id TEXT,
                perception_call_id TEXT,
                perception_cot TEXT,
                judgment_cot TEXT,
                decision_cot TEXT,
                market_type TEXT,
                market_narrative TEXT,
                entry_regime_flags TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_outcome ON trades(outcome)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_market_type ON trades(market_type)
        """)

        conn.commit()
        conn.close()

    def log_trade_entry(self, trade: TradeLog) -> str:
        """
        记录入场

        Args:
            trade: TradeLog对象

        Returns:
            trade_id
        """
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO trades (
                trade_id, entry_time, direction, entry_price, quantity,
                margin_usdt, leverage, outcome, attribution, experience_rule,
                decision_call_id, judgment_call_id, perception_call_id,
                perception_cot, judgment_cot, decision_cot,
                market_type, market_narrative, entry_regime_flags,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.trade_id,
            trade.entry_time,
            trade.direction,
            trade.entry_price,
            trade.quantity,
            trade.margin_usdt,
            trade.leverage,
            "open",  # 初始状态
            json.dumps(trade.attribution),
            trade.experience_rule,
            trade.decision_call_id,
            trade.judgment_call_id,
            trade.perception_call_id,
            trade.perception_cot,
            trade.judgment_cot,
            trade.decision_cot,
            trade.market_type,
            trade.market_narrative,
            json.dumps(trade.entry_regime_flags),
            trade.created_at,
            trade.updated_at
        ))

        conn.commit()
        conn.close()

        return trade.trade_id

    def log_trade_exit(
        self,
        trade_id: str,
        exit_price: float,
        exit_time: str,
        outcome: str,
        pnl_usdt: float,
        pnl_pct: float,
        attribution: Optional[Dict] = None,
        experience_rule: str = ""
    ):
        """
        记录出场

        Args:
            trade_id: 交易ID
            exit_price: 出场价格
            exit_time: 出场时间
            outcome: 结果 win/loss/breakeven
            pnl_usdt: 盈亏金额
            pnl_pct: 盈亏百分比
            attribution: 归因信息
            experience_rule: 提炼的经验规律
        """
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        cursor = conn.cursor()

        # 计算持仓时间
        cursor.execute("SELECT entry_time FROM trades WHERE trade_id = ?", (trade_id,))
        result = cursor.fetchone()
        if result:
            entry_time = datetime.fromisoformat(result[0].replace('Z', '+00:00'))
            exit_dt = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
            holding_hours = (exit_dt - entry_time).total_seconds() / 3600
        else:
            holding_hours = 0

        cursor.execute("""
            UPDATE trades SET
                exit_time = ?,
                exit_price = ?,
                holding_period_hours = ?,
                outcome = ?,
                pnl_usdt = ?,
                pnl_pct = ?,
                attribution = ?,
                experience_rule = ?,
                updated_at = ?
            WHERE trade_id = ?
        """, (
            exit_time,
            exit_price,
            holding_hours,
            outcome,
            pnl_usdt,
            pnl_pct,
            json.dumps(attribution or {}),
            experience_rule,
            datetime.utcnow().isoformat() + "Z",
            trade_id
        ))

        conn.commit()
        conn.close()

    def get_trade(self, trade_id: str) -> Optional[TradeLog]:
        """获取交易记录"""
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_trade_log(row)
        return None

    def get_recent_trades(self, limit: int = 100) -> List[TradeLog]:
        """获取最近交易记录"""
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM trades
            WHERE outcome != 'open'
            ORDER BY exit_time DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_trade_log(row) for row in rows]

    def get_trades_by_outcome(self, outcome: str, limit: int = 50) -> List[TradeLog]:
        """按结果筛选交易"""
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM trades
            WHERE outcome = ?
            ORDER BY exit_time DESC
            LIMIT ?
        """, (outcome, limit))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_trade_log(row) for row in rows]

    def get_trades_by_market_type(self, market_type: str, limit: int = 50) -> List[TradeLog]:
        """按市场类型筛选交易"""
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM trades
            WHERE market_type = ? AND outcome != 'open'
            ORDER BY exit_time DESC
            LIMIT ?
        """, (market_type, limit))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_trade_log(row) for row in rows]

    def get_statistics(self) -> Dict:
        """获取交易统计"""
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        cursor = conn.cursor()

        # 总交易数
        cursor.execute("SELECT COUNT(*) FROM trades WHERE outcome != 'open'")
        total_trades = cursor.fetchone()[0]

        if total_trades == 0:
            conn.close()
            return {
                "total_trades": 0,
                "win_rate": 0,
                "avg_pnl": 0,
                "avg_pnl_pct": 0
            }

        # 胜率
        cursor.execute("SELECT COUNT(*) FROM trades WHERE outcome = 'win'")
        wins = cursor.fetchone()[0]
        win_rate = wins / total_trades * 100

        # 平均盈亏
        cursor.execute("SELECT AVG(pnl_usdt) FROM trades WHERE outcome != 'open'")
        avg_pnl = cursor.fetchone()[0] or 0

        cursor.execute("SELECT AVG(pnl_pct) FROM trades WHERE outcome != 'open'")
        avg_pnl_pct = cursor.fetchone()[0] or 0

        # 按市场类型统计
        cursor.execute("""
            SELECT market_type, COUNT(*) as count, AVG(pnl_pct) as avg_pnl
            FROM trades
            WHERE outcome != 'open' AND market_type != ''
            GROUP BY market_type
        """)
        market_stats = cursor.fetchall()

        conn.close()

        return {
            "total_trades": total_trades,
            "wins": wins,
            "losses": total_trades - wins,
            "win_rate": round(win_rate, 2),
            "avg_pnl": round(avg_pnl, 2),
            "avg_pnl_pct": round(avg_pnl_pct, 2),
            "market_stats": [
                {"market_type": row[0], "count": row[1], "avg_pnl_pct": round(row[2], 2)}
                for row in market_stats
            ]
        }

    def get_experience_rules(self) -> List[str]:
        """获取所有经验规律"""
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT experience_rule
            FROM trades
            WHERE experience_rule != '' AND experience_rule IS NOT NULL
        """)

        rules = [row[0] for row in cursor.fetchall()]
        conn.close()

        return rules

    def _row_to_trade_log(self, row) -> TradeLog:
        """数据库行转换为TradeLog"""
        return TradeLog(
            trade_id=row["trade_id"],
            entry_time=row["entry_time"],
            exit_time=row["exit_time"],
            holding_period_hours=row["holding_period_hours"],
            direction=row["direction"],
            entry_price=row["entry_price"],
            exit_price=row["exit_price"],
            quantity=row["quantity"],
            margin_usdt=row["margin_usdt"],
            leverage=row["leverage"],
            pnl_usdt=row["pnl_usdt"],
            pnl_pct=row["pnl_pct"],
            outcome=row["outcome"],
            attribution=json.loads(row["attribution"] or "{}"),
            experience_rule=row["experience_rule"] or "",
            decision_call_id=row["decision_call_id"] or "",
            judgment_call_id=row["judgment_call_id"] or "",
            perception_call_id=row["perception_call_id"] or "",
            perception_cot=row["perception_cot"] or "",
            judgment_cot=row["judgment_cot"] or "",
            decision_cot=row["decision_cot"] or "",
            market_type=row["market_type"] or "",
            market_narrative=row["market_narrative"] or "",
            entry_regime_flags=json.loads(row["entry_regime_flags"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
