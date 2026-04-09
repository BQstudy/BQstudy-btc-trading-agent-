#!/usr/bin/env python3
"""
监控Agent V2 - 简化版
不依赖Docker CLI，只监控和告警，不执行重启
"""

import os
import sys
import time
import json
import logging
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
import threading

# 设置路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import yaml


@dataclass
class MonitorConfig:
    """监控配置"""
    check_interval: int = 60
    health_endpoint: str = "http://btc-agent:8080/health"
    notify_on_error: bool = True
    notify_on_status: bool = False
    log_level: str = "INFO"
    restart_threshold: int = 3  # 连续失败多少次后建议重启


class HealthChecker:
    """健康检查器"""

    def __init__(self, config: MonitorConfig):
        self.config = config
        self.consecutive_failures = 0

    def check_health_endpoint(self) -> Dict:
        """检查健康端点"""
        try:
            resp = requests.get(
                self.config.health_endpoint,
                timeout=10
            )
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    self.consecutive_failures = 0  # 重置失败计数
                    return {
                        "ok": True,
                        "status_code": resp.status_code,
                        "data": data,
                        "agent_status": data.get("status", "unknown"),
                        "cycles_completed": data.get("cycles_completed", 0),
                        "checks": data.get("checks", {})
                    }
                except:
                    return {"ok": True, "status_code": resp.status_code}
            return {
                "ok": False,
                "error": f"HTTP {resp.status_code}",
                "status_code": resp.status_code
            }
        except requests.exceptions.Timeout:
            self.consecutive_failures += 1
            return {"ok": False, "error": "请求超时", "consecutive_failures": self.consecutive_failures}
        except requests.exceptions.ConnectionError:
            self.consecutive_failures += 1
            return {"ok": False, "error": "连接失败", "consecutive_failures": self.consecutive_failures}
        except Exception as e:
            self.consecutive_failures += 1
            return {"ok": False, "error": str(e), "consecutive_failures": self.consecutive_failures}


class AlertNotifier:
    """告警通知器"""

    def __init__(self, config: MonitorConfig):
        self.config = config
        self.notifier = None
        self._init_notifier()

    def _init_notifier(self):
        """初始化Telegram通知器"""
        try:
            from utils.telegram_notifier import TelegramNotifier

            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
            chat_id = os.environ.get("TELEGRAM_CHAT_ID")

            if bot_token and chat_id:
                self.notifier = TelegramNotifier(
                    bot_token=bot_token,
                    chat_id=chat_id,
                    enabled=True
                )
        except Exception as e:
            print(f"[Monitor] 通知器初始化失败: {e}")

    def send_alert_notification(self, check_results: Dict, needs_restart: bool = False):
        """发送告警通知"""
        if not self.notifier or not self.config.notify_on_error:
            return

        health = check_results.get("health_endpoint", {})
        failures = health.get("consecutive_failures", 0)

        if needs_restart:
            message = f"""
🚨 *【紧急】交易Agent故障 - 建议重启*

⏰ 时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

❌ 检查失败:
• 健康端点: {health.get('error', '未知')}
• 连续失败: {failures} 次

⚠️ 建议执行重启:
```
cd /opt/btc-agent
docker compose -f deploy/docker-compose.yml restart btc-agent
```
"""
        else:
            message = f"""
⚠️ *交易Agent异常*

⏰ 时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

📊 状态:
• 健康端点: {health.get('error', '未知')}
• 连续失败: {failures} 次

正在持续监控中...
"""

        self.notifier.send_message(message)

    def send_recovery_notification(self, check_results: Dict):
        """发送恢复通知"""
        if not self.notifier:
            return

        health = check_results.get("health_endpoint", {})
        data = health.get("data", {})

        message = f"""
✅ *交易Agent恢复正常*

⏰ 时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

📊 当前状态:
• Agent状态: {data.get('status', 'unknown')}
• 完成周期: {data.get('cycles_completed', 0)}
• 运行时间: {data.get('uptime_seconds', 0)} 秒
"""
        self.notifier.send_message(message)

    def send_startup_notification(self):
        """发送启动通知"""
        if not self.notifier:
            return

        message = f"""
🤖 *监控Agent V2已启动*

⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

配置:
• 检查间隔: {self.config.check_interval}秒
• 健康端点: {self.config.health_endpoint}
• 告警阈值: {self.config.restart_threshold}次连续失败

注意: 此版本不自动重启，仅监控和告警
"""
        self.notifier.send_message(message)


class MonitorAgentV2:
    """监控Agent V2 - 简化版"""

    def __init__(self, config_path: str = "monitor/monitor_config.yaml"):
        self.config = self._load_config(config_path)
        self.health_checker = HealthChecker(self.config)
        self.notifier = AlertNotifier(self.config)
        self.running = False
        self.was_healthy = True
        self.status_history: List[Dict] = []
        self._lock = threading.Lock()
        self._setup_logging()

    def _load_config(self, path: str) -> MonitorConfig:
        """加载配置"""
        config_file = PROJECT_ROOT / path

        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    data = yaml.safe_load(f)
                    if data:
                        return MonitorConfig(**data)
            except Exception as e:
                print(f"[Monitor] 配置加载失败: {e}")

        return MonitorConfig()

    def _setup_logging(self):
        """设置日志"""
        log_dir = PROJECT_ROOT / "logs"
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "monitor.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("MonitorAgentV2")

    def run_check(self) -> Dict:
        """执行一次完整检查"""
        check_time = datetime.now()

        # 执行健康检查
        health = self.health_checker.check_health_endpoint()

        result = {
            "time": check_time.isoformat(),
            "overall": "healthy" if health.get("ok") else "unhealthy",
            "health_endpoint": health,
        }

        # 状态变化检测
        is_healthy = health.get("ok", False)

        if is_healthy and not self.was_healthy:
            # 从异常恢复
            self.logger.info("✅ 交易Agent恢复正常")
            self.notifier.send_recovery_notification(result)

        elif not is_healthy:
            failures = health.get("consecutive_failures", 0)
            self.logger.warning(f"❌ 健康检查失败，连续失败: {failures}次")

            # 达到阈值，发送告警
            if failures >= self.config.restart_threshold:
                needs_restart = failures >= self.config.restart_threshold
                self.notifier.send_alert_notification(result, needs_restart=needs_restart)
                self.logger.error(f"🚨 连续失败{failures}次，建议人工介入")

        self.was_healthy = is_healthy

        # 保存历史
        with self._lock:
            self.status_history.append(result)
            self.status_history = self.status_history[-100:]

        # 打印状态
        status_icon = "✅" if is_healthy else "❌"
        self.logger.info(f"{status_icon} 检查完成: {result['overall']}")

        return result

    def run_continuous(self):
        """持续运行"""
        self.running = True

        self.logger.info(f"[{datetime.now()}] 监控Agent V2启动")
        self.logger.info(f"检查间隔: {self.config.check_interval}秒")

        # 发送启动通知
        self.notifier.send_startup_notification()

        # 立即执行一次检查
        self.run_check()

        while self.running:
            try:
                time.sleep(self.config.check_interval)
                if self.running:
                    self.run_check()

            except KeyboardInterrupt:
                self.logger.info("收到停止信号")
                break
            except Exception as e:
                self.logger.error(f"检查异常: {e}")
                time.sleep(10)

        self.logger.info("监控Agent V2已停止")

    def stop(self):
        """停止"""
        self.running = False


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="BTC交易Agent监控 V2 (简化版)")
    parser.add_argument("--config", default="monitor/monitor_config.yaml")
    parser.add_argument("--check-once", action="store_true")
    parser.add_argument("--status", action="store_true")

    args = parser.parse_args()

    agent = MonitorAgentV2(args.config)

    if args.check_once:
        result = agent.run_check()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["overall"] == "healthy" else 1)

    elif args.status:
        with agent._lock:
            for r in agent.status_history[-10:]:
                print(f"{r['time']}: {r['overall']}")
        sys.exit(0)

    else:
        agent.run_continuous()


if __name__ == "__main__":
    main()
