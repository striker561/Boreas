import json
import logging
import sys
from functools import lru_cache
from typing import Any

import logfire

from app.core.config.environment import Environment, get_environment


class _EventFormatter(logging.Formatter):
    """Console formatter that appends structured event data."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        event_data = getattr(record, "event_data", None)
        if not event_data:
            return message

        extras = " ".join(
            f"{key}={json.dumps(value, default=str, sort_keys=True)}"
            for key, value in sorted(event_data.items())
        )
        return f"{message} | {extras}"


def _resolve_log_level(level_name: str) -> int:
    return getattr(logging, level_name.upper(), logging.INFO)


@lru_cache(maxsize=1)
def _get_logfire_client() -> Any:
    settings = get_environment()
    return logfire.configure(
        local=not settings.IS_PRODUCTION,
        send_to_logfire=(
            settings.LOGFIRE_SEND_TO_LOGFIRE and bool(settings.LOGFIRE_TOKEN)
        ),
        token=settings.LOGFIRE_TOKEN,
        service_name=settings.LOGFIRE_SERVICE_NAME,
        service_version=settings.APP_VERSION,
        environment=settings.LOGFIRE_ENVIRONMENT,
        min_level=_resolve_log_level(settings.LOG_LEVEL),
    )


@lru_cache(maxsize=1)
def _build_stdlib_logger() -> logging.Logger:
    settings = get_environment()
    _get_logfire_client()

    application_logger = logging.getLogger(settings.LOGFIRE_SERVICE_NAME)
    if application_logger.handlers:
        return application_logger

    application_logger.setLevel(_resolve_log_level(settings.LOG_LEVEL))
    application_logger.propagate = False

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        _EventFormatter(
            fmt="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    application_logger.addHandler(console_handler)
    return application_logger


class AppLogger:
    """Small structured logger wrapper used across the app."""

    def __init__(self, raw_logger: logging.Logger | None = None) -> None:
        self._logger = raw_logger or _build_stdlib_logger()

    def _log(
        self,
        level: int,
        logfire_method_name: str,
        message: str,
        *,
        exc_info: bool = False,
        **kwargs: Any,
    ) -> None:
        event_data = {key: value for key, value in kwargs.items() if value is not None}
        self._logger.log(
            level,
            message,
            extra={"event_data": event_data},
            exc_info=exc_info,
        )
        getattr(_get_logfire_client(), logfire_method_name)(message, **event_data)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, "debug", message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log(logging.INFO, "info", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(logging.WARNING, "warning", message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        """Log error message."""
        self._log(
            logging.ERROR,
            "error",
            message,
            exc_info=exc_info,
            **kwargs,
        )

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        event_data = {key: value for key, value in kwargs.items() if value is not None}
        self._logger.exception(
            message,
            extra={"event_data": event_data},
        )
        _get_logfire_client().exception(message, **event_data)


@lru_cache(maxsize=1)
def get_logger() -> AppLogger:
    """Get the application logger."""
    return AppLogger()
