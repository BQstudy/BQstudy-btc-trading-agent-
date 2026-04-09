"""
Telegram通知模块
用于发送交易通知、警报和报告
"""

import os
import json
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass


@dataclass
class NotificationMessage:
    """通知消息结构"""
    title: str
    content: str
    message_type: str = "info"  # info/warning/error/success
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class TelegramNotifier:
    """
    Telegram Bot通知器
    支持发送交易通知、风控警报、日报等
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: bool = True
    ):
        """
        初始化Telegram通知器

        Args:
            bot_token: Bot Token (从@BotFather获取)
            chat_id: 聊天ID (可以是用户ID或频道ID)
            enabled: 是否启用通知
        """
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = enabled and bool(self.bot_token and self.chat_id)

        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.session = requests.Session()

        # 消息类型对应的emoji
        self.type_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
            "trade": "💰",
            "alert": "🚨"
        }

    def send_message(
        self,
        text: str,
        parse_mode: str = "Markdown",
        disable_notification: bool = False
    ) -> bool:
        """
        发送普通消息

        Args:
            text: 消息内容
            parse_mode: 解析模式 (Markdown/HTML)
            disable_notification: 是否静默发送

        Returns:
            是否发送成功
        """
        if not self.enabled:
            print("[Telegram] 通知未启用")
            return False

        url = f"{self.base_url}/sendMessage"

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification
        }

        try:
            response = self.session.post(url, json=payload, timeout=10)
            result = response.json()

            if result.get("ok"):
                return True
            else:
                print(f"[Telegram] 发送失败: {result.get('description')}")
                return False

        except Exception as e:
            print(f"[Telegram] 发送异常: {e}")
            return False

    def send_notification(
        self,
        title: str = "",
        content: str = "",
        message_type: str = "info",
        message: NotificationMessage = None
    ) -> bool:
        """
        发送格式化的通知消息

        Args:
            title: 通知标题
            content: 通知内容
            message_type: 消息类型 (info/warning/error/success)
            message: NotificationMessage对象 (可选，优先使用)

        Returns:
            是否发送成功
        """
        # 如果传入message对象，使用它
        if message is not None:
            msg = message
        else:
            msg = NotificationMessage(
                title=title,
                content=content,
                message_type=message_type
            )
        """
        发送格式化的通知消息

        Args:
            message: NotificationMessage对象

        Returns:
            是否发送成功
        """
        emoji = self.type_emoji.get(msg.message_type, "ℹ️")

        formatted_text = f"""
{emoji} *{msg.title}*

{msg.content}

⏰ {msg.timestamp}
"""
        return self.send_message(formatted_text)

    def send_trade_notification(
        self,
        action: str,
        symbol: str,
        side: str,
        price: float,
        quantity: float,
        leverage: int,
        stop_loss: float,
        pnl: Optional[float] = None
    ) -> bool:
        """
        发送交易通知

        Args:
            action: 操作类型 (开仓/平仓)
            symbol: 交易对
            side: 方向 (多/空)
            price: 价格
            quantity: 数量
            leverage: 杠杆
            stop_loss: 止损价格
            pnl: 盈亏(平仓时)

        Returns:
            是否发送成功
        """
        emoji = "🟢" if side == "long" else "🔴"
        pnl_text = ""

        if pnl is not None:
            pnl_emoji = "📈" if pnl > 0 else "📉"
            pnl_text = f"\n{pnl_emoji} *盈亏:* {pnl:+.2f} USDT"

        text = f"""
{emoji} *{action}通知*

📊 *交易对:* {symbol}
📈 *方向:* {side}
💵 *价格:* {price:,.2f}
📦 *数量:* {quantity:.6f}
⚡ *杠杆:* {leverage}x
🛡️ *止损:* {stop_loss:,.2f}{pnl_text}

⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
        return self.send_message(text)

    def send_risk_alert(
        self,
        alert_type: str,
        message: str,
        details: Optional[Dict] = None
    ) -> bool:
        """
        发送风控警报

        Args:
            alert_type: 警报类型 (止损/爆仓/回撤等)
            message: 警报消息
            details: 详细信息

        Returns:
            是否发送成功
        """
        details_text = ""
        if details:
            for key, value in details.items():
                details_text += f"\n• {key}: {value}"

        text = f"""
🚨 *风控警报: {alert_type}*

{message}{details_text}

⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
        return self.send_message(text)

    def send_daily_report(
        self,
        date: str,
        total_trades: int,
        win_count: int,
        loss_count: int,
        total_pnl: float,
        win_rate: float,
        balance: float
    ) -> bool:
        """
        发送日报

        Args:
            date: 日期
            total_trades: 总交易数
            win_count: 盈利次数
            loss_count: 亏损次数
            total_pnl: 总盈亏
            win_rate: 胜率
            balance: 当前余额

        Returns:
            是否发送成功
        """
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"

        text = f"""
📊 *交易日报 - {date}*

💰 *总盈亏:* {pnl_emoji} {total_pnl:+.2f} USDT
📈 *胜率:* {win_rate:.1f}%
🔄 *交易次数:* {total_trades} ({win_count}胜/{loss_count}负)
💵 *当前余额:* {balance:,.2f} USDT

⏰ {datetime.now().strftime("%H:%M:%S")}
"""
        return self.send_message(text)

    def send_system_status(
        self,
        status: str,
        uptime: str,
        last_trade: str,
        errors: Optional[list] = None
    ) -> bool:
        """
        发送系统状态

        Args:
            status: 系统状态 (正常/警告/错误)
            uptime: 运行时间
            last_trade: 最后交易时间
            errors: 错误列表

        Returns:
            是否发送成功
        """
        status_emoji = {
            "正常": "🟢",
            "警告": "🟡",
            "错误": "🔴"
        }.get(status, "⚪")

        errors_text = ""
        if errors:
            errors_text = "\n\n❌ *近期错误:*\n"
            for error in errors[-3:]:  # 只显示最近3个
                errors_text += f"• {error}\n"

        text = f"""
🤖 *系统状态*

{status_emoji} *状态:* {status}
⏱️ *运行时间:* {uptime}
🔄 *最后交易:* {last_trade}{errors_text}

⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
        return self.send_message(text)

    def test_connection(self) -> bool:
        """
        测试Telegram连接

        Returns:
            连接是否成功
        """
        if not self.enabled:
            print("[Telegram] 通知未启用，请配置bot_token和chat_id")
            return False

        url = f"{self.base_url}/getMe"

        try:
            response = self.session.get(url, timeout=10)
            result = response.json()

            if result.get("ok"):
                bot_info = result.get("result", {})
                print(f"[Telegram] 连接成功!")
                print(f"  Bot名称: {bot_info.get('first_name')}")
                print(f"  Bot用户名: @{bot_info.get('username')}")
                return True
            else:
                print(f"[Telegram] 连接失败: {result.get('description')}")
                return False

        except Exception as e:
            print(f"[Telegram] 连接异常: {e}")
            return False


def create_notifier_from_config(config_path: str = "config/settings.yaml") -> TelegramNotifier:
    """
    从配置文件创建通知器

    Args:
        config_path: 配置文件路径

    Returns:
        TelegramNotifier实例
    """
    import yaml

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        telegram_config = config.get("notifications", {}).get("telegram", {})

        return TelegramNotifier(
            bot_token=telegram_config.get("bot_token", ""),
            chat_id=telegram_config.get("chat_id", ""),
            enabled=telegram_config.get("enabled", False)
        )

    except Exception as e:
        print(f"[Telegram] 从配置创建失败: {e}")
        return TelegramNotifier(enabled=False)


# 测试代码
if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("=" * 60)
    print("Telegram通知器测试")
    print("=" * 60)

    # 从配置创建
    notifier = create_notifier_from_config()

    # 测试连接
    print("\n1. 测试连接...")
    if notifier.test_connection():
        print("\n2. 发送测试消息...")
        notifier.send_message("🤖 BTC交易Agent已启动！")

        print("\n3. 发送交易通知...")
        notifier.send_trade_notification(
            action="开仓",
            symbol="BTC/USDT",
            side="long",
            price=71300.5,
            quantity=0.01,
            leverage=10,
            stop_loss=69650.0
        )

        print("\n✅ 测试完成!")
    else:
        print("\n❌ 连接失败，请检查配置")
        print("\n获取Chat ID方法:")
        print("1. 给Bot发送消息")
        print("2. 访问: https://api.telegram.org/bot<你的Token>/getUpdates")
        print("3. 在返回的JSON中查找chat.id")
