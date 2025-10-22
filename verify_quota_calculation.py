#!/usr/bin/env python3
"""
验证配额计算的正确性（滑动窗口版本）
"""

from config import ConfigManager
from database import Database
from scheduler.cpu_scheduler import CPUScheduler


def main():
    print("=" * 80)
    print("CPU 配额计算验证（滑动窗口）")
    print("=" * 80)

    # 初始化
    db = Database()
    config = ConfigManager(db)
    scheduler = CPUScheduler(db, config)

    # 获取配置
    print("\n【配置信息】")
    print(f"  滚动窗口: {config.rolling_window_hours} 小时 (滑动窗口: now - {config.rolling_window_hours}h 到 now)")
    print(f"  平均负载限制: {config.avg_load_limit_percent}%")
    print(f"  采集间隔: {config.metrics_interval_seconds} 秒")
    print(f"  最小负载: {config.min_load_percent}%")
    print(f"  最大负载: {config.max_load_percent}%")

    # 计算滚动窗口平均
    avg_cpu, data_points = scheduler.calculate_rolling_window_avg()
    print("\n【滚动窗口统计】")
    print(f"  数据点数量: {data_points}")
    print(f"  平均 CPU: {avg_cpu}%")

    # 计算配额信息
    quota_info = scheduler.calculate_remaining_quota()
    print("\n【配额计算（滑动窗口）】")
    print(f"  窗口时长: {quota_info['window_minutes']:.2f} 分钟 ({quota_info['window_minutes'] / 60:.2f} 小时)")
    print(f"  实际运行时长: {quota_info['actual_minutes']:.2f} 分钟 ({quota_info['actual_minutes'] / 60:.2f} 小时)")
    print(
        f"  剩余时间: {quota_info['window_minutes'] - quota_info['actual_minutes']:.2f} 分钟 ({(quota_info['window_minutes'] - quota_info['actual_minutes']) / 60:.2f} 小时)",
    )

    print(f"\n  总配额: {quota_info['total_quota']:.2f} 百分比·分钟")
    print(
        f"    计算: {config.avg_load_limit_percent}% × {quota_info['window_minutes']:.2f}min = {quota_info['total_quota']:.2f} %·min",
    )

    print(f"\n  实际平均 CPU: {quota_info['avg_cpu_percent']:.2f}%")
    print(f"  已用配额: {quota_info['used_quota']:.2f} 百分比·分钟")
    print(
        f"    计算: {quota_info['avg_cpu_percent']:.2f}% × {quota_info['actual_minutes']:.2f}min = {quota_info['used_quota']:.2f} %·min",
    )
    print("    说明: 使用实际运行时长，而不是窗口时长")

    print(f"\n  剩余配额: {quota_info['remaining_quota']:.2f} 百分比·分钟")
    print(
        f"    计算: {quota_info['total_quota']:.2f} - {quota_info['used_quota']:.2f} = {quota_info['remaining_quota']:.2f} %·min",
    )

    remaining_minutes = quota_info["window_minutes"] - quota_info["actual_minutes"]
    print(f"\n  目标 CPU 使用率: {quota_info['target_cpu_percent']:.2f}%")
    if remaining_minutes > 0:
        print(
            f"    说明: 未来 {remaining_minutes:.2f} 分钟 ({remaining_minutes / 60:.2f} 小时) 内，建议保持在 {quota_info['target_cpu_percent']:.2f}% 以下",
        )
        print(
            f"    计算: {quota_info['remaining_quota']:.2f} %·min / {remaining_minutes:.2f}min = {quota_info['target_cpu_percent']:.2f}%",
        )
    elif quota_info["remaining_quota"] >= 0:
        print("    说明: 已运行满窗口时长，剩余配额为正，可以继续保持在限制内")
    else:
        print("    说明: 已运行满窗口时长，剩余配额为负，已超出预算")

    # 计算安全限制
    safe_limit = scheduler.calculate_safe_cpu_limit()
    print("\n【安全限制计算】")
    safety_factor = 0.9
    quota_based = quota_info["target_cpu_percent"] * safety_factor
    print(f"  基于目标CPU的限制: {quota_based:.2f}%")
    print(f"    计算: {quota_info['target_cpu_percent']:.2f}% × {safety_factor} = {quota_based:.2f}%")
    print(f"  最终安全限制: {safe_limit}%")

    # 获取完整状态
    status = scheduler.get_scheduler_status()
    print("\n【调度器状态】")
    print(f"  滚动窗口平均 CPU: {status['rolling_window_avg_cpu']}%")
    print(f"  平均负载限制: {status['avg_load_limit']}%")
    print(f"  绝对余量: {status['margin_absolute']:.2f}%")
    print(
        f"    计算: {status['avg_load_limit']}% - {status['rolling_window_avg_cpu']}% = {status['margin_absolute']:.2f}%",
    )
    if status["margin_absolute"] < 0:
        print(f"    ⚠️  警告: 当前平均CPU已超过限制 {abs(status['margin_absolute']):.2f}%")
    print(f"  相对余量: {status['margin_percent']:.2f}%")
    print(
        f"    计算: ({status['margin_absolute']:.2f} / {status['avg_load_limit']}) × 100 = {status['margin_percent']:.2f}%",
    )
    print(f"  负载等级: {status['risk_level']}")
    print(f"  安全 CPU 限制: {status['safe_cpu_limit']}%")
    print(f"  数据点数量: {status['data_points']}")

    # 验证计算正确性
    print("\n【验证】")

    # 验证1: 总配额
    expected_total = config.avg_load_limit_percent * config.rolling_window_hours * 60
    actual_total = quota_info["total_quota"]
    print(
        f"  ✓ 总配额: {actual_total:.2f} (期望: {expected_total:.2f}) - {'✅ 通过' if abs(actual_total - expected_total) < 0.01 else '❌ 失败'}",
    )

    # 验证2: 已用配额（使用实际运行时长）
    expected_used = quota_info["avg_cpu_percent"] * quota_info["actual_minutes"]
    actual_used = quota_info["used_quota"]
    print(
        f"  ✓ 已用配额: {actual_used:.2f} (期望: {expected_used:.2f}) - {'✅ 通过' if abs(actual_used - expected_used) < 0.01 else '❌ 失败'}",
    )

    # 验证3: 剩余配额
    expected_remaining = expected_total - expected_used
    actual_remaining = quota_info["remaining_quota"]
    print(
        f"  ✓ 剩余配额: {actual_remaining:.2f} (期望: {expected_remaining:.2f}) - {'✅ 通过' if abs(actual_remaining - expected_remaining) < 0.01 else '❌ 失败'}",
    )

    # 验证4: 绝对余量
    expected_margin = config.avg_load_limit_percent - avg_cpu
    actual_margin = status["margin_absolute"]
    print(
        f"  ✓ 绝对余量: {actual_margin:.2f}% (期望: {expected_margin:.2f}%) - {'✅ 通过' if abs(actual_margin - expected_margin) < 0.01 else '❌ 失败'}",
    )

    # 验证5: 目标CPU
    remaining_minutes = quota_info["window_minutes"] - quota_info["actual_minutes"]
    if remaining_minutes > 0:
        expected_target = max(0, min(100, quota_info["remaining_quota"] / remaining_minutes))
    else:
        expected_target = config.avg_load_limit_percent if quota_info["remaining_quota"] >= 0 else 0
    actual_target = quota_info["target_cpu_percent"]
    print(
        f"  ✓ 目标CPU: {actual_target:.2f}% (期望: {expected_target:.2f}%) - {'✅ 通过' if abs(actual_target - expected_target) < 0.01 else '❌ 失败'}",
    )

    print("\n" + "=" * 80)

    # 总结
    print("\n【总结】")
    if quota_info["remaining_quota"] >= 0:
        print("  ✅ 当前状态: 未超限")
        print(
            f"  📊 剩余配额: {quota_info['remaining_quota']:.2f} %·min ({quota_info['remaining_quota'] / 60:.2f} %·h)"
        )
        print("  🎯 建议: 可以继续保持当前负载水平")
    else:
        print("  ⚠️  当前状态: 已超限")
        print(
            f"  📊 超出配额: {abs(quota_info['remaining_quota']):.2f} %·min ({abs(quota_info['remaining_quota']) / 60:.2f} %·h)"
        )
        print(f"  🎯 建议: 降低CPU使用率到 {quota_info['target_cpu_percent']:.2f}% 以下")
        print(f"  🔧 安全限制: {safe_limit}% (已应用安全系数)")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
