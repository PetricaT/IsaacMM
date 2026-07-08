"""Logging utilities backed by loguru."""

from __future__ import annotations

import sys

from loguru import logger

from . import config

__all__ = ["logger", "log", "set_handler", "set_level"]

_LEVEL_MAP = {
    "debug": "DEBUG",
    "info": "INFO",
    "warning": "WARNING",
    "error": "ERROR",
}

_current_handler = None


def set_handler(handler) -> None:
    """Replace all handlers with a single callable sink."""
    global _current_handler
    _current_handler = handler
    logger.remove()
    if handler is not None:
        logger.add(
            _loguru_sink(handler),
            level=_LEVEL_MAP.get(config.log_level, "INFO"),
            format="{message}",
        )


def set_level(level: str) -> None:
    """Update the log level on the registered handler at runtime."""
    logger.remove()
    if _current_handler is not None:
        logger.add(
            _loguru_sink(_current_handler),
            level=_LEVEL_MAP.get(level, "INFO"),
            format="{message}",
        )


def log(level: str, message: str) -> None:
    logger.log(_LEVEL_MAP.get(level, "INFO"), message)


def _loguru_sink(user_handler):
    """Wrap a ``handler(level, message)`` callable as a loguru sink."""

    def _sink(msg):
        record = msg.record
        user_handler(record["level"].name.lower(), record["message"])

    return _sink


# Remove the default stderr handler loguru adds on import
logger.remove()
