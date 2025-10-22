"""日志管理模块."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Any

from config.settings import get_settings
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """自定义JSON日志格式化器."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """添加自定义字段到日志记录."""
        super().add_fields(log_record, record, message_dict)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        if hasattr(record, "module"):
            log_record["module"] = record.module
        if hasattr(record, "funcName"):
            log_record["function"] = record.funcName


def setup_logging() -> None:
    """配置日志系统."""
    settings = get_settings()

    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    # 清除现有处理器
    root_logger.handlers.clear()

    # 控制台处理器 - 使用简单格式
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.log_level)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器 - 使用JSON格式
    log_path = settings.get_log_path()
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(settings.log_level)
    json_formatter = CustomJsonFormatter(
        "%(timestamp)s %(level)s %(logger)s %(module)s %(function)s %(message)s",
    )
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    # 设置第三方库的日志级别
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志记录器.

    Args:
        name: 日志记录器名称,通常使用 __name__

    Returns:
        日志记录器实例
    """
    return logging.getLogger(name)

