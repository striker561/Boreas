"""Configuration module - Logger and environment settings."""

from app.core.config.environment import Environment, get_environment
from app.core.config.logger import AppLogger, get_logger

# Core configuration exports
logger: AppLogger = get_logger()
environment: Environment = get_environment()

__all__ = ["environment", "get_environment", "get_logger", "logger"]
