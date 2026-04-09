"""
自检查模块 - 交易Agent自我健康检查 (Layer 1)
记录运行状态、检测异常、上报健康状态
"""

import os
import json
import time
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from threading import Lock


@dataclass
class HealthStatus:
    """健康状态数据结构"""
    status: str  # "healthy", "degraded", "critical"
    timestamp: str
    uptime_seconds: int
    last_cycle_time: Optional[str]
    cycles_completed: int
    cycles_per_hour: float
    errors_last_hour: int
    telegram_last_success: Optional[str]
    memory_usage_mb: float
    memory_usage_percent: float
    checks: Dict[str, bool]
    details: Dict[str, Any]


class SelfChecker:
    """
    自我健康检查器
    单例模式，在整个Agent生命周期中保持状态
    """
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.start_time = datetime.now()
        self.cycles_completed = 0
        self.cycle_times: List[datetime] = []
        self.errors: List[Dict] = []
        self.last_telegram_success: Optional[datetime] = None
        self.last_cycle_time: Optional[datetime] = None
        self._initialized = True
        self._lock = Lock()

    def record_cycle_start(self):
        """记录周期开始"""
        pass  # 可选：记录周期开始时间

    def record_cycle_complete(self):
        """记录周期完成"""
        with self._lock:
            self.cycles_completed += 1
            now = datetime.now()
            self.last_cycle_time = now
            self.cycle_times.append(now)
            # 只保留最近24小时的周期记录
            cutoff = now - timedelta(hours=24)
            self.cycle_times = [t for t in self.cycle_times if t > cutoff]

    def record_error(self, error: str, context: Optional[Dict] = None):
        """记录错误"""
        with self._lock:
            self.errors.append({
                "time": datetime.now(),
                "error": error,
                "context": context or {}
            })
            # 只保留最近100条错误
            self.errors = self.errors[-100:]

    def record_telegram_success(self):
        """记录Telegram发送成功"""
        with self._lock:
            self.last_telegram_success = datetime.now()

    def record_telegram_failure(self, error: str):
        """记录Telegram发送失败"""
        with self._lock:
            self.errors.append({
                "time": datetime.now(),
                "error": f"Telegram发送失败: {error}",
                "context": {}
            })

    def get_health_status(self) -> HealthStatus:
        """获取完整健康状态"""
        now = datetime.now()

        # 计算各项指标
        uptime = (now - self.start_time).total_seconds()
        errors_last_hour = self._count_errors_last_hour()
        cycles_per_hour = self._calculate_cycles_per_hour()
        memory_info = self._get_memory_info()

        # 执行各项检查
        checks = {
            "running": True,
            "memory_ok": memory_info["percent"] < 80,
            "cycles_flowing": self._check_cycles_flowing(),
            "telegram_working": self._check_telegram(),
            "no_recent_errors": errors_last_hour < 5,
        }

        # 确定综合状态
        failed_checks = sum(1 for v in checks.values() if not v)
        if failed_checks == 0:
            status = "healthy"
        elif failed_checks <= 2:
            status = "degraded"
        else:
            status = "critical"

        # 详细信息
        details = {
            "error_history": [
                {
                    "time": e["time"].isoformat(),
                    "error": e["error"]
                }
                for e in self.errors[-5:]  # 最近5条错误
            ],
            "cycle_interval_minutes": self._estimate_cycle_interval(),
            "expected_next_cycle": self._estimate_next_cycle().isoformat() if self._estimate_next_cycle() else None,
        }

        return HealthStatus(
            status=status,
            timestamp=now.isoformat(),
            uptime_seconds=int(uptime),
            last_cycle_time=self.last_cycle_time.isoformat() if self.last_cycle_time else None,
            cycles_completed=self.cycles_completed,
            cycles_per_hour=cycles_per_hour,
            errors_last_hour=errors_last_hour,
            telegram_last_success=self.last_telegram_success.isoformat() if self.last_telegram_success else None,
            memory_usage_mb=memory_info["mb"],
            memory_usage_percent=memory_info["percent"],
            checks=checks,
            details=details
        )

    def get_simple_status(self) -> Dict:
        """获取简化状态（用于健康检查端点）"""
        status = self.get_health_status()
        return {
            "status": status.status,
            "timestamp": status.timestamp,
            "uptime_seconds": status.uptime_seconds,
            "cycles_completed": status.cycles_completed,
            "checks": status.checks
        }

    def _count_errors_last_hour(self) -> int:
        """计算最近1小时的错误数"""
        hour_ago = datetime.now() - timedelta(hours=1)
        return sum(1 for e in self.errors if e["time"] > hour_ago)

    def _calculate_cycles_per_hour(self) -> float:
        """计算每小时周期数"""
        if len(self.cycle_times) < 2:
            return 0.0

        hour_ago = datetime.now() - timedelta(hours=1)
        recent_cycles = [t for t in self.cycle_times if t > hour_ago]

        if len(recent_cycles) < 2:
            return float(len(recent_cycles))

        # 计算平均间隔
        intervals = [
            (recent_cycles[i] - recent_cycles[i-1]).total_seconds()
            for i in range(1, len(recent_cycles))
        ]
        avg_interval = sum(intervals) / len(intervals)

        if avg_interval == 0:
            return 0.0

        return 3600.0 / avg_interval

    def _get_memory_info(self) -> Dict:
        """获取内存使用信息"""
        try:
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            system_mem = psutil.virtual_memory()

            return {
                "mb": round(mem_info.rss / 1024 / 1024, 2),
                "percent": round(mem_info.rss / system_mem.total * 100, 2)
            }
        except:
            return {"mb": 0, "percent": 0}

    def _check_cycles_flowing(self) -> bool:
        """检查周期是否正常流动"""
        if self.last_cycle_time is None:
            # 刚开始运行，还没有完成周期
            return True

        # 如果超过70分钟没有新周期，认为异常
        # (正常30分钟一次，给2倍余量+10分钟buffer)
        elapsed = (datetime.now() - self.last_cycle_time).total_seconds()
        return elapsed < 4200  # 70分钟 = 4200秒

    def _check_telegram(self) -> bool:
        """检查Telegram是否正常"""
        if self.last_telegram_success is None:
            # 还没发送过，认为正常
            return True

        # 如果超过70分钟没有成功发送，认为异常
        elapsed = (datetime.now() - self.last_telegram_success).total_seconds()
        return elapsed < 4200

    def _estimate_cycle_interval(self) -> Optional[int]:
        """估算周期间隔（分钟）"""
        if len(self.cycle_times) < 2:
            return None

        intervals = [
            (self.cycle_times[i] - self.cycle_times[i-1]).total_seconds() / 60
            for i in range(1, len(self.cycle_times))
        ]
        return int(sum(intervals) / len(intervals))

    def _estimate_next_cycle(self) -> Optional[datetime]:
        """估算下次周期时间"""
        if self.last_cycle_time is None:
            return None

        interval = self._estimate_cycle_interval()
        if interval is None:
            interval = 30  # 默认30分钟

        return self.last_cycle_time + timedelta(minutes=interval)


# 全局单例实例
_checker_instance = None

def get_self_checker() -> SelfChecker:
    """获取SelfChecker单例实例"""
    global _checker_instance
    if _checker_instance is None:
        _checker_instance = SelfChecker()
    return _checker_instance
