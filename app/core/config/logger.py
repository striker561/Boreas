import io
import logging
import sys
from functools import lru_cache
from typing import Any, Optional

import logfire

from app.core.config.environment import get_environment

# ANSI colour codes — only applied in development
_RESET = "\033[0m"
_LEVEL_COLORS: dict[int, str] = {
    logging.DEBUG: "\033[36m",  # cyan
    logging.INFO: "\033[32m",  # green
    logging.WARNING: "\033[33m",  # yellow
    logging.ERROR: "\033[31m",  # red
    logging.CRITICAL: "\033[35m",  # magenta
}


class _ColorFormatter(logging.Formatter):
    """Console formatter that colourises the level name in development."""

    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelno, "")
        record.levelname = f"{color}{record.levelname:<8}{_RESET}"
        return super().format(record)


class AppLogger:
    """
    Simple singleton logger for the application.

    Usage:
        logger = get_logger()
        logger.info("User logged in")
        logger.error("Failed to connect", service="database")
    """

    _instance: Optional["AppLogger"] = None

    def __new__(cls) -> "AppLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize logger once."""
        settings = get_environment()

        # Setup Logfire
        if settings.IS_PRODUCTION:
            logfire.configure(token=getattr(settings, "LOGFIRE_TOKEN", None))
        else:
            logfire.configure(send_to_logfire=False)

        # Setup standard logger
        self._logger = logging.getLogger(f"{settings.APP_NAME}-log")

        if not self._logger.handlers:
            if not settings.IS_PRODUCTION:
                # Development: coloured console + file, DEBUG level
                dev_fmt = "%(asctime)s | %(levelname)s | %(message)s"
                console = logging.StreamHandler(
                    io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
                )
                console.setFormatter(_ColorFormatter(dev_fmt, datefmt="%H:%M:%S"))
                self._logger.addHandler(console)

                file_handler = logging.FileHandler("app.log", encoding="utf-8")
                file_handler.setFormatter(
                    logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")
                )
                self._logger.addHandler(file_handler)
                self._logger.setLevel(logging.DEBUG)
            else:
                self._logger.setLevel(logging.INFO)

    def _format(self, message: str, **kwargs: Any) -> str:
        """Format message with kwargs."""
        if not kwargs:
            return message
        extras = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        return f"{message} | {extras}"

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._logger.debug(self._format(message, **kwargs))

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._logger.info(self._format(message, **kwargs))
        logfire.info(message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._logger.warning(self._format(message, **kwargs))
        logfire.warn(message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        """Log error message."""
        self._logger.error(self._format(message, **kwargs), exc_info=exc_info)
        logfire.error(message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self._logger.exception(self._format(message, **kwargs))
        logfire.exception(message, **kwargs)


@lru_cache(maxsize=1)
def get_logger() -> AppLogger:
    """Get the application logger."""
    return AppLogger()
