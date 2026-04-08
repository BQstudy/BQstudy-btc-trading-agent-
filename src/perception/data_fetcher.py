"""
数据采集模块 - 连接Binance/OKX API获取市场数据
使用ccxt库统一接口
"""

import ccxt
import pandas as pd
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class MarketData:
    """市场数据结构"""
    symbol: str
    timeframe: str
    klines: pd.DataFrame  # OHLCV数据
    funding_rate: float
    funding_trend: str  # rising/falling/stable
    open_interest: float
    oi_change_24h: float
    long_liquidations: float  # 24h
    short_liquidations: float  # 24h
    orderbook: dict  # 买卖盘口
    timestamp: datetime


class DataFetcher:
    """交易所数据获取器"""

    def __init__(self, exchange_id: str = "binance", api_key: Optional[str] = None, secret: Optional[str] = None):
        """
        初始化数据获取器

        Args:
            exchange_id: 交易所ID (binance/okx)
            api_key: API密钥（可选，用于私有接口）
            secret: API密钥（可选）
        """
        self.exchange_id = exchange_id

        # 初始化交易所实例
        exchange_class = getattr(ccxt, exchange_id)
        config = {
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap"  # 永续合约
            }
        }
        if api_key and secret:
            config["apiKey"] = api_key
            config["secret"] = secret

        self.exchange = exchange_class(config)

    def fetch_ohlcv(
        self,
        symbol: str = "BTC/USDT:USDT",
        timeframe: str = "1h",
        limit: int = 100
    ) -> pd.DataFrame:
        """
        获取K线数据

        Args:
            symbol: 交易对
            timeframe: 时间周期 (15m, 1h, 4h, 1d)
            limit: 获取条数

        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]
        """
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        return df

    def fetch_multi_timeframe(
        self,
        symbol: str = "BTC/USDT:USDT",
        timeframes: List[str] = ["15m", "1h", "4h", "1d"]
    ) -> Dict[str, pd.DataFrame]:
        """
        获取多周期K线数据

        Returns:
            {timeframe: DataFrame}
        """
        result = {}
        for tf in timeframes:
            limit = 100 if tf in ["15m", "1h"] else 50
            result[tf] = self.fetch_ohlcv(symbol, tf, limit=limit)
        return result

    def fetch_funding_rate(self, symbol: str = "BTC/USDT:USDT") -> dict:
        """
        获取资金费率

        Returns:
            {
                "current": float,
                "trend": str,  # rising/falling/stable
                "history": List[float]  # 过去24h的历史
            }
        """
        # 当前资金费率
        funding = self.exchange.fetchFundingRate(symbol)
        current_rate = funding["fundingRate"]

        # 获取历史资金费率计算趋势
        try:
            funding_history = self.exchange.fetchFundingRateHistory(symbol, limit=3)
            rates = [f["fundingRate"] for f in funding_history]

            if len(rates) >= 2:
                if rates[0] > rates[-1]:
                    trend = "falling"
                elif rates[0] < rates[-1]:
                    trend = "rising"
                else:
                    trend = "stable"
            else:
                trend = "stable"
        except Exception:
            trend = "stable"
            rates = [current_rate]

        return {
            "current": current_rate,
            "trend": trend,
            "history": rates
        }

    def fetch_open_interest(self, symbol: str = "BTC/USDT:USDT") -> dict:
        """
        获取持仓量数据

        Returns:
            {
                "current": float,
                "change_24h": float  # 百分比变化
            }
        """
        try:
            oi_data = self.exchange.fetchOpenInterest(symbol)
            current_oi = oi_data["openInterestAmount"]

            # 计算24h变化（简化处理，实际可能需要历史数据）
            # 这里返回原始值，变化率由上层计算
            return {
                "current": current_oi,
                "change_24h": 0.0  # 需要额外计算
            }
        except Exception:
            return {"current": 0.0, "change_24h": 0.0}

    def fetch_liquidations(self, symbol: str = "BTC/USDT:USDT") -> dict:
        """
        获取爆仓数据

        Returns:
            {
                "long": float,  # 多头爆仓金额(USDT)
                "short": float  # 空头爆仓金额(USDT)
            }
        """
        try:
            # ccxt不直接支持爆仓数据，需要通过其他方式获取
            # 这里返回占位值，实际可通过聚合数据API获取
            return {
                "long": 0.0,
                "short": 0.0
            }
        except Exception:
            return {"long": 0.0, "short": 0.0}

    def fetch_orderbook(self, symbol: str = "BTC/USDT:USDT", limit: int = 20) -> dict:
        """
        获取订单簿深度

        Returns:
            {
                "bids": List[[price, amount], ...],
                "asks": List[[price, amount], ...],
                "spread": float,
                "spread_pct": float
            }
        """
        orderbook = self.exchange.fetchOrderBook(symbol, limit=limit)

        bids = orderbook["bids"]
        asks = orderbook["asks"]

        if bids and asks:
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            spread = best_ask - best_bid
            spread_pct = spread / best_bid
        else:
            spread = 0
            spread_pct = 0

        # 计算前10档深度
        bid_depth = sum([b[1] * b[0] for b in bids[:10]])
        ask_depth = sum([a[1] * a[0] for a in asks[:10]])

        return {
            "bids": bids,
            "asks": asks,
            "spread": spread,
            "spread_pct": spread_pct,
            "bid_depth_usdt": bid_depth,
            "ask_depth_usdt": ask_depth,
            "depth_ratio": bid_depth / ask_depth if ask_depth > 0 else 1.0
        }

    def fetch_full_market_data(self, symbol: str = "BTC/USDT:USDT") -> dict:
        """
        获取完整市场数据（用于感知层输入）

        Returns:
            包含所有必要字段的字典
        """
        # 获取当前价格
        ticker = self.exchange.fetchTicker(symbol)
        current_price = ticker["last"]
        price_change_24h = ticker.get("percentage", 0)

        # 获取多周期K线
        multi_tf = self.fetch_multi_timeframe(symbol)

        # 获取资金费率
        funding = self.fetch_funding_rate(symbol)

        # 获取持仓量
        oi = self.fetch_open_interest(symbol)

        # 获取爆仓数据
        liq = self.fetch_liquidations(symbol)

        # 获取订单簿
        ob = self.fetch_orderbook(symbol)

        # 计算距离前高前低
        daily_high = ticker.get("high", current_price)
        daily_low = ticker.get("low", current_price)
        dist_to_high = (daily_high - current_price) / current_price * 100
        dist_to_low = (current_price - daily_low) / current_price * 100

        return {
            "current_price": current_price,
            "price_change_24h": price_change_24h,
            "daily_high": daily_high,
            "daily_low": daily_low,
            "dist_to_high": round(dist_to_high, 2),
            "dist_to_low": round(dist_to_low, 2),
            "multi_tf_klines": multi_tf,
            "funding_rate": funding["current"],
            "funding_trend": funding["trend"],
            "open_interest": oi["current"],
            "oi_change_24h": oi["change_24h"],
            "long_liquidations": liq["long"],
            "short_liquidations": liq["short"],
            "orderbook": ob,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
