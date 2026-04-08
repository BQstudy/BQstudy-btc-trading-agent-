"""
Phase 4 单元测试
测试记忆经验系统各模块功能
"""

import unittest
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from memory.trade_logger import TradeLogger, TradeLog
from memory.review_engine import ReviewEngine, generate_review_prompt
from memory.vector_store import VectorStore, ExperienceEntry, ExperienceRetriever


class TestTradeLogger(unittest.TestCase):
    """测试交易日志记录器"""

    def setUp(self):
        # 使用测试数据库
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test_trades.db")
        self.logger = TradeLogger(self.test_db_path)

    def tearDown(self):
        # 关闭连接后清理
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass

    def test_log_trade_entry(self):
        """测试记录入场"""
        trade = TradeLog(
            trade_id="test-001",
            entry_time=datetime.utcnow().isoformat() + "Z",
            direction="long",
            entry_price=62000,
            quantity=0.1,
            margin_usdt=1000,
            leverage=10,
            market_type="trend_up",
            market_narrative="上涨趋势，突破关键阻力",
            decision_cot="判断上涨..."
        )

        trade_id = self.logger.log_trade_entry(trade)

        self.assertEqual(trade_id, "test-001")

        # 验证可以读取
        retrieved = self.logger.get_trade("test-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.direction, "long")

    def test_log_trade_exit(self):
        """测试记录出场"""
        # 先记录入场
        trade = TradeLog(
            trade_id="test-002",
            entry_time=datetime.utcnow().isoformat() + "Z",
            direction="long",
            entry_price=62000,
            quantity=0.1,
            margin_usdt=1000,
            leverage=10
        )
        self.logger.log_trade_entry(trade)

        # 记录出场
        exit_time = datetime.utcnow().isoformat() + "Z"
        self.logger.log_trade_exit(
            trade_id="test-002",
            exit_price=63000,
            exit_time=exit_time,
            outcome="win",
            pnl_usdt=100,
            pnl_pct=10,
            attribution={"win_reason": "judgment_correct"},
            experience_rule="趋势突破后回调入场"
        )

        # 验证
        retrieved = self.logger.get_trade("test-002")
        self.assertEqual(retrieved.outcome, "win")
        self.assertEqual(retrieved.pnl_usdt, 100)

    def test_get_recent_trades(self):
        """测试获取最近交易"""
        # 创建多条记录
        for i in range(5):
            trade = TradeLog(
                trade_id=f"test-{i}",
                entry_time=datetime.utcnow().isoformat() + "Z",
                direction="long",
                entry_price=62000,
                quantity=0.1,
                margin_usdt=1000
            )
            self.logger.log_trade_entry(trade)
            # 标记为已出场
            self.logger.log_trade_exit(
                trade_id=f"test-{i}",
                exit_price=63000,
                exit_time=datetime.utcnow().isoformat() + "Z",
                outcome="win",
                pnl_usdt=100,
                pnl_pct=10
            )

        trades = self.logger.get_recent_trades(limit=3)

        self.assertEqual(len(trades), 3)

    def test_get_statistics(self):
        """测试获取统计"""
        import uuid
        # 创建赢亏记录
        for outcome in ["win", "win", "loss"]:
            trade_id = f"stat-test-{outcome}-{uuid.uuid4().hex[:8]}"
            trade = TradeLog(
                trade_id=trade_id,
                entry_time=datetime.utcnow().isoformat() + "Z",
                direction="long",
                entry_price=62000,
                quantity=0.1,
                margin_usdt=1000
            )
            self.logger.log_trade_entry(trade)
            self.logger.log_trade_exit(
                trade_id=trade_id,
                exit_price=63000 if outcome == "win" else 61000,
                exit_time=datetime.utcnow().isoformat() + "Z",
                outcome=outcome,
                pnl_usdt=100 if outcome == "win" else -100,
                pnl_pct=10 if outcome == "win" else -10
            )

        stats = self.logger.get_statistics()

        self.assertGreaterEqual(stats["total_trades"], 3)


class TestReviewEngine(unittest.TestCase):
    """测试复盘引擎"""

    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test_trades_review.db")
        self.logger = TradeLogger(self.test_db_path)
        self.engine = ReviewEngine(self.logger)

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass

    def test_generate_review_prompt(self):
        """测试生成复盘提示词"""
        trade = TradeLog(
            trade_id="review-001",
            entry_time=datetime.utcnow().isoformat() + "Z",
            exit_time=datetime.utcnow().isoformat() + "Z",
            direction="long",
            entry_price=62000,
            exit_price=61000,
            pnl_usdt=-100,
            pnl_pct=-10,
            outcome="loss",
            market_type="trend_up",
            market_narrative="上涨趋势",
            decision_cot="判断突破..."
        )

        prompt = generate_review_prompt(trade)

        self.assertIn("复盘任务", prompt)
        self.assertIn("62000", prompt)
        self.assertIn("loss", prompt)

    def test_review_trade(self):
        """测试复盘交易"""
        # 创建交易
        trade = TradeLog(
            trade_id="review-002",
            entry_time=datetime.utcnow().isoformat() + "Z",
            direction="long",
            entry_price=62000,
            quantity=0.1,
            margin_usdt=1000
        )
        self.logger.log_trade_entry(trade)
        self.logger.log_trade_exit(
            trade_id="review-002",
            exit_price=63000,
            exit_time=datetime.utcnow().isoformat() + "Z",
            outcome="win",
            pnl_usdt=100,
            pnl_pct=10
        )

        # 复盘
        review = self.engine.review_trade("review-002")

        self.assertEqual(review.trade_id, "review-002")
        self.assertIsNotNone(review.chain_of_thought)


class TestVectorStore(unittest.TestCase):
    """测试向量存储"""

    def setUp(self):
        self.store = VectorStore("data/test_chroma")

    def test_add_experience(self):
        """测试添加经验"""
        entry = ExperienceEntry(
            id="exp-001",
            date="2025-01-15",
            market_type="trend_up",
            btc_price_range=[60000, 65000],
            market_narrative="上涨趋势",
            trade_action="long",
            entry_price=62000,
            exit_price=64000,
            pnl_pct=3.2,
            outcome="win",
            attribution={"win_reason": "judgment_correct"},
            experience_rule="趋势突破后入场"
        )

        exp_id = self.store.add_experience(entry)

        self.assertEqual(exp_id, "exp-001")

    def test_search_by_market_type(self):
        """测试按市场类型搜索"""
        # 添加几条记录
        for i, mt in enumerate(["trend_up", "trend_up", "range"]):
            entry = ExperienceEntry(
                id=f"exp-{i}",
                date="2025-01-15",
                market_type=mt,
                btc_price_range=[60000, 65000],
                market_narrative=f"{mt}行情",
                trade_action="long",
                entry_price=62000,
                exit_price=64000,
                pnl_pct=3.0,
                outcome="win",
                attribution={},
                experience_rule="经验"
            )
            self.store.add_experience(entry)

        results = self.store.search_by_market_type("trend_up", limit=5)

        # 简单存储返回所有
        self.assertIsInstance(results, list)

    def test_get_experience_summary(self):
        """测试获取经验摘要"""
        summary = self.store.get_experience_summary()

        self.assertIn("total_experiences", summary)
        self.assertIn("by_market_type", summary)


class TestExperienceRetriever(unittest.TestCase):
    """测试经验检索器"""

    def setUp(self):
        self.store = VectorStore("data/test_chroma_retriever")
        self.retriever = ExperienceRetriever(self.store)

    def test_retrieve_for_decision(self):
        """测试为决策检索经验"""
        results = self.retriever.retrieve_for_decision(
            current_market_type="trend_up",
            current_price=62000,
            current_narrative="上涨趋势"
        )

        self.assertIn("similar_market", results)
        self.assertIn("winning_cases", results)
        self.assertIn("loss_warnings", results)


if __name__ == "__main__":
    unittest.main()
