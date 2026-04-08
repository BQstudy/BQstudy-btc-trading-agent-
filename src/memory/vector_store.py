"""
向量存储与检索 - Phase 4 记忆系统
使用Chroma DB存储交易经验，支持语义相似度检索
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json

# 尝试导入chromadb，如果不可用则使用简单实现
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


@dataclass
class ExperienceEntry:
    """经验条目数据结构"""
    id: str
    date: str

    # 市场背景
    market_type: str  # trend_up/trend_down/range/breakout
    btc_price_range: List[float]  # [low, high]
    market_narrative: str

    # 交易信息
    trade_action: str  # long/short/no_trade
    entry_price: float
    exit_price: float
    pnl_pct: float
    outcome: str  # win/loss/breakeven

    # 归因
    attribution: Dict

    # 经验
    experience_rule: str

    # 向量ID
    embedding_id: str = ""

    # 完整CoT日志ID
    full_cot_log_id: str = ""


class VectorStore:
    """
    向量经验存储
    支持语义相似度检索
    """

    def __init__(self, persist_directory: str = "data/chroma_db"):
        self.persist_directory = persist_directory

        if CHROMADB_AVAILABLE:
            try:
                self.client = chromadb.PersistentClient(path=persist_directory)
                self.collection = self.client.get_or_create_collection(
                    name="trading_experience",
                    metadata={"description": "Trading experience embeddings"}
                )
            except Exception as e:
                print(f"Warning: Failed to initialize ChromaDB: {e}")
                self.client = None
                self.collection = None
        else:
            self.client = None
            self.collection = None

        # 备用：简单内存存储
        self.simple_store: Dict[str, Dict] = {}

    def add_experience(
        self,
        entry: ExperienceEntry,
        embedding: Optional[List[float]] = None
    ) -> str:
        """
        添加经验条目

        Args:
            entry: 经验条目
            embedding: 向量嵌入（可选）

        Returns:
            条目ID
        """
        if self.collection and embedding:
            try:
                self.collection.add(
                    ids=[entry.id],
                    embeddings=[embedding],
                    metadatas=[{
                        "date": entry.date,
                        "market_type": entry.market_type,
                        "trade_action": entry.trade_action,
                        "outcome": entry.outcome,
                        "pnl_pct": entry.pnl_pct,
                        "experience_rule": entry.experience_rule,
                        "market_narrative": entry.market_narrative[:500]  # 截断
                    }]
                )
                return entry.id
            except Exception as e:
                print(f"Warning: Failed to add to ChromaDB: {e}")

        # 备用：存入简单存储
        self.simple_store[entry.id] = {
            "entry": entry,
            "embedding": embedding
        }
        return entry.id

    def search_similar(
        self,
        query_embedding: List[float],
        n_results: int = 3,
        filters: Optional[Dict] = None
    ) -> List[ExperienceEntry]:
        """
        检索相似经验

        Args:
            query_embedding: 查询向量
            n_results: 返回数量
            filters: 筛选条件

        Returns:
            相似经验列表
        """
        if self.collection:
            try:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=filters
                )

                entries = []
                if results and results["ids"]:
                    for i, id in enumerate(results["ids"][0]):
                        meta = results["metadatas"][0][i]
                        entries.append(ExperienceEntry(
                            id=id,
                            date=meta.get("date", ""),
                            market_type=meta.get("market_type", ""),
                            btc_price_range=[],
                            market_narrative=meta.get("market_narrative", ""),
                            trade_action=meta.get("trade_action", ""),
                            entry_price=0,
                            exit_price=0,
                            pnl_pct=meta.get("pnl_pct", 0),
                            outcome=meta.get("outcome", ""),
                            attribution={},
                            experience_rule=meta.get("experience_rule", "")
                        ))

                return entries
            except Exception as e:
                print(f"Warning: Search failed: {e}")

        # 备用：简单检索
        return self._simple_search(query_embedding, n_results)

    def search_by_market_type(
        self,
        market_type: str,
        limit: int = 5
    ) -> List[ExperienceEntry]:
        """
        按市场类型检索

        Args:
            market_type: 市场类型
            limit: 数量限制

        Returns:
            经验列表
        """
        if self.collection:
            try:
                results = self.collection.get(
                    where={"market_type": market_type},
                    limit=limit
                )

                entries = []
                if results and results["ids"]:
                    for i, id in enumerate(results["ids"]):
                        meta = results["metadatas"][i]
                        entries.append(ExperienceEntry(
                            id=id,
                            date=meta.get("date", ""),
                            market_type=meta.get("market_type", ""),
                            btc_price_range=[],
                            market_narrative=meta.get("market_narrative", ""),
                            trade_action=meta.get("trade_action", ""),
                            entry_price=0,
                            exit_price=0,
                            pnl_pct=meta.get("pnl_pct", 0),
                            outcome=meta.get("outcome", ""),
                            attribution={},
                            experience_rule=meta.get("experience_rule", "")
                        ))

                return entries
            except Exception as e:
                print(f"Warning: Search by market type failed: {e}")

        # 备用
        return self._filter_by_market_type(market_type, limit)

    def search_by_outcome(
        self,
        outcome: str,
        limit: int = 10
    ) -> List[ExperienceEntry]:
        """
        按结果检索（用于分析盈利/亏损案例）

        Args:
            outcome: win/loss
            limit: 数量限制

        Returns:
            经验列表
        """
        if self.collection:
            try:
                results = self.collection.get(
                    where={"outcome": outcome},
                    limit=limit
                )

                entries = []
                if results and results["ids"]:
                    for i, id in enumerate(results["ids"]):
                        meta = results["metadatas"][i]
                        entries.append(ExperienceEntry(
                            id=id,
                            date=meta.get("date", ""),
                            market_type=meta.get("market_type", ""),
                            btc_price_range=[],
                            market_narrative=meta.get("market_narrative", ""),
                            trade_action=meta.get("trade_action", ""),
                            entry_price=0,
                            exit_price=0,
                            pnl_pct=meta.get("pnl_pct", 0),
                            outcome=meta.get("outcome", ""),
                            attribution={},
                            experience_rule=meta.get("experience_rule", "")
                        ))

                return entries
            except Exception as e:
                print(f"Warning: Search by outcome failed: {e}")

        return []

    def get_experience_summary(self) -> Dict:
        """获取经验库摘要"""
        if self.collection:
            try:
                count = self.collection.count()

                # 按市场类型统计
                market_types = {}
                outcomes = {"win": 0, "loss": 0, "breakeven": 0}

                # 获取所有数据
                results = self.collection.get()

                if results and results["metadatas"]:
                    for meta in results["metadatas"]:
                        mt = meta.get("market_type", "unknown")
                        market_types[mt] = market_types.get(mt, 0) + 1

                        outcome = meta.get("outcome", "")
                        if outcome in outcomes:
                            outcomes[outcome] += 1

                return {
                    "total_experiences": count,
                    "by_market_type": market_types,
                    "by_outcome": outcomes
                }
            except Exception as e:
                print(f"Warning: Failed to get summary: {e}")

        return {
            "total_experiences": len(self.simple_store),
            "by_market_type": {},
            "by_outcome": {}
        }

    def _simple_search(
        self,
        query_embedding: List[float],
        n_results: int
    ) -> List[ExperienceEntry]:
        """简单检索（无向量时使用）"""
        # 返回最近的记录
        entries = []
        for id, data in list(self.simple_store.items())[-10:]:
            entries.append(data["entry"])
        return entries[:n_results]

    def _filter_by_market_type(
        self,
        market_type: str,
        limit: int
    ) -> List[ExperienceEntry]:
        """简单筛选"""
        entries = []
        for data in self.simple_store.values():
            if data["entry"].market_type == market_type:
                entries.append(data["entry"])
                if len(entries) >= limit:
                    break
        return entries


class ExperienceRetriever:
    """
    经验检索器
    在决策时检索相关历史经验
    """

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

    def retrieve_for_decision(
        self,
        current_market_type: str,
        current_price: float,
        current_narrative: str,
        n_results: int = 3
    ) -> List[Dict]:
        """
        为当前决策检索相关经验

        Args:
            current_market_type: 当前市场类型
            current_price: 当前价格
            current_narrative: 当前行情叙事

        Returns:
            检索结果列表
        """
        # 1. 检索相同市场类型的经验
        similar_by_type = self.vector_store.search_by_market_type(
            current_market_type, n_results
        )

        # 2. 检索盈利经验（正向学习）
        wins = self.vector_store.search_by_outcome("win", n_results)

        # 3. 检索亏损经验（警示学习）
        losses = self.vector_store.search_by_outcome("loss", n_results)

        return {
            "similar_market": [self._format_entry(e) for e in similar_by_type],
            "winning_cases": [self._format_entry(e) for e in wins],
            "loss_warnings": [self._format_entry(e) for e in losses]
        }

    def compare_similar_outcomes(
        self,
        market_type: str,
        trade_action: str
    ) -> Dict:
        """
        对比相似条件下的不同结果
        用于发现关键差异因素
        """
        # 获取相同条件下的盈利和亏损案例
        wins = self.vector_store.search_by_outcome("win", 10)
        losses = self.vector_store.search_by_outcome("loss", 10)

        # 过滤相同市场类型
        wins = [w for w in wins if w.market_type == market_type]
        losses = [l for l in losses if l.market_type == market_type]

        return {
            "wins": [self._format_entry(w) for w in wins[:5]],
            "losses": [self._format_entry(l) for l in losses[:5]],
            "analysis": "对比分析结果"
        }

    def _format_entry(self, entry: ExperienceEntry) -> Dict:
        """格式化经验条目"""
        return {
            "date": entry.date,
            "market_type": entry.market_type,
            "action": entry.trade_action,
            "outcome": entry.outcome,
            "pnl_pct": entry.pnl_pct,
            "experience_rule": entry.experience_rule,
            "narrative": entry.market_narrative[:200] + "..."
        }


def generate_embedding_text(trade_log) -> str:
    """
    从交易日志生成用于向量化的文本

    Args:
        trade_log: TradeLog对象

    Returns:
        向量化文本
    """
    return f"""
    市场类型: {trade_log.market_type}
    交易方向: {trade_log.direction}
    入场价格: {trade_log.entry_price}
    出场价格: {trade_log.exit_price}
    盈亏比例: {trade_log.pnl_pct}%
    结果: {trade_log.outcome}
    行情描述: {trade_log.market_narrative}
    思维链: {trade_log.decision_cot[:500]}
    """
