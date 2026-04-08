"""
Binance API 客户端
封装Binance Futures API
"""

import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

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
    side: str  # long/short
    size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: int
    liquidation_price: float


class BinanceClient:
    """
    Binance Futures API 客户端
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = True
    ):
        self.api_key = api_key or os.environ.get("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("BINANCE_API_SECRET", "")
        self.testnet = testnet

        # 初始化ccxt交易所
        config = {
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap"  # 永续合约
            }
        }

        if testnet:
            config["urls"] = {
                "api": {
                    "public": "https://testnet.binancefuture.com/fapi/v1",
                    "private": "https://testnet.binancefuture.com/fapi/v1"
                }
            }

        self.exchange = ccxt.binance(config)

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
            print(f"Error fetching account info: {e}")
            return AccountInfo(0, 0, 0, 0, 0)

    def get_positions(self, symbol: Optional[str] = None) -> List[PositionInfo]:
        """获取持仓信息"""
        try:
            positions = self.exchange.fetch_positions(
                [symbol] if symbol else None
            )

            result = []
            for pos in positions:
                if pos.get("contracts", 0) != 0:  # 只返回有持仓的
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
            print(f"Error fetching positions: {e}")
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
            print(f"Error fetching OHLCV: {e}")
            return []

    def fetch_order_book(self, symbol: str = "BTC/USDT:USDT", limit: int = 20) -> Dict:
        """获取订单簿"""
        try:
            return self.exchange.fetch_order_book(symbol, limit)
        except Exception as e:
            print(f"Error fetching order book: {e}")
            return {}

    def fetch_funding_rate(self, symbol: str = "BTC/USDT:USDT") -> Dict:
        """获取资金费率"""
        try:
            return self.exchange.fetch_funding_rate(symbol)
        except Exception as e:
            print(f"Error fetching funding rate: {e}")
            return {}

    def fetch_open_interest(self, symbol: str = "BTC/USDT:USDT") -> Dict:
        """获取持仓量"""
        try:
            return self.exchange.fetch_open_interest(symbol)
        except Exception as e:
            print(f"Error fetching open interest: {e}")
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
        """
        创建订单

        Args:
            symbol: 交易对
            order_type: 订单类型 (market/limit/stop_market等)
            side: 方向 (buy/sell)
            amount: 数量
            price: 价格（限价单需要）
            params: 额外参数

        Returns:
            订单信息
        """
        try:
            return self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price,
                params=params or {}
            )
        except Exception as e:
            print(f"Error creating order: {e}")
            return {}

    def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        post_only: bool = True
    ) -> Dict:
        """创建限价单"""
        params = {}
        if post_only:
            params["timeInForce"] = "GTX"  # Post Only

        return self.create_order(
            symbol=symbol,
            order_type="limit",
            side=side,
            amount=amount,
            price=price,
            params=params
        )

    def create_stop_loss_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        stop_price: float
    ) -> Dict:
        """创建止损单"""
        return self.create_order(
            symbol=symbol,
            order_type="stop_market",
            side=side,
            amount=amount,
            params={"stopPrice": stop_price}
        )

    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """取消订单"""
        try:
            self.exchange.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            print(f"Error canceling order: {e}")
            return False

    def cancel_all_orders(self, symbol: str) -> bool:
        """取消所有订单"""
        try:
            self.exchange.cancel_all_orders(symbol)
            return True
        except Exception as e:
            print(f"Error canceling all orders: {e}")
            return False

    def get_order_status(self, order_id: str, symbol: str) -> Dict:
        """获取订单状态"""
        try:
            return self.exchange.fetch_order(order_id, symbol)
        except Exception as e:
            print(f"Error fetching order status: {e}")
            return {}

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """设置杠杆"""
        try:
            self.exchange.set_leverage(leverage, symbol)
            return True
        except Exception as e:
            print(f"Error setting leverage: {e}")
            return False

    def get_ticker(self, symbol: str = "BTC/USDT:USDT") -> Dict:
        """获取最新价格"""
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            print(f"Error fetching ticker: {e}")
            return {}

    def get_mark_price(self, symbol: str = "BTC/USDT:USDT") -> float:
        """获取标记价格"""
        try:
            ticker = self.get_ticker(symbol)
            return ticker.get("last", 0)
        except Exception as e:
            print(f"Error fetching mark price: {e}")
            return 0
