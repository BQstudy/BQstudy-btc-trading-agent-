"""
Phase 1: 市场感知层
将原始市场数据转化为LLM可以进行主观判断的语言描述
"""

from .data_fetcher import DataFetcher, MarketData
from .market_narrator import MarketNarrator, CandlePattern
from .sentiment import SentimentAnalyzer, RegimeFlags

__all__ = [
    "DataFetcher",
    "MarketData",
    "MarketNarrator",
    "CandlePattern",
    "SentimentAnalyzer",
    "RegimeFlags",
]
