import json
import logging
import sys
from functools import lru_cache
from typing import Any

from app.core.config.environment import get_environment


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
def _build_stdlib_logger() -> logging.Logger:
    settings = get_environment()
    log_level = _resolve_log_level(settings.LOG_LEVEL)

    application_logger = logging.getLogger(settings.APP_NAME)
    if application_logger.handlers:
        return application_logger

    application_logger.setLevel(log_level)
    application_logger.propagate = False

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        _EventFormatter(
            fmt="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    application_logger.addHandler(console_handler)

    if settings.AXIOM_TOKEN:
        try:
            import axiom_py
            from axiom_py.logging import AxiomHandler

            client = axiom_py.Client(settings.AXIOM_TOKEN)
            axiom_handler = AxiomHandler(client, settings.AXIOM_DATASET)
            axiom_handler.setLevel(log_level)
            application_logger.addHandler(axiom_handler)
        except Exception as exc:  # pragma: no cover
            application_logger.warning(
                "Axiom handler setup failed; logging to stdout only | error=%s",
                exc,
            )

    return application_logger


class AppLogger:
    """Small structured logger wrapper used across the app."""

    def __init__(self, raw_logger: logging.Logger | None = None) -> None:
        self._logger = raw_logger or _build_stdlib_logger()

    def _log(
        self,
        level: int,
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

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, exc_info=exc_info, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        event_data = {key: value for key, value in kwargs.items() if value is not None}
        self._logger.exception(message, extra={"event_data": event_data})


@lru_cache(maxsize=1)
def get_logger() -> AppLogger:
    """Get the application logger."""
    return AppLogger()
