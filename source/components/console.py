"""Console widget for log output display."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .. import config, logger
from ..folder_watcher import ModFolderWatcher
from .workshop import (
    WORKSHOP_RATE_LIMIT,
    _workshop_limiter_state,
    _workshop_queue_length,
)


class ConsoleWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._watcher = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.console = QPlainTextEdit(self)
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Courier New", 9))
        fm = self.console.fontMetrics()
        self.console.setFixedHeight(fm.lineSpacing() * 5 + 4)
        self.console.setStyleSheet(
            f"background-color: {config.console_bg or 'palette(base)'}; color: {config.console_fg or 'palette(text)'}; border: 1px solid {config.console_border or 'palette(mid)'};"
        )
        logger.set_handler(lambda lvl, msg: self._write_console(msg, lvl))

        self.rate_bar = QFrame(self)
        rf = self.rate_bar.fontMetrics()
        self.rate_bar.setFixedHeight(rf.height() + 10)
        self.rate_bar.setStyleSheet(
            f"background-color: {config.rate_bar_bg or 'palette(window)'}; border: 1px solid {config.console_border or 'palette(mid)'}; border-top: none;"
        )
        rate_layout = QHBoxLayout(self.rate_bar)
        margin = self.style().pixelMetric(QStyle.PM_LayoutLeftMargin)
        rate_layout.setContentsMargins(margin, 0, margin, 0)
        rate_layout.setSpacing(0)
        self.rate_label = QLabel(f"Workshop: 0/{WORKSHOP_RATE_LIMIT}")
        self.rate_label.setStyleSheet(
            f"color: {config.console_fg or 'palette(text)'};"
        )
        self.queue_label = QLabel("Queued: 0")
        self.queue_label.setStyleSheet(
            f"color: {config.console_fg or 'palette(text)'};"
        )
        self.rate_timer_label = QLabel("—")
        self.rate_timer_label.setStyleSheet(
            f"color: {config.console_fg or 'palette(text)'};"
        )
        rate_layout.addWidget(self.rate_label)
        rate_layout.addWidget(self.queue_label)
        rate_layout.addStretch()
        self._watcher_dot = QLabel("\u25cf")
        self._watcher_dot.setToolTip("Folder watcher: inactive")
        self._watcher_dot.setStyleSheet("color: palette(mid);")
        rate_layout.addWidget(self._watcher_dot)
        rate_layout.addWidget(self.rate_timer_label)

        self._rate_timer = QTimer(self)
        self._rate_timer.timeout.connect(self._update_rate_bar)
        self._rate_timer.start(1000)
        self._update_rate_bar()

        layout.addWidget(self.console)
        layout.addWidget(self.rate_bar)

    def set_watcher(self, watcher: ModFolderWatcher | None) -> None:
        self._watcher = watcher
        if watcher is not None:
            watcher.is_active_changed.connect(self._on_watcher_state)
            self._on_watcher_state()

    def _on_watcher_state(self) -> None:
        active = self._watcher and self._watcher.is_active
        if active:
            self._watcher_dot.setStyleSheet("color: palette(highlight);")
            self._watcher_dot.setToolTip("Folder watcher: active")
        else:
            self._watcher_dot.setStyleSheet("color: palette(mid);")
            self._watcher_dot.setToolTip("Folder watcher: inactive")

    def log(self, message: str, level: str = "info") -> None:
        logger.log(level, message)

    def _write_console(self, message: str, level: str = "info") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_prefixes = {
            "debug": "[DBG]",
            "info": "[INF]",
            "warning": "[WRN]",
            "error": "[ERR]",
        }
        prefix = level_prefixes.get(level, "[INF]")
        level_colors = {
            "info": config.log_info_color,
            "warning": config.log_warn_color,
            "error": config.log_error_color,
        }
        log_color = level_colors.get(level, config.log_info_color)
        text_cursor = self.console.textCursor()
        text_cursor.movePosition(QTextCursor.MoveOperation.End)
        char_format = QTextCharFormat()
        if log_color:
            char_format.setForeground(QColor(log_color))
        text_cursor.insertText(f"{prefix} [{timestamp}] {message}\n", char_format)
        self.console.setTextCursor(text_cursor)
        self.console.ensureCursorVisible()

    def log_colored(self, segments: list[tuple[str, Optional[str]]]) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        text_cursor = self.console.textCursor()
        text_cursor.movePosition(QTextCursor.MoveOperation.End)
        char_format = QTextCharFormat()
        if config.log_info_color:
            char_format.setForeground(QColor(config.log_info_color))
        text_cursor.insertText(f"[INF] [{timestamp}] ", char_format)
        for text, color in segments:
            if color:
                char_format.setForeground(QColor(color))
            elif config.log_info_color:
                char_format.setForeground(QColor(config.log_info_color))
            else:
                char_format.clearForeground()
            text_cursor.insertText(text, char_format)
        text_cursor.insertText("\n", char_format)
        self.console.setTextCursor(text_cursor)
        self.console.ensureCursorVisible()

    def _update_rate_bar(self) -> None:
        count, next_available = _workshop_limiter_state()
        self.rate_label.setText(f"Workshop: {count}/{WORKSHOP_RATE_LIMIT}")
        self.queue_label.setText(f"Queued: {_workshop_queue_length()}")
        if next_available is not None:
            remaining = int(next_available - time.time())
            if remaining > 0:
                mins, secs = divmod(remaining, 60)
                self.rate_timer_label.setText(f"Cooldown: {mins}m {secs}s")
                self.rate_timer_label.setStyleSheet(
                    f"color: {config.log_warn_color or 'palette(text)'};"
                )
                self.rate_timer_label.show()
            else:
                self.rate_timer_label.hide()
        else:
            self.rate_timer_label.hide()
