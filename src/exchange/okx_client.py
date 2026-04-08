"""
OKX API 客户端
封装OKX Futures API
"""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass

import ccxt


@dataclass
class AccountInfo:
    """账户信息"""
    balance_usdt: float
    equity_usdt: float
    margin_used: float
    margin_ratio: float
    available_balance: float


@dataclass
class PositionInfo:
    """持仓信息"""
    symbol: str
    side: str
    size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: int
    liquidation_price: float


class OKXClient:
    """
    OKX Futures API 客户端
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        testnet: bool = True
    ):
        self.api_key = api_key or os.environ.get("OKX_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("OKX_API_SECRET", "")
        self.passphrase = passphrase or os.environ.get("OKX_PASSPHRASE", "")
        self.testnet = testnet

        # 初始化ccxt
        config = {
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "password": self.passphrase,
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap"
            }
        }

        self.exchange = ccxt.okx(config)

        if testnet:
            # OKX模拟盘使用不同的域名
            self.exchange.set_sandbox_mode(True)

    def get_account_info(self) -> AccountInfo:
        """获取账户信息"""
        try:
            balance = self.exchange.fetch_balance()
            usdt_info = balance.get("USDT", {})

            total = usdt_info.get("total", 0)
            free = usdt_info.get("free", 0)
            used = usdt_info.get("used", 0)

            return AccountInfo(
                balance_usdt=total,
                equity_usdt=total,
                margin_used=used,
                margin_ratio=(total / used) if used > 0 else float('inf'),
                available_balance=free
            )
        except Exception as e:
            print(f"Error fetching OKX account info: {e}")
            return AccountInfo(0, 0, 0, 0, 0)

    def get_positions(self, symbol: Optional[str] = None) -> List[PositionInfo]:
        """获取持仓信息"""
        try:
            # OKX使用不同的API获取持仓
            positions = self.exchange.fetch_positions()

            result = []
            for pos in positions:
                if pos.get("contracts", 0) != 0:
                    result.append(PositionInfo(
                        symbol=pos.get("symbol", ""),
                        side="long" if pos.get("side") == "long" else "short",
                        size=abs(pos.get("contracts", 0)),
                        entry_price=pos.get("entryPrice", 0),
                        mark_price=pos.get("markPrice", 0),
                        unrealized_pnl=pos.get("unrealizedPnl", 0),
                        leverage=pos.get("leverage", 1),
                        liquidation_price=pos.get("liquidationPrice", 0)
                    ))

            return result
        except Exception as e:
            print(f"Error fetching OKX positions: {e}")
            return []

    def fetch_ohlcv(
        self,
        symbol: str = "BTC/USDT:USDT",
        timeframe: str = "1h",
        limit: int = 100
    ) -> List[List]:
        """获取K线数据"""
        try:
            return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            print(f"Error fetching OKX OHLCV: {e}")
            return []

    def fetch_order_book(self, symbol: str = "BTC/USDT:USDT", limit: int = 20) -> Dict:
        """获取订单簿"""
        try:
            return self.exchange.fetch_order_book(symbol, limit)
        except Exception as e:
            print(f"Error fetching OKX order book: {e}")
            return {}

    def fetch_funding_rate(self, symbol: str = "BTC/USDT:USDT") -> Dict:
        """获取资金费率"""
        try:
            return self.exchange.fetch_funding_rate(symbol)
        except Exception as e:
            print(f"Error fetching OKX funding rate: {e}")
            return {}

    def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """创建订单"""
        try:
            # OKX需要设置posSide参数：long/short/net
            order_params = params or {}
            if "posSide" not in order_params:
                # 根据side设置position side
                order_params["posSide"] = "long" if side == "buy" else "short"

            return self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price,
                params=order_params
            )
        except Exception as e:
            print(f"Error creating OKX order: {e}")
            return {}

    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """取消订单"""
        try:
            self.exchange.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            print(f"Error canceling OKX order: {e}")
            return False

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """设置杠杆"""
        try:
            self.exchange.set_leverage(leverage, symbol)
            return True
        except Exception as e:
            print(f"Error setting OKX leverage: {e}")
            return False
