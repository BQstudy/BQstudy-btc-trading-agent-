"""
交易所工厂
根据配置创建对应的交易所客户端
"""

import os
import yaml
from typing import Optional, Union

from .binance_client import BinanceClient
from .okx_client import OKXClient


def create_exchange_client(
    exchange_id: str = "binance",
    config_path: str = "config/settings.yaml",
    testnet: bool = True
) -> Union[BinanceClient, OKXClient]:
    """
    创建交易所客户端

    Args:
        exchange_id: 交易所ID (binance/okx)
        config_path: 配置文件路径
        testnet: 是否使用测试网

    Returns:
        交易所客户端实例
    """
    # 尝试从配置文件加载
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            exchange_config = config.get("exchange", {})
    except Exception:
        exchange_config = {}

    if exchange_id.lower() == "binance":
        # 从环境变量或配置获取
        api_key = os.environ.get("BINANCE_API_KEY") or exchange_config.get("binance", {}).get("api_key", "")
        api_secret = os.environ.get("BINANCE_API_SECRET") or exchange_config.get("binance", {}).get("api_secret", "")

        return BinanceClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet
        )

    elif exchange_id.lower() == "okx":
        api_key = os.environ.get("OKX_API_KEY") or exchange_config.get("okx", {}).get("api_key", "")
        api_secret = os.environ.get("OKX_API_SECRET") or exchange_config.get("okx", {}).get("api_secret", "")
        passphrase = os.environ.get("OKX_PASSPHRASE") or exchange_config.get("okx", {}).get("passphrase", "")

        return OKXClient(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            testnet=testnet
        )

    else:
        raise ValueError(f"Unsupported exchange: {exchange_id}")


def get_exchange_from_config(config_path: str = "config/settings.yaml") -> str:
    """
    从配置获取默认交易所

    Args:
        config_path: 配置文件路径

    Returns:
        交易所ID
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get("exchange", {}).get("default", "binance")
    except Exception:
        return "binance"
