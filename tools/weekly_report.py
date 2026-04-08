"""
周度迭代报告生成器
自动生成周度迭代报告
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from memory.trade_logger import TradeLogger
from evolution.meta_analyzer import MetaAnalyzer
from evolution.prompt_optimizer import PromptOptimizer


def generate_weekly_report(
    trade_logger: TradeLogger,
    output_path: str = "reports/weekly_report.json"
) -> str:
    """
    生成周度迭代报告

    Args:
        trade_logger: 交易日志记录器
        output_path: 输出路径

    Returns:
        报告文件路径
    """
    # 计算上周日期范围
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)

    # 1. 执行元分析
    analyzer = MetaAnalyzer(trade_logger)
    report = analyzer.analyze(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat()
    )

    # 2. 获取交易统计
    stats = trade_logger.get_statistics()

    # 3. 获取经验规则
    rules = trade_logger.get_experience_rules()

    # 4. 生成报告
    weekly_report = {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",

        # 交易概览
        "trading_summary": {
            "total_trades": stats["total_trades"],
            "wins": stats.get("wins", 0),
            "losses": stats.get("losses", 0),
            "win_rate": stats.get("win_rate", 0),
            "avg_pnl": stats.get("avg_pnl", 0),
            "avg_pnl_pct": stats.get("avg_pnl_pct", 0)
        },

        # 行情类型表现
        "regime_performance": {
            regime: {
                "trades": perf.total_trades,
                "win_rate": perf.win_rate,
                "avg_pnl": perf.avg_pnl_pct
            }
            for regime, perf in report.regime_performance.items()
        },

        # 系统性偏差
        "identified_biases": {
            "long_bias_score": report.biases.long_bias_score,
            "early_entry_bias": report.biases.early_entry_bias,
            "stop_tightness": report.biases.stop_tightness
        },

        # 高价值模式
        "high_value_patterns": report.high_value_patterns,
        "loss_patterns": report.loss_patterns,

        # 提示词优化建议
        "optimization_suggestions": report.prompt_optimization_suggestions,

        # 风格漂移
        "style_drift": {
            "detected": report.style_drift_detected,
            "details": report.style_drift_details
        },

        # 经验库
        "experience_rules": rules[:10],  # 最近10条

        # 行动建议
        "action_items": _generate_action_items(report, stats)
    }

    # 保存报告
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(weekly_report, f, indent=2, ensure_ascii=False)

    return str(output_file)


def _generate_action_items(report, stats) -> List[str]:
    """生成行动建议"""
    actions = []

    # 基于偏差
    if report.biases.long_bias_score > 0.7:
        actions.append("[高优先级] 存在过度做多倾向，建议调整判断层提示词增加空头视角权重")

    if report.biases.early_entry_bias:
        actions.append("[高优先级] 存在入场过早问题，建议增加等待确认步骤")

    # 基于绩效
    if stats.get("win_rate", 0) < 40:
        actions.append("[高优先级] 胜率低于40%，建议降低交易频率，提高入场标准")

    # 基于风格漂移
    if report.style_drift_detected:
        actions.append("[中优先级] 检测到风格漂移，建议检查是否过拟合近期行情")

    # 基于优化建议
    for suggestion in report.prompt_optimization_suggestions[:2]:
        actions.append(
            f"[中优先级] {suggestion.get('target', '')}: {suggestion.get('suggestion', '')}"
        )

    if not actions:
        actions.append("[低优先级] 当前表现稳定，继续观察并积累数据")

    return actions


def print_report_summary(report_path: str):
    """打印报告摘要"""
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)

    print("=" * 60)
    print("周度迭代报告摘要")
    print("=" * 60)

    # 交易概览
    summary = report["trading_summary"]
    print(f"\n📊 交易概览")
    print(f"  总交易: {summary['total_trades']}")
    print(f"  胜率: {summary['win_rate']}%")
    print(f"  平均盈亏: {summary['avg_pnl_pct']}%")

    # 行情类型表现
    print(f"\n📈 行情类型表现")
    for regime, perf in report["regime_performance"].items():
        print(f"  {regime}: 胜率{perf['win_rate']}%, 交易{perf['trades']}笔")

    # 系统性偏差
    print(f"\n⚠️  系统性偏差")
    biases = report["identified_biases"]
    print(f"  做多倾向: {biases['long_bias_score']:.2f}")
    print(f"  入场过早: {'是' if biases['early_entry_bias'] else '否'}")

    # 行动建议
    print(f"\n🎯 行动建议")
    for i, action in enumerate(report["action_items"][:5], 1):
        print(f"  {i}. {action}")

    print(f"\n完整报告: {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    # 示例用法
    logger = TradeLogger("data/trades.db")

    report_path = generate_weekly_report(logger)
    print_report_summary(report_path)
