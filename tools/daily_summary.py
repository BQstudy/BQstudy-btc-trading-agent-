#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易决策汇总推送脚本
每6小时执行一次，推送之前6小时的交易决策汇总
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml


def load_config():
    """加载配置"""
    config_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_recent_decisions(hours=6):
    """获取最近N小时的交易决策"""
    log_dir = Path("logs")

    decisions = []
    cutoff_time = datetime.now() - timedelta(hours=hours)

    # 遍历所有日志文件
    for phase in ["cot_perception", "cot_judgment", "cot_decision"]:
        phase_dir = log_dir / phase
        if not phase_dir.exists():
            continue

        for log_file in phase_dir.glob("*.jsonl"):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            # 解析时间
                            timestamp = entry.get("timestamp", "")
                            if timestamp:
                                try:
                                    # 尝试解析ISO格式
                                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                                    dt = dt.replace(tzinfo=None)  # 转为本地时间
                                except:
                                    continue

                                if dt >= cutoff_time:
                                    decisions.append({
                                        "time": dt.strftime("%H:%M"),
                                        "phase": phase,
                                        "entry": entry
                                    })
                        except:
                            continue
            except:
                continue

    return decisions


def analyze_decisions(decisions):
    """分析决策数据"""
    # 按时间排序
    decisions.sort(key=lambda x: x["time"])

    # 统计
    stats = {
        "total_cycles": 0,
        "trades": 0,
        "no_trades": 0,
        "trade_details": [],
    }

    # 按周期分组
    cycles = defaultdict(dict)

    for d in decisions:
        time = d["time"]
        phase = d["phase"]
        entry = d["entry"]

        # 提取小时
        hour = time.split(":")[0]

        if phase == "cot_decision" and "decision" in entry:
            # 这是决策阶段的日志
            decision = entry.get("decision", {})

            # 提取决策信息
            action = decision.get("action", "unknown")
            bias = decision.get("bias", "unknown")
            confidence = decision.get("confidence", 0)
            reason = decision.get("reason_for_no_trade", "")

            # 判断是否开单
            if action in ["long", "short"]:
                stats["trades"] += 1
                stats["trade_details"].append({
                    "time": time,
                    "action": action,
                    "bias": bias,
                    "confidence": confidence,
                    "entry_zone": decision.get("entry_zone", []),
                    "stop_loss": decision.get("stop_loss", ""),
                    "position_size": decision.get("position_size_pct", 0),
                })
                stats["total_cycles"] += 1
            elif action == "no_trade":
                stats["no_trades"] += 1
                stats["total_cycles"] += 1

    return stats


def build_summary_message(stats, hours=6):
    """构建汇总消息"""
    now = datetime.now()
    time_range = f"{now.strftime('%H:%M')}前{hours}小时"

    # 标题
    message = f"""
📊 *交易决策汇总*

⏰ 时间范围: {time_range}
📈 周期总数: {stats['total_cycles']}
🟢 开单次数: {stats['trades']}
🔴 不交易次数: {stats['no_trades']}

"""

    # 开单详情
    if stats["trade_details"]:
        message += "📌 *开单记录:*\n"
        for i, trade in enumerate(stats["trade_details"], 1):
            emoji = "🟢" if trade["action"] == "long" else "🔴"
            entry_zone = trade.get("entry_zone", [])
            if entry_zone:
                entry_text = f"{entry_zone[0]:.0f}-{entry_zone[-1]:.0f}" if len(entry_zone) > 1 else f"{entry_zone[0]:.0f}"
            else:
                entry_text = "市价"

            message += f"""
{i}. {emoji} {trade['time']} | {trade['action'].upper()}
   方向: {trade['bias']} | 置信度: {trade['confidence']:.0%}
   入场: {entry_text} | 止损: {trade['stop_loss']:.0f} | 仓位: {trade['position_size']}%
"""
    else:
        message += "📌 *开单记录:* 无\n"

    # 不交易详情（只显示前3个）
    if stats["no_trades"] > 0:
        # 这里可以进一步提取不交易的原因
        message += f"\n📌 *不交易:* 共{stats['no_trades']}次\n"

    message += f"\n⏰ {now.strftime('%Y-%m-%d %H:%M')}"

    return message


def send_notification(message):
    """发送Telegram通知"""
    try:
        from utils.telegram_notifier import TelegramNotifier

        config = load_config()
        telegram_config = config.get("notifications", {}).get("telegram", {})

        notifier = TelegramNotifier(
            bot_token=telegram_config.get("bot_token"),
            chat_id=telegram_config.get("chat_id"),
            enabled=True
        )

        # 简化消息发送
        return notifier.send_message(message)

    except Exception as e:
        print(f"发送通知失败: {e}")
        return False


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="交易决策汇总")
    parser.add_argument("--hours", type=int, default=6, help="汇总小时数")
    parser.add_argument("--dry-run", action="store_true", help="仅显示不发送")

    args = parser.parse_args()

    print(f"[{datetime.now()}] 开始汇总最近{args.hours}小时的交易决策...")

    # 获取决策
    decisions = get_recent_decisions(hours=args.hours)
    print(f"获取到 {len(decisions)} 条日志记录")

    # 分析
    stats = analyze_decisions(decisions)

    # 构建消息
    message = build_summary_message(stats, hours=args.hours)

    print("\n" + "=" * 50)
    print(message)
    print("=" * 50)

    if args.dry_run:
        print("\n[测试模式] 不发送通知")
        return

    # 发送
    print("\n发送通知...")
    if send_notification(message):
        print("✅ 通知发送成功")
    else:
        print("❌ 通知发送失败")


if __name__ == "__main__":
    main()
