#!/usr/bin/env python3
"""
Agent监控脚本
用于检查Agent运行状态和发送心跳通知
"""

import requests
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.telegram_notifier import TelegramNotifier, create_notifier_from_config


def check_health(host="localhost", port=8080):
    """检查Agent健康状态"""
    try:
        response = requests.get(f"http://{host}:{port}/health", timeout=5)
        return response.status_code == 200
    except Exception as e:
        return False


def check_docker_status():
    """检查Docker容器状态"""
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=btc-trading-agent", "--format", "{{.Status}}"],
            capture_output=True, text=True, timeout=10
        )
        status = result.stdout.strip()
        return status if status else "未运行"
    except Exception as e:
        return f"检查失败: {e}"


def send_status_report(notifier: TelegramNotifier):
    """发送状态报告"""
    health_ok = check_health()
    docker_status = check_docker_status()

    status_emoji = "✅" if health_ok else "❌"
    docker_emoji = "🟢" if "Up" in docker_status else "🔴"

    message = f"""
{status_emoji} *Agent状态报告*

🕐 检查时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{docker_emoji} Docker状态: {docker_status}
💓 健康检查: {'正常' if health_ok else '异常'}

📊 监控说明:
• 每5分钟运行一次交易分析
• 每次周期完成会发送通知
• 如未收到通知超过10分钟，请检查Agent状态
"""

    notifier.send_message(message)
    print(f"状态报告已发送: {datetime.now()}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Agent监控工具")
    parser.add_argument("--config", default="config/settings.yaml", help="配置文件路径")
    parser.add_argument("--check", action="store_true", help="检查状态并发送报告")
    parser.add_argument("--health", action="store_true", help="仅检查健康状态")

    args = parser.parse_args()

    if args.health:
        ok = check_health()
        print(f"健康检查: {'正常' if ok else '异常'}")
        sys.exit(0 if ok else 1)

    if args.check:
        # 创建通知器
        try:
            notifier = create_notifier_from_config(args.config)
            send_status_report(notifier)
        except Exception as e:
            print(f"发送报告失败: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
