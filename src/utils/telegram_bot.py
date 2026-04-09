"""
Telegram Bot 命令处理器
支持通过 Telegram 命令控制交易 Agent
"""

import os
import json
import requests
import threading
import time
from typing import Optional, Dict, Callable, Any
from datetime import datetime
from enum import Enum


class TradingMode(Enum):
    """交易模式枚举"""
    PAPER = "paper"
    SIMULATION = "simulation"
    LIVE = "live"

    def get_display_name(self) -> str:
        """获取显示名称"""
        return {
            TradingMode.PAPER: "纸面交易",
            TradingMode.SIMULATION: "模拟交易",
            TradingMode.LIVE: "实盘交易"
        }[self]

    def get_description(self) -> str:
        """获取描述"""
        return {
            TradingMode.PAPER: "纯模拟，不调用交易所API",
            TradingMode.SIMULATION: "OKX模拟盘(testnet)",
            TradingMode.LIVE: "真实资金交易"
        }[self]


class TelegramBotHandler:
    """
    Telegram Bot 命令处理器
    支持 /mode, /status, /start, /help 等命令
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        on_mode_change: Optional[Callable[[TradingMode], bool]] = None,
        on_get_status: Optional[Callable[[], Dict]] = None
    ):
        """
        初始化 Bot 处理器

        Args:
            bot_token: Bot Token
            on_mode_change: 模式切换回调函数
            on_get_status: 获取状态回调函数
        """
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.enabled = bool(self.bot_token)
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.session = requests.Session()

        # 回调函数
        self.on_mode_change = on_mode_change
        self.on_get_status = on_get_status

        # 当前模式
        self.current_mode = TradingMode.PAPER

        # 运行状态
        self.running = False
        self.last_update_id = 0
        self._thread: Optional[threading.Thread] = None

        # 命令处理映射
        self.commands = {
            "/start": self._cmd_start,
            "/help": self._cmd_help,
            "/mode": self._cmd_mode,
            "/status": self._cmd_status,
            "/mode_paper": self._cmd_mode_paper,
            "/mode_simulation": self._cmd_mode_simulation,
            "/mode_live": self._cmd_mode_live,
        }

    def start(self):
        """启动 Bot 轮询"""
        if not self.enabled:
            print("[TelegramBot] Bot 未启用，请配置 bot_token")
            return False

        self.running = True
        self._thread = threading.Thread(target=self._poll_updates, daemon=True)
        self._thread.start()
        print("[TelegramBot] Bot 命令处理器已启动")
        return True

    def stop(self):
        """停止 Bot 轮询"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[TelegramBot] Bot 命令处理器已停止")

    def set_mode(self, mode: TradingMode):
        """设置当前模式（用于初始化）"""
        self.current_mode = mode

    def _poll_updates(self):
        """轮询获取更新"""
        while self.running:
            try:
                updates = self._get_updates()
                for update in updates:
                    self._process_update(update)
                time.sleep(1)  # 每秒轮询一次
            except Exception as e:
                print(f"[TelegramBot] 轮询异常: {e}")
                time.sleep(5)

    def _get_updates(self) -> list:
        """获取更新"""
        url = f"{self.base_url}/getUpdates"
        params = {
            "offset": self.last_update_id + 1,
            "limit": 100
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            result = response.json()

            if result.get("ok"):
                updates = result.get("result", [])
                if updates:
                    self.last_update_id = updates[-1]["update_id"]
                return updates
        except Exception as e:
            print(f"[TelegramBot] 获取更新失败: {e}")

        return []

    def _process_update(self, update: Dict):
        """处理单个更新"""
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")

        if not text or not chat_id:
            return

        # 解析命令
        command = text.split()[0].lower()

        if command in self.commands:
            self.commands[command](chat_id, text)

    def _send_message(self, chat_id: int, text: str, parse_mode: str = "HTML"):
        """发送消息"""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }

        try:
            self.session.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"[TelegramBot] 发送消息失败: {e}")

    # ========== 命令处理 ==========

    def _cmd_start(self, chat_id: int, text: str):
        """/start 命令"""
        welcome_text = """🤖 <b>BTC 交易 Agent</b>

欢迎使用交易控制 Bot！

<b>可用命令：</b>
/mode - 查看/切换交易模式
/mode_paper - 切换到纸面交易
/mode_simulation - 切换到模拟交易
/mode_live - 切换到实盘交易
/status - 查看当前状态
/help - 显示帮助

<b>当前模式：</b> {mode}
""".format(mode=self.current_mode.get_display_name())

        self._send_message(chat_id, welcome_text)

    def _cmd_help(self, chat_id: int, text: str):
        """/help 命令"""
        help_text = """📖 <b>命令帮助</b>

<b>/mode</b>
查看当前交易模式，显示模式切换按钮

<b>/mode_paper</b>
切换到<b>纸面交易</b>模式
• 纯模拟，不调用交易所 API
• 仅记录决策，不下单

<b>/mode_simulation</b>
切换到<b>模拟交易</b>模式
• 使用 OKX 模拟盘 (testnet)
• 真实下单，但使用虚拟资金

<b>/mode_live</b>
切换到<b>实盘交易</b>模式 ⚠️
• 使用真实资金进行交易
• 请确保已配置正确的 API Key

<b>/status</b>
查看 Agent 当前运行状态

<b>/help</b>
显示此帮助信息
"""
        self._send_message(chat_id, help_text)

    def _cmd_mode(self, chat_id: int, text: str):
        """/mode 命令"""
        mode_text = """🎮 <b>交易模式设置</b>

<b>当前模式：</b> {current_mode}

<b>可用模式：</b>

📄 <b>纸面交易 (paper)</b>
{paper_desc}

🧪 <b>模拟交易 (simulation)</b>
{simulation_desc}

💰 <b>实盘交易 (live)</b>
{live_desc}

<b>切换命令：</b>
/mode_paper - 纸面交易
/mode_simulation - 模拟交易
/mode_live - 实盘交易
""".format(
            current_mode=self.current_mode.get_display_name(),
            paper_desc=TradingMode.PAPER.get_description(),
            simulation_desc=TradingMode.SIMULATION.get_description(),
            live_desc=TradingMode.LIVE.get_description()
        )

        self._send_message(chat_id, mode_text)

    def _cmd_mode_paper(self, chat_id: int, text: str):
        """/mode_paper 命令"""
        self._change_mode(chat_id, TradingMode.PAPER)

    def _cmd_mode_simulation(self, chat_id: int, text: str):
        """/mode_simulation 命令"""
        self._change_mode(chat_id, TradingMode.SIMULATION)

    def _cmd_mode_live(self, chat_id: int, text: str):
        """/mode_live 命令"""
        self._change_mode(chat_id, TradingMode.LIVE)

    def _change_mode(self, chat_id: int, new_mode: TradingMode):
        """切换模式"""
        if new_mode == self.current_mode:
            self._send_message(
                chat_id,
                f"ℹ️ 当前已经是 <b>{new_mode.get_display_name()}</b> 模式"
            )
            return

        # 实盘交易需要确认
        if new_mode == TradingMode.LIVE:
            confirm_text = """⚠️ <b>确认切换到实盘交易？</b>

实盘交易将使用<b>真实资金</b>进行交易！

请确认：
1. 已配置正确的 API Key
2. 已了解交易风险
3. 已设置合理的仓位和止损

如需切换，请再次发送 /mode_live

当前模式：<b>{current}</b>
目标模式：<b>{target}</b>
""".format(
                current=self.current_mode.get_display_name(),
                target=new_mode.get_display_name()
            )
            self._send_message(chat_id, confirm_text)
            return

        # 执行模式切换
        if self.on_mode_change:
            success = self.on_mode_change(new_mode)
            if success:
                self.current_mode = new_mode
                self._send_message(
                    chat_id,
                    f"✅ 已切换到 <b>{new_mode.get_display_name()}</b> 模式\n\n{new_mode.get_description()}"
                )
            else:
                self._send_message(
                    chat_id,
                    f"❌ 切换到 <b>{new_mode.get_display_name()}</b> 失败，请检查日志"
                )
        else:
            # 没有回调函数，仅更新本地状态
            self.current_mode = new_mode
            self._send_message(
                chat_id,
                f"✅ 已切换到 <b>{new_mode.get_display_name()}</b> 模式\n\n⚠️ 注意：Agent 需要重启才能生效"
            )

    def _cmd_status(self, chat_id: int, text: str):
        """/status 命令"""
        if self.on_get_status:
            status = self.on_get_status()
            status_text = """📊 <b>Agent 状态</b>

<b>交易模式：</b> {mode}
<b>运行状态：</b> {running}
<b>当前时间：</b> {time}
""".format(
                mode=self.current_mode.get_display_name(),
                running=status.get("running", "未知"),
                time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            # 添加额外状态信息
            if "cycles_completed" in status:
                status_text += f"\n<b>完成周期：</b> {status['cycles_completed']}"
            if "last_trade" in status:
                status_text += f"\n<b>最后交易：</b> {status['last_trade']}"

        else:
            status_text = """📊 <b>Agent 状态</b>

<b>交易模式：</b> {mode}
<b>当前时间：</b> {time}

<i>详细状态信息不可用</i>
""".format(
                mode=self.current_mode.get_display_name(),
                time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

        self._send_message(chat_id, status_text)


def create_bot_handler(
    config_path: str = "config/settings.yaml",
    on_mode_change: Optional[Callable[[TradingMode], bool]] = None,
    on_get_status: Optional[Callable[[], Dict]] = None
) -> TelegramBotHandler:
    """
    从配置文件创建 Bot 处理器

    Args:
        config_path: 配置文件路径
        on_mode_change: 模式切换回调
        on_get_status: 获取状态回调

    Returns:
        TelegramBotHandler 实例
    """
    import yaml

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        telegram_config = config.get("notifications", {}).get("telegram", {})

        handler = TelegramBotHandler(
            bot_token=telegram_config.get("bot_token", ""),
            on_mode_change=on_mode_change,
            on_get_status=on_get_status
        )

        # 从配置读取初始模式
        mode_str = config.get("execution", {}).get("trading_mode", "paper")
        mode_map = {
            "paper": TradingMode.PAPER,
            "simulation": TradingMode.SIMULATION,
            "live": TradingMode.LIVE
        }
        if mode_str in mode_map:
            handler.set_mode(mode_map[mode_str])

        return handler

    except Exception as e:
        print(f"[TelegramBot] 从配置创建失败: {e}")
        return TelegramBotHandler(enabled=False)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("Telegram Bot 命令处理器测试")
    print("=" * 60)

    def on_mode_change(mode: TradingMode) -> bool:
        print(f"[回调] 切换到模式: {mode.get_display_name()}")
        return True

    def on_get_status() -> Dict:
        return {
            "running": "运行中",
            "cycles_completed": 10,
            "last_trade": "2024-01-15 10:30:00"
        }

    handler = create_bot_handler(
        on_mode_change=on_mode_change,
        on_get_status=on_get_status
    )

    if handler.enabled:
        print("\nBot 已启动，请在 Telegram 中发送命令测试")
        print("可用命令: /start, /help, /mode, /mode_paper, /mode_simulation, /mode_live, /status")
        handler.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n停止测试...")
            handler.stop()
    else:
        print("\nBot 未启用，请检查配置")
