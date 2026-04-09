#!/usr/bin/env python3
"""
监控Agent - Layer 2监控层
独立进程，监控交易Agent的健康状态，自动修复

职责：
1. 检查交易Agent的健康端点
2. 检查Docker容器状态
3. 检查日志活动
4. 自动重启故障服务
5. 发送告警通知

限制：
- 不能修改交易Agent代码
- 不能执行交易操作
- 重启次数超限后必须人工介入
"""

import os
import sys
import time
import json
import logging
import subprocess
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


# ================= 配置类 =================

@dataclass
class MonitorConfig:
    """监控配置"""
    check_interval: int = 60
    health_endpoint: str = "http://btc-agent:8080/health"
    docker_container: str = "btc-trading-agent"
    deploy_path: str = "/opt/btc-agent"
    auto_restart: bool = True
    max_restart_attempts: int = 3
    restart_cooldown: int = 300
    notify_on_restart: bool = True
    notify_on_error: bool = True
    notify_on_status: bool = False
    log_level: str = "INFO"
    log_file: str = "logs/monitor.log"
    thresholds: Dict = field(default_factory=lambda: {
        "max_cycle_gap_minutes": 70,
        "max_error_count": 5,
        "max_memory_percent": 80,
        "max_restarts_per_hour": 3
    })


# ================= 健康检查器 =================

class HealthChecker:
    """健康检查器"""

    def __init__(self, config: MonitorConfig):
        self.config = config

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
                    return {
                        "ok": True,
                        "status_code": resp.status_code,
                        "data": data,
                        "agent_status": data.get("status", "unknown"),
                        "cycles_completed": data.get("cycles_completed", 0)
                    }
                except:
                    return {"ok": True, "status_code": resp.status_code}
            return {
                "ok": False,
                "error": f"HTTP {resp.status_code}",
                "status_code": resp.status_code
            }
        except requests.exceptions.Timeout:
            return {"ok": False, "error": "请求超时"}
        except requests.exceptions.ConnectionError:
            return {"ok": False, "error": "连接失败"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def check_docker_status(self) -> Dict:
        """检查Docker容器状态"""
        try:
            # 使用docker inspect获取详细状态
            result = subprocess.run(
                [
                    "docker", "inspect",
                    "--format",
                    "{{.State.Status}}|{{.State.Health.Status}}|{{.State.Running}}|{{.State.RestartCount}}|{{.StartedAt}}|{{.Health.FailingStreak}}",
                    self.config.docker_container
                ],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                parts = result.stdout.strip().split("|")
                if len(parts) >= 4:
                    return {
                        "ok": parts[0] == "running",
                        "status": parts[0],
                        "health": parts[1] if parts[1] != "<nil>" else "unknown",
                        "running": parts[2] == "true",
                        "restarts": int(parts[3]) if parts[3].isdigit() else 0,
                        "started_at": parts[4] if len(parts) > 4 else None,
                        "failing_streak": int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 0
                    }
            return {"ok": False, "error": "container not found"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "docker命令超时"}
        except FileNotFoundError:
            return {"ok": False, "error": "docker未安装"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def check_log_activity(self) -> Dict:
        """检查日志活动"""
        log_dir = Path(self.config.deploy_path) / "logs" / "cot_perception"

        try:
            if not log_dir.exists():
                return {"ok": False, "error": "日志目录不存在"}

            # 获取最新的日志文件
            log_files = sorted([
                f for f in os.listdir(str(log_dir))
                if f.endswith('.jsonl')
            ])

            if not log_files:
                return {"ok": False, "error": "没有日志文件"}

            # 检查最后修改时间
            latest = log_dir / log_files[-1]
            mtime = datetime.fromtimestamp(os.path.getmtime(str(latest)))
            now = datetime.now()
            gap_minutes = (now - mtime).total_seconds() / 60

            # 如果超过阈值，认为异常
            threshold = self.config.thresholds["max_cycle_gap_minutes"]
            if gap_minutes > threshold:
                return {
                    "ok": False,
                    "error": f"没有新日志已 {int(gap_minutes)} 分钟 (阈值: {threshold})",
                    "last_log_time": mtime.isoformat(),
                    "gap_minutes": int(gap_minutes),
                    "latest_file": log_files[-1]
                }

            return {
                "ok": True,
                "last_log_time": mtime.isoformat(),
                "gap_minutes": int(gap_minutes),
                "latest_file": log_files[-1]
            }

        except PermissionError:
            return {"ok": False, "error": "没有日志目录权限"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def check_disk_space(self) -> Dict:
        """检查磁盘空间"""
        try:
            result = subprocess.run(
                ["df", "-h", self.config.deploy_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 2:
                    parts = lines[1].split()
                    return {
                        "ok": True,
                        "total": parts[1],
                        "used": parts[2],
                        "available": parts[3],
                        "percent": parts[4]
                    }
            return {"ok": False, "error": "无法获取磁盘信息"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ================= 自动修复器 =================

class AutoFixer:
    """自动修复器"""

    def __init__(self, config: MonitorConfig):
        self.config = config
        self.restart_history: List[datetime] = []
        self._lock = threading.Lock()

    def can_restart(self) -> bool:
        """检查是否可以重启"""
        with self._lock:
            # 清理过期的重启记录
            cutoff = datetime.now() - timedelta(seconds=self.config.restart_cooldown)
            self.restart_history = [t for t in self.restart_history if t > cutoff]

            return len(self.restart_history) < self.config.max_restart_attempts

    def get_restart_count_last_hour(self) -> int:
        """获取最近1小时的重启次数"""
        with self._lock:
            hour_ago = datetime.now() - timedelta(hours=1)
            return sum(1 for t in self.restart_history if t > hour_ago)

    def restart_service(self) -> Dict:
        """重启服务"""
        if not self.can_restart():
            return {
                "success": False,
                "error": "重启次数超限，需要人工介入"
            }

        try:
            # 记录重启时间
            with self._lock:
                self.restart_history.append(datetime.now())

            # 执行重启
            result = subprocess.run(
                ["docker", "compose", "-f", "deploy/docker-compose.yml", "restart", "btc-agent"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=self.config.deploy_path
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "output": "服务已重启",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                # 回滚记录
                with self._lock:
                    if self.restart_history:
                        self.restart_history.pop()
                return {
                    "success": False,
                    "error": result.stderr or "重启失败",
                    "output": result.stdout
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "重启命令超时"}
        except FileNotFoundError:
            return {"success": False, "error": "docker命令未找到"}
        except Exception as e:
            # 回滚记录
            with self._lock:
                if self.restart_history:
                    self.restart_history.pop()
            return {"success": False, "error": str(e)}


# ================= 通知器 =================

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

    def send_restart_notification(self, result: Dict, check_results: Dict):
        """发送重启通知"""
        if not self.notifier or not self.config.notify_on_restart:
            return

        health = check_results.get("health_endpoint", {})
        docker = check_results.get("docker", {})
        logs = check_results.get("logs", {})

        message = f"""
🔄 *监控Agent自动重启服务*

⏰ 时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

📊 检查状态:
• 健康端点: {'✅ 正常' if health.get('ok') else f'❌ {health.get("error", "未知错误")}'}
• Docker容器: {'✅ 运行中' if docker.get('ok') else f'❌ {docker.get("error", "未知错误")}'}
• 日志活动: {'✅ 正常' if logs.get('ok') else f'❌ {logs.get("error", "未知错误")}'}

🔧 执行操作: {'✅ 重启成功' if result.get('success') else f'❌ 重启失败: {result.get("error")}'}

⚠️ 最近1小时重启次数: {self._get_restart_count()}
"""

        self.notifier.send_message(message)

    def send_alert_notification(self, check_results: Dict):
        """发送告警通知（需要人工介入）"""
        if not self.notifier or not self.config.notify_on_error:
            return

        health = check_results.get("health_endpoint", {})
        docker = check_results.get("docker", {})
        logs = check_results.get("logs", {})

        message = f"""
🚨 *【紧急】交易Agent故障 - 需要人工介入*

⏰ 时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

❌ 检查失败:
• 健康端点: {health.get('error', '未知')}
• Docker: {docker.get('error', '未知')}
• 日志: {logs.get('error', '未知')}

⚠️ 自动重启次数已达上限，请立即检查！

🔍 排查命令:
```
docker ps -a
docker logs btc-trading-agent --tail=50
curl http://localhost:8080/health
```
"""

        self.notifier.send_message(message)

    def send_status_notification(self, check_results: Dict):
        """发送定期状态通知"""
        if not self.notifier or not self.config.notify_on_status:
            return

        health = check_results.get("health_endpoint", {})
        docker = check_results.get("docker", {})

        message = f"""
📊 *交易Agent状态报告*

⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

✅ 运行状态:
• 健康端点: {health.get('ok', False)}
• Docker: {docker.get('status', 'unknown')}
• Agent状态: {health.get('agent_status', 'unknown')}
• 完成周期数: {health.get('cycles_completed', 0)}
"""

        self.notifier.send_message(message)

    def send_startup_notification(self):
        """发送启动通知"""
        if not self.notifier:
            return

        message = f"""
🤖 *监控Agent已启动*

⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

开始监控交易Agent...
检查间隔: {self.config.check_interval}秒
自动重启: {'启用' if self.config.auto_restart else '禁用'}
"""
        self.notifier.send_message(message)

    def _get_restart_count(self) -> int:
        """获取重启次数（需要从AutoFixer获取）"""
        # 这里返回最近的重启次数，由MonitorAgent传入
        return 0


# ================= 主监控类 =================

class MonitorAgent:
    """监控Agent主类"""

    def __init__(self, config_path: str = "monitor/monitor_config.yaml"):
        self.config = self._load_config(config_path)
        self.health_checker = HealthChecker(self.config)
        self.auto_fixer = AutoFixer(self.config)
        self.notifier = AlertNotifier(self.config)
        self.running = False
        self.status_history: List[Dict] = []
        self._lock = threading.Lock()

        # 设置日志
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
        self.logger = logging.getLogger("MonitorAgent")

    def run_check(self) -> Dict:
        """执行一次完整检查"""
        check_time = datetime.now()

        # 执行各项检查
        health = self.health_checker.check_health_endpoint()
        docker = self.health_checker.check_docker_status()
        logs = self.health_checker.check_log_activity()
        disk = self.health_checker.check_disk_space()

        # 综合判断
        all_ok = all([
            health.get("ok"),
            docker.get("ok"),
            logs.get("ok")
        ])

        result = {
            "time": check_time.isoformat(),
            "overall": "healthy" if all_ok else "unhealthy",
            "health_endpoint": health,
            "docker": docker,
            "logs": logs,
            "disk": disk,
            "action_taken": None
        }

        # 如果异常且允许自动修复
        if not all_ok:
            restart_count = self.auto_fixer.get_restart_count_last_hour()
            max_restarts = self.config.thresholds["max_restarts_per_hour"]

            if self.config.auto_restart and restart_count < max_restarts:
                if self.auto_fixer.can_restart():
                    fix_result = self.auto_fixer.restart_service()
                    result["action_taken"] = {
                        "type": "restart",
                        "result": fix_result
                    }

                    # 发送重启通知
                    self.notifier.send_restart_notification(fix_result, result)

                    self.logger.info(f"执行自动重启: {fix_result}")
                else:
                    result["action_taken"] = {
                        "type": "alert",
                        "message": "重启次数超限，需要人工介入"
                    }

                    # 发送告警通知
                    self.notifier.send_alert_notification(result)

                    self.logger.warning("重启次数超限，发送告警")
            elif restart_count >= max_restarts:
                result["action_taken"] = {
                    "type": "alert",
                    "message": f"重启次数{restart_count}次超过阈值{max_restarts}，停止自动重启"
                }

                self.notifier.send_alert_notification(result)

                self.logger.warning(f"重启次数{restart_count}超过阈值，发送告警")

        # 保存历史
        with self._lock:
            self.status_history.append(result)
            # 只保留最近100条
            self.status_history = self.status_history[-100:]

        # 打印状态
        status_icon = "✅" if all_ok else "❌"
        self.logger.info(f"{status_icon} 检查完成: {result['overall']}")

        if result.get("action_taken"):
            self.logger.info(f"  执行操作: {result['action_taken']}")

        return result

    def run_continuous(self):
        """持续运行"""
        self.running = True

        self.logger.info(f"[{datetime.now()}] 监控Agent启动")
        self.logger.info(f"检查间隔: {self.config.check_interval}秒")
        self.logger.info(f"自动重启: {self.config.auto_restart}")

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
                time.sleep(10)  # 异常后等待10秒再重试

        self.logger.info("监控Agent已停止")

    def stop(self):
        """停止"""
        self.running = False


# ================= 入口 =================

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="BTC交易Agent监控 (Layer 2)")
    parser.add_argument("--config", default="monitor/monitor_config.yaml",
                        help="配置文件路径")
    parser.add_argument("--check-once", action="store_true",
                        help="只检查一次")
    parser.add_argument("--status", action="store_true",
                        help="显示最近状态")

    args = parser.parse_args()

    # 创建监控Agent
    agent = MonitorAgent(args.config)

    if args.check_once:
        # 只检查一次
        result = agent.run_check()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["overall"] == "healthy" else 1)

    elif args.status:
        # 显示最近状态
        with agent._lock:
            for r in agent.status_history[-10:]:
                print(f"{r['time']}: {r['overall']}")
        sys.exit(0)

    else:
        # 持续运行
        agent.run_continuous()


if __name__ == "__main__":
    main()
