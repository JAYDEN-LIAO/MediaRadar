# backend/core/logger.py
import logging
import os
import json
import socket
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional, Dict, Any
from core.config import settings


class JSONFormatter(logging.Formatter):
    """JSON 格式化器"""

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
        self._hostname = socket.gethostname()

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.") + f"{record.msecs:.3f}",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "hostname": self._hostname,
        }

        # 添加组件信息（从 extra 获取）
        if hasattr(record, "component") and record.component:
            log_data["component"] = record.component

        # 添加任务上下文
        if hasattr(record, "task_id") and record.task_id:
            log_data["task_id"] = record.task_id
        if hasattr(record, "keyword") and record.keyword:
            log_data["keyword"] = record.keyword

        # 添加额外字段
        if self.include_extra and hasattr(record, "extra") and record.extra:
            log_data["extra"] = record.extra

        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """彩色控制台格式化器"""

    COLORS = {
        "DEBUG": "\033[36m",     # 青色
        "INFO": "\033[32m",      # 绿色
        "WARNING": "\033[33m",   # 黄色
        "ERROR": "\033[31m",     # 红色
        "CRITICAL": "\033[35m",  # 紫色
        "RESET": "\033[0m",
    }

    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"] if self.use_color else ""

        # 时间精简
        time_str = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")

        # 获取组件名
        component = getattr(record, "component", "") or record.name.split(".")[-1]

        # 构建 task_id 显示
        task_id = getattr(record, "task_id", "") or ""
        task_str = f" [{task_id[:8]}]" if task_id else ""

        # 消息处理（去掉 emoji）
        msg = record.getMessage()

        level_str = f"{color}{record.levelname:<8}{reset}"
        if self.use_color:
            return f"[{time_str}] [{level_str}] [{component}]{task_str} {msg}"
        else:
            return f"[{time_str}] [{record.levelname:<8}] [{component}]{task_str} {msg}"


class PlainFormatter(logging.Formatter):
    """普通文本格式化器"""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


class LoggerFactory:
    """Logger 工厂类 - 线程安全"""

    _instance: Optional["LoggerFactory"] = None
    _lock = threading.Lock()

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
        self._initialized = True

        self._loggers: Dict[str, logging.Logger] = {}
        self._handlers: Dict[str, logging.Handler] = {}
        self._global_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        self._format_type = settings.LOG_FORMAT.lower()
        self._log_to_file = settings.LOG_TO_FILE
        self._log_to_console = settings.LOG_TO_CONSOLE

        # 确保日志目录存在
        self._ensure_log_dirs()

    def _ensure_log_dirs(self):
        """确保所有日志目录存在"""
        log_base = settings.LOG_DIR
        subdirs = ["radar", "crawler", "agent", "gateway", "mcp", "audit", "error"]
        for subdir in subdirs:
            path = os.path.join(log_base, subdir)
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)

    def _create_file_handler(
        self,
        log_path: str,
        level: int,
        format_type: str = None
    ) -> logging.Handler:
        """创建文件处理器"""
        format_type = format_type or self._format_type

        if format_type == "json":
            handler = TimedRotatingFileHandler(
                filename=log_path,
                when="midnight",
                interval=1,
                backupCount=settings.LOG_BACKUP_COUNT,
                encoding="utf-8"
            )
            handler.setFormatter(JSONFormatter())
        else:
            handler = TimedRotatingFileHandler(
                filename=log_path,
                when="midnight",
                interval=1,
                backupCount=settings.LOG_BACKUP_COUNT,
                encoding="utf-8"
            )
            handler.setFormatter(PlainFormatter())

        handler.setLevel(level)
        return handler

    def _create_console_handler(self, level: int) -> logging.Handler:
        """创建控制台处理器"""
        handler = logging.StreamHandler()
        handler.setLevel(level)

        if os.name == "nt":
            # Windows 不使用 ANSI 颜色
            handler.setFormatter(ColoredConsoleFormatter(use_color=False))
        else:
            handler.setFormatter(ColoredConsoleFormatter(use_color=True))

        return handler

    def _get_log_path(self, logger_name: str) -> str:
        """根据 logger 名称获取日志文件路径"""
        log_base = settings.LOG_DIR
        today = datetime.now().strftime("%Y-%m-%d")

        # 根据 logger 前缀确定子目录
        if logger_name.startswith("radar") or logger_name.startswith("radar_service"):
            subdir = "radar"
            filename = f"radar-{today}.log"
        elif logger_name.startswith("crawler"):
            subdir = "crawler"
            filename = f"crawler-{today}.log"
        elif logger_name.startswith("agent"):
            subdir = "agent"
            filename = f"agent-{today}.log"
        elif logger_name.startswith("gateway"):
            subdir = "gateway"
            filename = f"gateway-{today}.log"
        elif logger_name.startswith("mcp"):
            subdir = "mcp"
            filename = f"mcp-{today}.log"
        else:
            subdir = "radar"
            filename = f"{logger_name}-{today}.log"

        return os.path.join(log_base, subdir, filename)

    def get_logger(
        self,
        name: str,
        level: Optional[int] = None,
        propagate: bool = False
    ) -> logging.Logger:
        """
        获取或创建一个 Logger

        Args:
            name: logger 名称，如 "radar.pipeline"
            level: 日志级别，默认使用全局设置
            propagate: 是否向上传播（不建议开启，会导致重复输出）

        Returns:
            logging.Logger 实例
        """
        if name in self._loggers:
            return self._loggers[name]

        with self._lock:
            if name in self._loggers:
                return self._loggers[name]

            logger = logging.getLogger(name)
            logger.setLevel(level or self._global_level)
            logger.propagate = propagate
            logger.handlers.clear()

            # 文件输出
            if self._log_to_file:
                log_path = self._get_log_path(name)
                file_handler = self._create_file_handler(log_path, logger.level)
                logger.addHandler(file_handler)

                # 错误日志汇总 - 单独处理
                if logger.level <= logging.ERROR:
                    error_path = os.path.join(
                        settings.LOG_DIR, "error", f"error-{datetime.now().strftime('%Y-%m-%d')}.log"
                    )
                    error_handler = self._create_file_handler(error_path, logging.ERROR)
                    logger.addHandler(error_handler)

            # 控制台输出
            if self._log_to_console:
                console_handler = self._create_console_handler(logger.level)
                logger.addHandler(console_handler)

            self._loggers[name] = logger
            return logger

    def set_global_level(self, level: str):
        """设置全局日志级别"""
        self._global_level = getattr(logging, level.upper(), logging.INFO)
        for logger in self._loggers.values():
            logger.setLevel(self._global_level)

    def flush(self):
        """刷新所有 handler"""
        for logger in self._loggers.values():
            for handler in logger.handlers:
                handler.flush()


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    便捷函数：获取 logger

    Usage:
        logger = get_logger("radar.pipeline")
        logger = get_logger("radar.cluster", level=logging.DEBUG)
    """
    return LoggerFactory().get_logger(name, level)


# 保持向后兼容的默认 logger
def get_default_logger() -> logging.Logger:
    """获取默认 logger（向后兼容）"""
    return get_logger("MediaRadar")


# 审计日志独立实例
_audit_logger: Optional[logging.Logger] = None


def get_audit_logger() -> logging.Logger:
    """获取审计日志 logger"""
    global _audit_logger
    if _audit_logger is None:
        audit_path = os.path.join(
            settings.LOG_DIR, "audit", f"audit-{datetime.now().strftime('%Y-%m-%d')}.log"
        )

        _audit_logger = logging.getLogger("audit")
        _audit_logger.setLevel(logging.INFO)
        _audit_logger.propagate = False
        _audit_logger.handlers.clear()

        handler = TimedRotatingFileHandler(
            filename=audit_path,
            when="midnight",
            interval=1,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8"
        )
        handler.setFormatter(JSONFormatter())

        _audit_logger.addHandler(handler)

        # 控制台也输出审计日志
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ColoredConsoleFormatter(use_color=True))
        _audit_logger.addHandler(console_handler)

    return _audit_logger
