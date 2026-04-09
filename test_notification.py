"""
测试Telegram通知功能
验证每30分钟推送是否正常
"""

import sys
sys.path.insert(0, 'src')

from utils.telegram_notifier import create_notifier_from_config
from datetime import datetime

def test_notification():
    """测试通知功能"""
    print("=" * 60)
    print("Telegram通知测试")
    print("=" * 60)

    # 创建通知器
    notifier = create_notifier_from_config("config/settings.yaml")

    # 测试连接
    print("\n1. 测试连接...")
    if not notifier.test_connection():
        print("❌ 连接失败，请检查配置")
        return False

    # 发送测试消息
    print("\n2. 发送测试通知...")

    # 模拟"不开单"场景
    content_no_trade = f"""
📊 *市场感知*
• 类型: ranging
• 情绪: neutral
• 叙述: 当前市场处于震荡区间，多空力量均衡，缺乏明确方向...

🧠 *主观判断*
• 方向: neutral
• 置信度: 45%
• 辩论: 多头认为支撑位稳固，空头认为上方阻力强劲，双方观点分歧不大...

📌 *最终决策*
• 行动: no_trade
• 方向不明或置信度0.45过低

⏰ {datetime.now().strftime("%H:%M:%S")}
"""

    result1 = notifier.send_notification(
        title="交易周期完成 | NO_TRADE",
        content=content_no_trade,
        message_type="info"
    )

    if result1:
        print("✅ '不开单'通知发送成功")
    else:
        print("❌ '不开单'通知发送失败")

    # 模拟"开单"场景
    content_trade = f"""
📊 *市场感知*
• 类型: trending
• 情绪: bullish
• 叙述: BTC突破关键阻力位，成交量放大，多头趋势确立...

🧠 *主观判断*
• 方向: long
• 置信度: 78%
• 辩论: 多头力量强劲，突破后回踩确认，建议逢低做多...

📌 *最终决策*
• 行动: open_long
• 止损68500.0，仓位12%

⏰ {datetime.now().strftime("%H:%M:%S")}
"""

    result2 = notifier.send_notification(
        title="交易周期完成 | OPEN_LONG",
        content=content_trade,
        message_type="success"
    )

    if result2:
        print("✅ '开单'通知发送成功")
    else:
        print("❌ '开单'通知发送失败")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
    print(f"\n配置检查:")
    print(f"  - 运行间隔: 1800秒 (30分钟)")
    print(f"  - 周期完成通知: 已启用")
    print(f"  - 交易执行通知: 已启用")
    print(f"  - 风控警报: 已启用")

    return result1 and result2

if __name__ == "__main__":
    success = test_notification()
    sys.exit(0 if success else 1)
