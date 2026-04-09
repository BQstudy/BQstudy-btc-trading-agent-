"""
BTC交易Agent - 主程序入口
整合所有模块，实现完整交易流程
"""

import time
import json
import threading
from typing import Dict, Optional, Any
from datetime import datetime
from pathlib import Path
from enum import Enum


class TradingMode(Enum):
    """交易模式枚举"""
    PAPER = "paper"      # 纸面交易：纯模拟，不调用交易所API
    SIMULATION = "simulation"  # 模拟交易：OKX模拟盘（testnet）
    LIVE = "live"        # 实盘交易：真实账户

    def get_display_name(self) -> str:
        """获取显示名称"""
        return {
            TradingMode.PAPER: "纸面交易",
            TradingMode.SIMULATION: "模拟交易",
            TradingMode.LIVE: "实盘交易"
        }[self]


# 各阶段模块
from perception.data_fetcher import DataFetcher
from perception.market_narrator import MarketNarrator
from perception.sentiment import SentimentAnalyzer

from judgment.debate_engine import DebateEngine
from judgment.regime_detector import RegimeDetector
from judgment.level_analyzer import LevelAnalyzer

from decision.decision_engine import DecisionEngine
from decision.risk_manager import AccountState
from decision.executor import ExchangeExecutor

from memory.trade_logger import TradeLogger, TradeLog
from memory.review_engine import ReviewEngine
from memory.vector_store import VectorStore, ExperienceRetriever

from evolution.meta_analyzer import MetaAnalyzer
from evolution.distill_exporter import DistillExporter

from utils.llm_client import create_llm_client, MultiRoleClient
from utils.telegram_notifier import TelegramNotifier, create_notifier_from_config
from utils.telegram_bot import TelegramBotHandler, create_bot_handler, TradingMode as BotTradingMode
from utils.cot_logger import CoTLogger
from exchange.exchange_factory import create_exchange_client
from self_check import get_self_checker, SelfChecker


class BTCTradingAgent:
    """
    BTC永续合约交易Agent
    整合五阶段完整流程
    """

    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config_path = config_path

        # 加载配置
        self.config = self._load_config()

        # 运行状态
        self.running = False
        # 从配置读取交易模式，默认纸面交易
        mode_str = self.config.get("execution", {}).get("trading_mode", "paper")
        mode_map = {"paper": TradingMode.PAPER, "simulation": TradingMode.SIMULATION, "live": TradingMode.LIVE}
        self.trading_mode = mode_map.get(mode_str, TradingMode.PAPER)

        # 自检查模块 (Layer 1)
        self.self_checker = get_self_checker()

        # CoT日志记录器
        self.cot_logger = CoTLogger()

        # 初始化各模块（在 trading_mode 初始化之后）
        self._init_modules()

    def _load_config(self) -> Dict:
        """加载配置"""
        try:
            import yaml
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Failed to load config: {e}")
            return {}

    def _init_modules(self):
        """初始化各模块"""
        # Phase 1: 市场感知
        exchange_id = self.config.get("exchange", {}).get("default", "okx")
        self.data_fetcher = DataFetcher(exchange_id=exchange_id)
        self.market_narrator = MarketNarrator()
        self.sentiment_analyzer = SentimentAnalyzer()

        # Phase 2: 主观判断
        self.debate_engine = DebateEngine()
        self.regime_detector = RegimeDetector()
        self.level_analyzer = LevelAnalyzer()

        # Phase 3: 决策执行
        self.decision_engine = DecisionEngine()
        self.executor = ExchangeExecutor()

        # Phase 4: 记忆系统
        self.trade_logger = TradeLogger()
        self.review_engine = ReviewEngine(self.trade_logger)
        self.vector_store = VectorStore()
        self.experience_retriever = ExperienceRetriever(self.vector_store)

        # Phase 5: 自迭代
        self.meta_analyzer = MetaAnalyzer(self.trade_logger)
        self.distill_exporter = DistillExporter()

        # LLM客户端
        try:
            self.llm_client = create_llm_client(self.config_path)
            self.multi_role_client = MultiRoleClient(self.llm_client)
        except Exception as e:
            print(f"Warning: LLM client initialization failed: {e}")
            self.llm_client = None
            self.multi_role_client = None

        # 交易所客户端
        try:
            exchange_id = self.config.get("exchange", {}).get("default", "binance")
            testnet = self.config.get("exchange", {}).get("testnet", True)
            self.exchange = create_exchange_client(exchange_id, self.config_path, testnet)
        except Exception as e:
            print(f"Warning: Exchange client initialization failed: {e}")
            self.exchange = None

        # Telegram通知器
        try:
            self.notifier = create_notifier_from_config(self.config_path)
            notify_config = self.config.get("notifications", {}).get("notify_on", {})
            self.notify_on_trade = notify_config.get("trade_execution", True)
            self.notify_on_close = notify_config.get("trade_closed", True)
            self.notify_on_risk = notify_config.get("risk_alert", True)
            self.notify_on_cycle = notify_config.get("cycle_complete", True)
        except Exception as e:
            print(f"Warning: Telegram notifier initialization failed: {e}")
            self.notifier = None

        # Telegram Bot 命令处理器
        try:
            self.bot_handler = create_bot_handler(
                config_path=self.config_path,
                on_mode_change=self._handle_mode_change,
                on_get_status=self._get_agent_status
            )
            # 设置初始模式
            self.bot_handler.set_mode(self.trading_mode)
            # 启动 Bot 轮询
            self.bot_handler.start()
        except Exception as e:
            print(f"Warning: Telegram bot handler initialization failed: {e}")
            self.bot_handler = None

    def run_single_cycle(self) -> Dict[str, Any]:
        """
        运行单次交易周期

        Returns:
            完整周期结果
        """
        print(f"\n{'='*60}")
        print(f"交易周期开始: {datetime.now().isoformat()}")
        print(f"{'='*60}\n")

        result = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "phases": {}
        }

        # 发送周期开始通知
        if self.notifier and self.notify_on_cycle:
            self.notifier.send_notification(
                title="交易周期开始",
                content=f"开始新一轮交易分析...\n模式: {self.trading_mode.get_display_name()}",
                message_type="info"
            )

        try:
            # ========== Phase 1: 市场感知 ==========
            print("[Phase 1] 市场感知层...")
            perception_result = self._run_perception()
            result["phases"]["perception"] = perception_result
            print(f"  市场类型: {perception_result.get('market_type', 'unknown')}")

            # ========== Phase 2: 主观判断 ==========
            print("\n[Phase 2] 主观判断引擎...")
            judgment_result = self._run_judgment(perception_result)
            result["phases"]["judgment"] = judgment_result
            print(f"  方向: {judgment_result.get('final_judgment', {}).get('bias', 'neutral')}")
            print(f"  置信度: {judgment_result.get('final_judgment', {}).get('confidence', 0)}")

            # ========== Phase 3: 决策执行 ==========
            print("\n[Phase 3] 决策执行层...")

            # 获取账户状态
            account_state = self._get_account_state()

            decision_result = self._run_decision(
                judgment_result,
                perception_result,
                account_state
            )
            result["phases"]["decision"] = decision_result

            action = decision_result.get("action", "no_trade")
            print(f"  决策: {action}")

            if action != "no_trade":
                print(f"  入场区间: {decision_result.get('entry_zone')}")
                print(f"  止损: {decision_result.get('stop_loss')}")
                print(f"  仓位: {decision_result.get('position_size_pct')}%")

                # 执行交易（实盘或模拟盘）
                if self.trading_mode in [TradingMode.LIVE, TradingMode.SIMULATION] and self.exchange:
                    print("\n  [执行] 实盘下单...")
                    execution_result = self._execute_trade(decision_result)
                    result["execution"] = execution_result

                    # 发送交易执行通知
                    if self.notifier and self.notify_on_trade:
                        self.notifier.send_trade_notification(
                            action="开仓",
                            symbol="BTC/USDT:USDT",
                            side=decision_result.get("action", "long"),
                            price=execution_result.get("price", 0),
                            quantity=execution_result.get("quantity", 0),
                            leverage=decision_result.get("leverage", 1),
                            stop_loss=decision_result.get("stop_loss", 0)
                        )

            print(f"\n{'='*60}")
            print("交易周期完成")
            print(f"{'='*60}\n")

            # 记录周期完成 (Layer 1自检查)
            self.self_checker.record_cycle_complete()

            # 发送周期完成通知（包含思考过程）
            if self.notifier and self.notify_on_cycle:
                action = decision_result.get("action", "no_trade")

                # 收集思考过程
                perception = perception_result or {}
                judgment = judgment_result or {}
                decision = decision_result or {}

                # Phase 1 感知摘要
                market_narrative = perception.get("market_narrative", "")[:200] if perception.get("market_narrative") else "无"
                sentiment = perception.get("sentiment", "unknown")
                market_type = perception.get("market_type", "unknown")

                # Phase 2 判断摘要
                final_judgment = judgment.get("final_judgment", {})
                bias = final_judgment.get("bias", "neutral")
                confidence = final_judgment.get("confidence", 0)
                debate_summary = judgment.get("debate_summary", "")[:300] if judgment.get("debate_summary") else "无"

                # Phase 3 决策摘要
                entry_zone = decision.get("entry_zone", "无")
                stop_loss = decision.get("stop_loss", "无")
                position_size = decision.get("position_size_pct", 0)
                reason = decision.get("reason_for_no_trade", "无")
                if action != "no_trade":
                    reason = f"止损{stop_loss}，仓位{position_size}%"

                # 组装详细通知 (使用HTML格式避免Markdown解析错误)
                content = f"""📊 <b>市场感知</b>
• 类型: {market_type}
• 情绪: {sentiment}
• 叙述: {market_narrative}...

🧠 <b>主观判断</b>
• 方向: {bias}
• 置信度: {confidence:.0%}
• 辩论: {debate_summary}...

📌 <b>最终决策</b>
• 行动: {action}
• {reason}

⏰ {datetime.now().strftime("%H:%M:%S")}"""

                msg_type = "success" if action != "no_trade" else "info"
                notify_success = self.notifier.send_notification(
                    title=f"交易周期完成 | {action.upper()}",
                    content=content,
                    message_type=msg_type
                )

                # 记录Telegram发送状态 (Layer 1自检查)
                if notify_success:
                    self.self_checker.record_telegram_success()
                else:
                    self.self_checker.record_telegram_failure("发送失败")

            return result

        except Exception as e:
            print(f"Error in trading cycle: {e}")
            import traceback
            traceback.print_exc()
            result["error"] = str(e)

            # 记录错误 (Layer 1自检查)
            self.self_checker.record_error(
                str(e),
                {"phase": "main_cycle", "type": type(e).__name__}
            )

            # 发送错误通知
            if self.notifier:
                self.notifier.send_risk_alert(
                    alert_type="系统错误",
                    message=f"交易周期执行失败: {str(e)}",
                    details={"错误类型": type(e).__name__}
                )

            return result

    def _run_perception(self) -> Dict:
        """运行市场感知"""
        # 获取市场数据
        market_data = self.data_fetcher.fetch_full_market_data()

        # 生成叙事
        narrative_result = self.market_narrator.compose_full_narrative(market_data)

        # 计算事实锚点
        regime_flags = self.sentiment_analyzer.calculate_regime_flags(
            multi_tf_data=market_data.get("multi_tf_klines", {}),
            funding_rate=market_data.get("funding_rate", 0),
            oi_change_pct=market_data.get("oi_change_24h", 0),
            orderbook=market_data.get("orderbook")
        )

        # 格式化锚点
        flags_text = self.sentiment_analyzer.format_flags_for_prompt(regime_flags)

        perception_output = {
            **narrative_result,
            "market_data": market_data,
            "regime_flags": regime_flags,
            "regime_flags_text": flags_text
        }

        # 记录CoT日志
        market_context = {
            "current_price": market_data.get("current_price", 0),
            "market_type": narrative_result.get("market_type", "unknown"),
            "sentiment": narrative_result.get("sentiment", "unknown"),
        }
        self.cot_logger.log(
            phase="perception",
            chain_of_thought=narrative_result.get("market_narrative", ""),
            decision={
                "sentiment": narrative_result.get("sentiment", "unknown"),
                "market_type": narrative_result.get("market_type", "unknown"),
            },
            market_context=market_context
        )

        return perception_output

    def _run_judgment(self, perception_result: Dict) -> Dict:
        """运行主观判断"""
        # 行情性质判断
        multi_tf = perception_result.get("market_data", {}).get("multi_tf_klines", {})
        regime_analysis = self.regime_detector.analyze(multi_tf)

        # 支撑压力分析
        current_price = perception_result.get("market_data", {}).get("current_price", 0)
        level_analysis = self.level_analyzer.analyze(multi_tf, current_price)

        # 多角色辩论（使用LLM）
        if self.multi_role_client:
            # 生成用户消息
            user_message = self.debate_engine.generate_user_message(
                perception_output=perception_result,
                regime_flags=perception_result.get("regime_flags", {}),
                market_data=perception_result.get("market_data", {})
            )

            # 这里简化处理，实际应该调用多角色辩论
            # debate_result = self.multi_role_client.call_debate(...)

        # 简化：使用代码层分析结果
        judgment_output = {
            "market_regime": regime_analysis.regime.value,
            "regime_analysis": {
                "trend_strength": regime_analysis.trend_strength,
                "breakout_probability": regime_analysis.breakout_probability,
                "trend_evidence": regime_analysis.trend_evidence,
                "invalidation_condition": regime_analysis.invalidation_condition
            },
            "level_analysis": {
                "key_supports": [s.price for s in level_analysis.critical_supports[:3]],
                "key_resistances": [r.price for r in level_analysis.critical_resistances[:3]],
                "current_zone": level_analysis.current_zone
            },
            "final_judgment": {
                "bias": perception_result.get("sentiment", "neutral"),
                "confidence": 0.6 if perception_result.get("confidence") == "high" else 0.4,
                "strength": "moderate",
                "key_invalidation": regime_analysis.invalidation_condition
            }
        }

        # 记录CoT日志
        analysis_text = f"""
市场状态: {regime_analysis.regime.value}
趋势强度: {regime_analysis.trend_strength}
突破概率: {regime_analysis.breakout_probability}
趋势证据: {regime_analysis.trend_evidence}
失效条件: {regime_analysis.invalidation_condition}
关键支撑: {[s.price for s in level_analysis.critical_supports[:3]]}
关键阻力: {[r.price for r in level_analysis.critical_resistances[:3]]}
当前区域: {level_analysis.current_zone}
"""
        self.cot_logger.log(
            phase="judgment",
            chain_of_thought=analysis_text,
            decision={
                "bias": perception_result.get("sentiment", "neutral"),
                "confidence": 0.6 if perception_result.get("confidence") == "high" else 0.4,
            }
        )

        return judgment_output

    def _run_decision(
        self,
        judgment_result: Dict,
        perception_result: Dict,
        account_state: AccountState
    ) -> Dict:
        """运行决策"""
        # 使用决策引擎
        decision = self.decision_engine.make_decision(
            judgment_result=judgment_result,
            perception_output=perception_result,
            account_state=account_state,
            market_data=perception_result.get("market_data", {})
        )

        decision_dict = decision.to_dict()

        # 记录CoT日志
        reason = decision_dict.get("reason_for_no_trade", "")
        action = decision_dict.get("action", "no_trade")
        chain_of_thought = f"""
决策: {action}
方向: {decision_dict.get('bias', 'neutral')}
置信度: {decision_dict.get('confidence', 0)}
入场区间: {decision_dict.get('entry_zone', [])}
止损: {decision_dict.get('stop_loss', 0)}
仓位: {decision_dict.get('position_size_pct', 0)}%
理由: {reason if reason else '通过风控检查，执行交易'}
"""
        self.cot_logger.log(
            phase="decision",
            chain_of_thought=chain_of_thought,
            decision=decision_dict
        )

        return decision_dict

    def _get_account_state(self) -> AccountState:
        """获取账户状态"""
        if self.exchange:
            try:
                account_info = self.exchange.get_account_info()
                positions = self.exchange.get_positions()

                # 计算连续亏损
                recent_trades = self.trade_logger.get_recent_trades(10)
                consecutive_losses = 0
                for trade in reversed(recent_trades):
                    if trade.outcome == "loss":
                        consecutive_losses += 1
                    else:
                        break

                return AccountState(
                    account_id="main",
                    balance_usdt=account_info.balance_usdt,
                    equity_usdt=account_info.equity_usdt,
                    margin_used=account_info.margin_used,
                    margin_ratio=account_info.margin_ratio,
                    daily_pnl=0,  # 需要计算
                    daily_pnl_pct=0,
                    total_pnl=0,
                    consecutive_losses=consecutive_losses,
                    max_drawdown_pct=0  # 需要计算
                )
            except Exception as e:
                print(f"Error getting account state: {e}")

        # 默认账户状态
        return AccountState(
            account_id="paper",
            balance_usdt=10000,
            equity_usdt=10000,
            margin_used=0,
            margin_ratio=1.0,
            daily_pnl=0,
            daily_pnl_pct=0,
            total_pnl=0,
            consecutive_losses=0,
            max_drawdown_pct=0
        )

    def _execute_trade(self, decision: Dict) -> Dict:
        """执行交易"""
        if not self.exchange:
            return {"error": "Exchange not available"}

        # 设置杠杆
        symbol = "BTC/USDT:USDT"
        leverage = decision.get("leverage", 1)
        self.exchange.set_leverage(symbol, leverage)

        # 创建订单
        entry_zone = decision.get("entry_zone", [])
        if len(entry_zone) >= 2:
            price = (entry_zone[0] + entry_zone[1]) / 2
        else:
            price = entry_zone[0] if entry_zone else 0

        side = "buy" if decision.get("action") == "long" else "sell"
        quantity = decision.get("position_result", {}).get("quantity_btc", 0)

        # 创建限价单
        order = self.exchange.create_limit_order(
            symbol=symbol,
            side=side,
            amount=quantity,
            price=price,
            post_only=True
        )

        return {
            "order_id": order.get("id"),
            "symbol": symbol,
            "side": side,
            "price": price,
            "quantity": quantity
        }

    def run_continuous(self, interval_seconds: int = 3600):
        """
        持续运行

        Args:
            interval_seconds: 运行间隔（秒）
        """
        self.running = True

        print(f"\n{'='*60}")
        print("BTC交易Agent启动")
        print(f"模式: {self.trading_mode.get_display_name()}")
        print(f"运行间隔: {interval_seconds}秒")
        print(f"{'='*60}\n")

        # 发送启动通知
        if self.notifier:
            self.notifier.send_notification(
                title="Agent启动",
                content=f"模式: {self.trading_mode.get_display_name()}\n运行间隔: {interval_seconds}秒",
                message_type="success"
            )

        while self.running:
            try:
                self.run_single_cycle()

                print(f"等待 {interval_seconds} 秒...")
                time.sleep(interval_seconds)

            except KeyboardInterrupt:
                print("\n收到停止信号，正在退出...")
                self.running = False
                break
            except Exception as e:
                print(f"Error in continuous run: {e}")
                time.sleep(60)  # 出错后等待1分钟

        print("\nAgent已停止")

        # 发送停止通知
        if self.notifier:
            self.notifier.send_notification(
                title="Agent停止",
                content="Agent已正常停止运行",
                message_type="warning"
            )

    def stop(self):
        """停止Agent"""
        self.running = False
        if self.bot_handler:
            self.bot_handler.stop()

    def _handle_mode_change(self, new_mode: BotTradingMode) -> bool:
        """
        处理 Telegram Bot 的模式切换请求

        Args:
            new_mode: 新的交易模式

        Returns:
            是否切换成功
        """
        try:
            # 映射 BotTradingMode 到 TradingMode
            mode_map = {
                BotTradingMode.PAPER: TradingMode.PAPER,
                BotTradingMode.SIMULATION: TradingMode.SIMULATION,
                BotTradingMode.LIVE: TradingMode.LIVE
            }

            if new_mode not in mode_map:
                print(f"[Agent] 未知的交易模式: {new_mode}")
                return False

            target_mode = mode_map[new_mode]

            # 检查是否可以切换到目标模式
            if target_mode in [TradingMode.SIMULATION, TradingMode.LIVE]:
                if not self.exchange:
                    print(f"[Agent] 无法切换到 {target_mode.get_display_name()}: 交易所未初始化")
                    return False

            # 执行模式切换
            old_mode = self.trading_mode
            self.trading_mode = target_mode

            # 更新 Bot handler 的状态
            if self.bot_handler:
                self.bot_handler.set_mode(new_mode)

            # 发送通知
            if self.notifier:
                self.notifier.send_notification(
                    title="交易模式已切换",
                    content=f"从 {old_mode.get_display_name()} 切换到 {target_mode.get_display_name()}",
                    message_type="warning" if target_mode == TradingMode.LIVE else "info"
                )

            print(f"[Agent] 交易模式已切换: {old_mode.get_display_name()} -> {target_mode.get_display_name()}")
            return True

        except Exception as e:
            print(f"[Agent] 模式切换失败: {e}")
            return False

    def _get_agent_status(self) -> Dict:
        """
        获取 Agent 状态（供 Telegram Bot 查询）

        Returns:
            状态字典
        """
        return {
            "running": "运行中" if self.running else "已停止",
            "mode": self.trading_mode.get_display_name(),
            "cycles_completed": getattr(self.self_checker, 'cycles_completed', 0),
            "last_cycle": getattr(self.self_checker, 'last_cycle_time', "未知"),
            "telegram_status": "正常" if self.notifier else "未启用",
            "exchange_status": "已连接" if self.exchange else "未连接"
        }

    def set_trading_mode(self, mode: TradingMode):
        """设置交易模式

        Args:
            mode: TradingMode.PAPER/SIMULATION/LIVE
        """
        self.trading_mode = mode
        print(f"交易模式: {mode.get_display_name()}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="BTC交易Agent")
    parser.add_argument("--config", default="config/settings.yaml", help="配置文件路径")
    parser.add_argument("--mode", choices=["paper", "simulation", "live"],
                        default="paper", help="交易模式: paper=纸面交易, simulation=模拟交易(OKX模拟盘), live=实盘交易")
    parser.add_argument("--once", action="store_true", help="运行单次周期")
    parser.add_argument("--interval", type=int, default=3600, help="运行间隔（秒）")

    args = parser.parse_args()

    # 创建Agent
    agent = BTCTradingAgent(args.config)

    # 设置交易模式
    mode_map = {
        "paper": TradingMode.PAPER,
        "simulation": TradingMode.SIMULATION,
        "live": TradingMode.LIVE
    }
    agent.set_trading_mode(mode_map[args.mode])

    # 运行
    if args.once:
        agent.run_single_cycle()
    else:
        agent.run_continuous(args.interval)


# 健康检查端点
def run_health_server():
    """运行HTTP健康检查服务器，集成自检查数据"""
    import http.server
    import socketserver
    import threading
    from self_check import get_self_checker

    checker = get_self_checker()

    class HealthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                # 获取自检查状态
                status = checker.get_simple_status()

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(status).encode())

            elif self.path == "/health/detail":
                # 获取详细状态
                status = checker.get_health_status()

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()

                # 转换为可序列化的字典
                import dataclasses
                self.wfile.write(json.dumps(dataclasses.asdict(status)).encode())

            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # 静默日志

    port = 8080
    with socketserver.TCPServer(("", port), HealthHandler) as httpd:
        print(f"健康检查服务器运行在 http://localhost:{port}/health")
        httpd.serve_forever()


if __name__ == "__main__":
    # 在后台启动健康检查服务器
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    main()
