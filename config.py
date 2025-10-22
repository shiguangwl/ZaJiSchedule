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
    def avg_load_limit_percent(self) -> float:
        return float(self.get("avg_load_limit_percent", 28.0))

    @property
    def history_retention_days(self) -> int:
        return int(self.get("history_retention_days", 30))

    @property
    def metrics_interval_seconds(self) -> int:
        return int(self.get("metrics_interval_seconds", 15))

    @property
    def safety_factor(self) -> float:
        """安全系数,用于计算CPU限制(0-1之间,越小越保守)"""
        return float(self.get("safety_factor", 0.85))

    @property
    def startup_safety_factor(self) -> float:
        """启动初期安全系数(数据不足时使用)"""
        return float(self.get("startup_safety_factor", 0.7))

    @property
    def startup_data_threshold_percent(self) -> float:
        """启动初期数据阈值(占窗口时长的百分比,低于此值使用启动安全系数)"""
        return float(self.get("startup_data_threshold_percent", 10.0))
