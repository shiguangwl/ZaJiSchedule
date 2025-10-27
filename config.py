"""
配置管理模块
"""

from typing import Any

from database import Database


class ConfigManager:
    """配置管理器"""

    def __init__(self, db: Database):
        self.db = db
        self._cache: dict[str, Any] = {}
        self.reload()

    def reload(self):
        """重新加载配置到缓存"""
        self._cache = self.db.get_all_config()

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._cache.get(key, default)

    def set(self, key: str, value: Any):
        """设置配置值"""
        self.db.set_config(key, value)
        self._cache[key] = value

    def update_batch(self, configs: dict[str, Any]):
        """批量更新配置"""
        self.db.update_config_batch(configs)
        self._cache.update(configs)

    def get_all(self) -> dict[str, Any]:
        """获取所有配置"""
        return self._cache.copy()

    # 便捷访问属性
    @property
    def min_load_percent(self) -> float:
        return float(self.get("min_load_percent", 10.0))

    @property
    def max_load_percent(self) -> float:
        return float(self.get("max_load_percent", 90.0))

    @property
    def rolling_window_hours(self) -> int:
        return int(self.get("rolling_window_hours", 24))

    @property
    def sliding_window_step_seconds(self) -> int:
        """滑动窗口步长（滑动间隔）秒数"""
        return int(self.get("sliding_window_step_seconds", 100))

    @property
    def avg_load_limit_percent(self) -> float:
        return float(self.get("avg_load_limit_percent", 30.0))

    @property
    def history_retention_days(self) -> int:
        return int(self.get("history_retention_days", 30))

    @property
    def metrics_interval_seconds(self) -> int:
        return int(self.get("metrics_interval_seconds", 15))

    @property
    def cpu_limit_adjust_interval_seconds(self) -> int:
        """CPU限制调整间隔秒数(独立于采集频率)"""
        return int(self.get("cpu_limit_adjust_interval_seconds", 15))

    @property
    def safety_factor(self) -> float:
        """安全系数,用于计算CPU限制(0-1之间,越小越保守)"""
        return float(self.get("safety_factor", 0.9))

    @property
    def cpu_limit_tolerance_percent(self) -> float:
        """CPU限制容差(百分比),避免统计精度导致的误报警告"""
        return float(self.get("cpu_limit_tolerance_percent", 1.0))
