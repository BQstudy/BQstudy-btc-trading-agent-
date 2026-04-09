#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试分层监控系统
"""
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sys
sys.path.insert(0, 'src')

from self_check import get_self_checker
from datetime import datetime

def test_self_checker():
    """测试自检查模块"""
    print("=" * 60)
    print("测试 Layer 1: 自检查模块")
    print("=" * 60)

    checker = get_self_checker()

    # 测试初始状态
    status = checker.get_health_status()
    print(f"\n初始状态: {status.status}")
    print(f"运行时间: {status.uptime_seconds}秒")
    print(f"完成周期: {status.cycles_completed}")
    print(f"内存使用: {status.memory_usage_mb}MB ({status.memory_usage_percent}%)")

    # 模拟周期完成
    print("\n模拟周期完成...")
    checker.record_cycle_complete()
    checker.record_telegram_success()

    status = checker.get_health_status()
    print(f"完成周期: {status.cycles_completed}")
    print(f"每小时周期数: {status.cycles_per_hour:.2f}")

    # 模拟错误
    print("\n模拟错误...")
    checker.record_error("测试错误", {"test": True})

    status = checker.get_health_status()
    print(f"最近1小时错误数: {status.errors_last_hour}")

    # 简化状态
    print("\n简化状态:")
    simple = checker.get_simple_status()
    for k, v in simple.items():
        print(f"  {k}: {v}")

    print("\n✅ Layer 1 测试通过")
    return True


def test_monitor_agent():
    """测试监控Agent"""
    print("\n" + "=" * 60)
    print("测试 Layer 2: 监控Agent")
    print("=" * 60)

    try:
        from monitor.monitor_agent import MonitorAgent

        agent = MonitorAgent("monitor/monitor_config.yaml")

        print(f"\n配置加载成功:")
        print(f"  检查间隔: {agent.config.check_interval}秒")
        print(f"  健康端点: {agent.config.health_endpoint}")
        print(f"  自动重启: {agent.config.auto_restart}")

        # 执行一次检查
        print("\n执行一次健康检查...")
        result = agent.run_check()

        print(f"\n检查结果:")
        print(f"  整体状态: {result['overall']}")
        print(f"  健康端点: {'✅' if result['health_endpoint'].get('ok') else '❌'}")
        print(f"  Docker: {'✅' if result['docker'].get('ok') else '❌'}")
        print(f"  日志: {'✅' if result['logs'].get('ok') else '❌'}")

        if result.get('action_taken'):
            print(f"  执行操作: {result['action_taken']}")

        print("\n✅ Layer 2 测试通过")
        return True

    except Exception as e:
        print(f"\n❌ Layer 2 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """测试集成"""
    print("\n" + "=" * 60)
    print("测试集成: 完整流程")
    print("=" * 60)

    checker = get_self_checker()

    # 模拟一个完整周期
    print("\n模拟完整交易周期...")

    # 1. 周期开始
    checker.record_cycle_start()
    print("  ✓ 周期开始")

    # 2. 模拟一些操作
    time.sleep(0.1)
    print("  ✓ 执行操作")

    # 3. 周期完成
    checker.record_cycle_complete()
    print("  ✓ 周期完成")

    # 4. Telegram通知
    checker.record_telegram_success()
    print("  ✓ Telegram通知成功")

    # 5. 获取状态
    status = checker.get_health_status()
    print(f"\n最终状态: {status.status}")
    print(f"完成周期: {status.cycles_completed}")

    print("\n✅ 集成测试通过")
    return True


if __name__ == "__main__":
    import time

    print("\n" + "=" * 60)
    print("分层监控系统测试")
    print("=" * 60)

    results = []

    # 测试 Layer 1
    results.append(("Layer 1 自检查", test_self_checker()))

    # 测试 Layer 2
    results.append(("Layer 2 监控Agent", test_monitor_agent()))

    # 测试集成
    results.append(("集成测试", test_integration()))

    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")

    all_passed = all(r[1] for r in results)
    print("\n" + ("✅ 所有测试通过" if all_passed else "❌ 部分测试失败"))

    sys.exit(0 if all_passed else 1)
