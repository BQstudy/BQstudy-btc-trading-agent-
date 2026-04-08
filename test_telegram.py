"""
Telegram通知测试脚本
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import yaml

print("=" * 60)
print("Telegram通知测试")
print("=" * 60)

# 加载配置
with open('config/settings.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

telegram_config = config.get('notifications', {}).get('telegram', {})

# 检查配置
print("\n1. 检查Telegram配置:")
print(f"   启用状态: {telegram_config.get('enabled', False)}")

bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', telegram_config.get('bot_token', ''))
chat_id = os.environ.get('TELEGRAM_CHAT_ID', telegram_config.get('chat_id', ''))

print(f"   Bot Token: {'已设置' if bot_token else '未设置'}")
print(f"   Chat ID: {'已设置' if chat_id else '未设置'}")

if not bot_token or not chat_id:
    print("\n" + "=" * 60)
    print("配置指南")
    print("=" * 60)
    print("""
获取Bot Token:
1. 在Telegram中搜索 @BotFather
2. 发送 /newbot 创建新机器人
3. 复制Bot Token

获取Chat ID:
1. 搜索你的机器人并发送消息
2. 访问: https://api.telegram.org/bot<TOKEN>/getUpdates
3. 找到 "chat":{"id":xxxxxx} 中的数字

设置方式:
- 环境变量: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
- 或直接编辑 config/settings.yaml
""")
    sys.exit(1)

# 创建通知器
from src.utils.telegram_notifier import TelegramNotifier

notifier = TelegramNotifier(
    bot_token=bot_token,
    chat_id=chat_id,
    enabled=True
)

# 测试连接
print("\n2. 测试Telegram连接...")
if notifier.test_connection():
    print("\n3. 发送测试消息...")

    # 发送测试消息
    notifier.send_message("🤖 BTC交易Agent测试消息")

    # 发送交易通知
    notifier.send_trade_notification(
        action="测试开仓",
        symbol="BTC/USDT:USDT",
        side="long",
        price=71000.0,
        quantity=0.01,
        leverage=10,
        stop_loss=69650.0
    )

    # 发送风控警报测试
    notifier.send_risk_alert(
        alert_type="测试警报",
        message="这是一条测试警报",
        details={"测试参数": "正常", "账户余额": "10000 USDT"}
    )

    print("\n" + "=" * 60)
    print("✅ Telegram通知测试完成!")
    print("=" * 60)
else:
    print("\n❌ 连接失败，请检查Token和Chat ID")
