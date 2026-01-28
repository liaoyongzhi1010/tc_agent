"""TC Agent 日志系统"""
import logging
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Any


class JsonFormatter(logging.Formatter):
    """JSON格式日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
            "data": getattr(record, "data", {}),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)


class StructuredLogger:
    """结构化日志,支持文件和控制台输出"""

    _loggers: dict[str, "StructuredLogger"] = {}

    def __init__(self, name: str, log_dir: Optional[Path] = None):
        self.logger = logging.getLogger(name)

        # 避免重复添加handler
        if not self.logger.handlers:
            self.logger.setLevel(logging.DEBUG)

            # 控制台输出
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(
                logging.Formatter(
                    "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            self.logger.addHandler(console_handler)

            # 文件输出
            if log_dir:
                log_dir.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(
                    log_dir / f"{datetime.now():%Y-%m-%d}.log", encoding="utf-8"
                )
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(JsonFormatter())
                self.logger.addHandler(file_handler)

    @classmethod
    def get_logger(cls, name: str, log_dir: Optional[Path] = None) -> "StructuredLogger":
        """获取或创建logger实例"""
        if name not in cls._loggers:
            cls._loggers[name] = cls(name, log_dir)
        return cls._loggers[name]

    def _log(self, level: int, msg: str, **kwargs: Any) -> None:
        """内部日志方法"""
        extra = {"data": kwargs} if kwargs else {}
        self.logger.log(level, msg, extra=extra)

    def info(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, **kwargs)

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, **kwargs)

    def exception(self, msg: str, **kwargs: Any) -> None:
        self.logger.exception(msg, extra={"data": kwargs})


# 便捷函数
def get_logger(name: str, component: str = "backend") -> StructuredLogger:
    """获取logger实例

    Args:
        name: logger名称
        component: 组件名称，用于日志目录分类 (如 backend, extension 等)
    """
    from app.infrastructure.config import settings
    log_dir = settings.data_dir.parent / "logs" / component if not settings.debug else None
    return StructuredLogger.get_logger(name, log_dir)
