"""
app/core/logging.py
统一日志配置：JSON 格式，同时输出到控制台和按日轮转的文件。

用法：
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Bug 创建成功", extra={"bug_id": 42, "user_id": 1})
"""
import logging
import logging.handlers
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path


# ── JSON Formatter ────────────────────────────────────────────────────────────

class JsonFormatter(logging.Formatter):
    """将 LogRecord 序列化为单行 JSON，extra 字段自动展开到顶层。"""

    # LogRecord 的系统字段，不重复输出到 extra
    _RESERVED = frozenset({
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "message",
        "taskName",
    })

    def format(self, record: logging.LogRecord) -> str:
        # 基础字段
        log: dict = {
            "time":    datetime.fromtimestamp(record.created, tz=timezone.utc)
                       .astimezone()
                       .strftime("%Y-%m-%dT%H:%M:%S%z"),
            "level":   record.levelname,
            "logger":  record.name,
            "module":  record.module,
            "line":    record.lineno,
            "msg":     record.getMessage(),
        }

        # extra 字段（用户自定义的业务字段）
        for k, v in record.__dict__.items():
            if k not in self._RESERVED:
                log[k] = v

        # 异常堆栈
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)

        return json.dumps(log, ensure_ascii=False, default=str)


# ── 初始化函数 ────────────────────────────────────────────────────────────────

def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    app_name: str = "bug-platform",
) -> None:
    """
    初始化全局日志配置，只需在应用启动时调用一次。

    输出：
    - 控制台（StreamHandler）：彩色级别前缀 + JSON
    - 文件（TimedRotatingFileHandler）：按日轮转，保留 30 天
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # 创建 logs 目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    formatter = JsonFormatter()

    # ── 控制台 Handler ────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    # ── 文件 Handler（按日轮转） ──────────────────────────────
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_path / f"{app_name}.log",
        when="midnight",          # 每天 0 点轮转
        interval=1,
        backupCount=30,           # 保留 30 天
        encoding="utf-8",
        utc=False,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    file_handler.suffix = "%Y-%m-%d"  # 轮转后文件名：bug-platform.log.2026-07-31

    # ── 错误单独文件（ERROR 及以上） ──────────────────────────
    error_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_path / f"{app_name}.error.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=False,
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    error_handler.suffix = "%Y-%m-%d"

    # ── 根 logger 配置 ────────────────────────────────────────
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 避免重复添加 handler（热重载时会多次调用）
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_handler)

    # 降低三方库噪音
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取模块 logger，在各模块顶部调用：logger = get_logger(__name__)"""
    return logging.getLogger(name)
