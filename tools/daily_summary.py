#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易决策汇总推送脚本
每6小时执行一次，推送之前6小时的交易决策汇总
包含：市场分析思路、交易理由、决策详情
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


def get_recent_cycles(hours=6):
    """获取最近N小时的完整交易周期数据"""
    log_dir = Path("logs")

    cycles = defaultdict(dict)  # {时间周期: {phase: entry}}
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

                            # 解析时间，提取小时作为周期标识
                            timestamp = entry.get("timestamp", "")
                            if timestamp:
                                try:
                                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                                    dt = dt.replace(tzinfo=None)
                                except:
                                    continue

                                if dt >= cutoff_time:
                                    # 使用小时+分钟作为周期标识
                                    cycle_key = dt.strftime("%Y-%m-%d %H:%M")

                                    # 存储各阶段数据
                                    if phase == "cot_perception":
                                        cycles[cycle_key]["perception"] = {
                                            "time": dt.strftime("%H:%M"),
                                            "market_narrative": entry.get("chain_of_thought", "")[:500],
                                            "sentiment": entry.get("decision", {}).get("sentiment", "unknown"),
                                            "market_type": entry.get("decision", {}).get("market_type", "unknown"),
                                        }
                                    elif phase == "cot_judgment":
                                        cycles[cycle_key]["judgment"] = {
                                            "time": dt.strftime("%H:%M"),
                                            "analysis": entry.get("chain_of_thought", "")[:800],
                                            "bias": entry.get("decision", {}).get("bias", "neutral"),
                                            "confidence": entry.get("decision", {}).get("confidence", 0),
                                        }
                                    elif phase == "cot_decision":
                                        cycles[cycle_key]["decision"] = {
                                            "time": dt.strftime("%H:%M"),
                                            "action": entry.get("decision", {}).get("action", "unknown"),
                                            "reason_for_no_trade": entry.get("decision", {}).get("reason_for_no_trade", ""),
                                            "entry_zone": entry.get("decision", {}).get("entry_zone", []),
                                            "stop_loss": entry.get("decision", {}).get("stop_loss", 0),
                                            "position_size_pct": entry.get("decision", {}).get("position_size_pct", 0),
                                        }

                        except:
                            continue
            except:
                continue

    return cycles


def analyze_cycles(cycles):
    """分析所有周期数据"""
    result = {
        "total_cycles": 0,
        "trades": 0,
        "no_trades": 0,
        "trade_records": [],  # 开单记录
        "no_trade_records": [],  # 不交易记录
    }

    # 按时间排序
    sorted_cycles = sorted(cycles.items(), key=lambda x: x[0])

    for cycle_time, data in sorted_cycles:
        decision = data.get("decision", {})
        if not decision:
            continue

        action = decision.get("action", "unknown")
        perception = data.get("perception", {})
        judgment = data.get("judgment", {})

        # 构建完整记录
        record = {
            "time": decision.get("time", cycle_time.split()[-1]),
            "action": action,
            # 市场感知
            "market_type": perception.get("market_type", "unknown"),
            "sentiment": perception.get("sentiment", "unknown"),
            "market_narrative": perception.get("market_narrative", ""),
            # 主观判断
            "bias": judgment.get("bias", "neutral"),
            "confidence": judgment.get("confidence", 0),
            "analysis": judgment.get("analysis", ""),
            # 决策
            "entry_zone": decision.get("entry_zone", []),
            "stop_loss": decision.get("stop_loss", 0),
            "position_size": decision.get("position_size_pct", 0),
            "reason": decision.get("reason_for_no_trade", ""),
        }

        result["total_cycles"] += 1

        if action in ["long", "short"]:
            result["trades"] += 1
            result["trade_records"].append(record)
        elif action == "no_trade":
            result["no_trades"] += 1
            result["no_trade_records"].append(record)

    return result


def build_summary_message(data, hours=6):
    """构建汇总消息"""
    now = datetime.now()
    time_range = f"{now.strftime('%H:%M')}前{hours}小时"

    message = f"""
📊 *交易决策汇总*

⏰ 时间范围: {time_range}
📈 周期总数: {data['total_cycles']}
🟢 开单次数: {data['trades']}
🔴 不交易次数: {data['no_trades']}

"""

    # ==================== 开单详情 ====================
    if data["trade_records"]:
        message += "═" * 24 + "\n"
        message += "📌 *开单记录*\n"
        message += "═" * 24 + "\n\n"

        for i, trade in enumerate(data["trade_records"], 1):
            emoji = "🟢" if trade["action"] == "long" else "🔴"

            # 入场价
            entry_zone = trade.get("entry_zone", [])
            if entry_zone:
                entry_text = f"{entry_zone[0]:,.0f}-{entry_zone[-1]:,.0f}"
            else:
                entry_text = "市价"

            # 交易理由
            if trade.get("analysis"):
                # 提取分析思路的关键部分
                analysis = trade["analysis"]
                # 取前200字符作为分析摘要
                if len(analysis) > 200:
                    analysis = analysis[:200] + "..."
            else:
                analysis = "无分析记录"

            # 市场叙事
            narrative = trade.get("market_narrative", "")
            if narrative:
                if len(narrative) > 150:
                    narrative = narrative[:150] + "..."
            else:
                narrative = "无市场叙述"

            message += f"""
{i}. {emoji} *{trade['time']}* | {trade['action'].upper()}

📊 *市场分析*
{narrative}

🧠 *判断思路*
{analysis}

📈 *决策参数*
• 方向: {trade['bias']} | 置信度: {trade['confidence']:.0%}
• 入场: {entry_text} | 止损: {trade['stop_loss']:,.0f}
• 仓位: {trade['position_size']}%

"""

    # ==================== 不交易详情 ====================
    if data["no_trade_records"]:
        message += "═" * 24 + "\n"
        message += "📌 *不交易记录*\n"
        message += "═" * 24 + "\n\n"

        # 只显示最近3个不交易记录
        for i, record in enumerate(data["no_trade_records"][-3:], 1):
            # 市场情况
            market_info = f"{record.get('market_type', 'unknown')}/{record.get('sentiment', 'unknown')}"

            # 不交易理由
            reason = record.get("reason", "无明确理由")
            if record.get("analysis"):
                # 提取不交易的分析思路
                analysis = record["analysis"]
                if len(analysis) > 150:
                    analysis = analysis[:150] + "..."
                reason = f"{reason}\n{analysis}" if reason else analysis

            message += f"""
{i}. *{record['time']}* | {market_info}

📌 原因: {reason}

"""

        if len(data["no_trade_records"]) > 3:
            message += f"\n... 还有 {len(data['no_trade_records']) - 3} 次不交易\n"

    if not data["trade_records"] and not data["no_trade_records"]:
        message += "📌 本时段无交易记录\n"

    message += f"""
⏰ 汇总时间: {now.strftime('%Y-%m-%d %H:%M')}
"""

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

    # 获取周期数据
    cycles = get_recent_cycles(hours=args.hours)
    print(f"获取到 {len(cycles)} 个交易周期")

    # 分析数据
    data = analyze_cycles(cycles)
    print(f"周期总数: {data['total_cycles']}")
    print(f"开单次数: {data['trades']}")
    print(f"不交易次数: {data['no_trades']}")

    # 构建消息
    message = build_summary_message(data, hours=args.hours)

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
