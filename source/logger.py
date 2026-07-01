"""Logging utilities for the application."""
from __future__ import annotations

import sys

from . import config

LOG_LEVELS: dict[str, int] = {
    "debug": 0,
    "info": 1,
    "warning": 2,
    "error": 3,
}

_handler = None


def set_handler(handler) -> None:
    global _handler
    _handler = handler


def log(level: str, message: str) -> None:
    if LOG_LEVELS.get(level, 1) >= LOG_LEVELS.get(config.log_level, 1):
        if _handler:
            _handler(level, message)
        else:
            print(f"[{level.upper()}] {message}", file=sys.stderr)
