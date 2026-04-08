"""
集成测试
测试核心模块集成
"""

import unittest
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.llm_client import LLMConfig
from exchange.binance_client import BinanceClient
from exchange.okx_client import OKXClient
from exchange.exchange_factory import create_exchange_client


class TestLLMConfig(unittest.TestCase):
    """测试LLM配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = LLMConfig()

        self.assertEqual(config.model, "claude-sonnet-4-20250514")
        self.assertEqual(config.max_tokens, 8000)
        self.assertEqual(config.thinking_budget, 5000)

    def test_config_from_dict(self):
        """测试从字典创建配置"""
        config = LLMConfig(
            api_key="test_key",
            model="claude-opus",
            max_tokens=4000
        )

        self.assertEqual(config.api_key, "test_key")
        self.assertEqual(config.model, "claude-opus")


class TestExchangeClients(unittest.TestCase):
    """测试交易所客户端"""

    def test_binance_client_init(self):
        """测试Binance客户端初始化"""
        # 无API密钥时应该能初始化但无法调用API
        client = BinanceClient(testnet=True)

        self.assertIsNotNone(client)
        self.assertTrue(client.testnet)

    def test_okx_client_init(self):
        """测试OKX客户端初始化"""
        client = OKXClient(testnet=True)

        self.assertIsNotNone(client)
        self.assertTrue(client.testnet)

    def test_exchange_factory_binance(self):
        """测试交易所工厂 - Binance"""
        try:
            client = create_exchange_client("binance", testnet=True)
            self.assertIsInstance(client, BinanceClient)
        except Exception as e:
            # 配置文件可能不存在
            self.assertIn("config", str(e).lower() or "settings" in str(e).lower())

    def test_exchange_factory_okx(self):
        """测试交易所工厂 - OKX"""
        try:
            client = create_exchange_client("okx", testnet=True)
            self.assertIsInstance(client, OKXClient)
        except Exception as e:
            # 配置文件可能不存在
            self.assertIn("config", str(e).lower() or "settings" in str(e).lower())


class TestAgentIntegration(unittest.TestCase):
    """测试Agent集成"""

    def test_agent_import(self):
        """测试Agent模块导入"""
        from agent import BTCTradingAgent

        self.assertTrue(True)  # 如果能导入就成功

    def test_agent_init_without_config(self):
        """测试Agent无配置初始化"""
        from agent import BTCTradingAgent

        # 应该能初始化，但会打印警告
        agent = BTCTradingAgent("nonexistent_config.yaml")

        self.assertIsNotNone(agent)
        self.assertTrue(agent.paper_trading)  # 默认纸面交易


if __name__ == "__main__":
    unittest.main()
