"""Console widget for log output display."""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Optional, Union

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QFont, QPalette, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ...core import config, logger
from ...mods.folder_watcher import ModFolderWatcher
from ...mods.workshop import (
    WORKSHOP_RATE_LIMIT,
    _workshop_limiter_state,
    icon_queue,
)

LEVEL_TAGS = {
    "debug": ("[DBG]", QColor("#3B82F6")),
    "info": ("[INF]", None),
    "warning": ("[WRN]", QColor("#EAB308")),
    "error": ("[ERR]", QColor("#EF4444")),
}


class ConsoleWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._watcher = None
        self._native_theme = config.active_theme == "System"
        self._last_message: tuple | None = None
        self._repeat_count: int = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.console = QPlainTextEdit(self)
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Courier New", 9))
        fm = self.console.fontMetrics()
        self.console.setMinimumHeight(fm.lineSpacing() * 3 + 4)
        if not self._native_theme:
            self.console.setStyleSheet(
                f"background-color: {config.console_bg or 'palette(base)'}; color: {config.console_fg or 'palette(text)'}; border: 1px solid {config.console_border or 'palette(mid)'};"
            )
        logger.set_handler(lambda lvl, msg: self._write_console(msg, lvl))

        self.rate_bar = QFrame(self)
        rf = self.rate_bar.fontMetrics()
        self.rate_bar.setFixedHeight(rf.height() + 10)
        if not self._native_theme:
            self.rate_bar.setStyleSheet(
                f"background-color: {config.rate_bar_bg or 'palette(window)'}; border: 1px solid {config.console_border or 'palette(mid)'}; border-top: none;"
            )
        rate_layout = QHBoxLayout(self.rate_bar)
        margin = self.style().pixelMetric(QStyle.PM_LayoutLeftMargin)
        rate_layout.setContentsMargins(margin, 0, margin, 0)
        rate_layout.setSpacing(0)
        self.rate_label = QLabel(f"Workshop: 0/{WORKSHOP_RATE_LIMIT}")
        if not self._native_theme:
            self.rate_label.setStyleSheet(
                f"color: {config.console_fg or 'palette(text)'};"
            )
        self.queue_label = QLabel(" Queued: 0")
        if not self._native_theme:
            self.queue_label.setStyleSheet(
                f"color: {config.console_fg or 'palette(text)'};"
            )
        self.rate_timer_label = QLabel("\u2014")
        if not self._native_theme:
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
            if self._native_theme:
                self._watcher_dot.setStyleSheet("color: palette(highlight);")
            else:
                self._watcher_dot.setStyleSheet(
                    f"color: {config.win_color or 'palette(highlight)'};"
                )
            self._watcher_dot.setToolTip("Folder watcher: active")
        else:
            self._watcher_dot.setStyleSheet("color: palette(mid);")
            self._watcher_dot.setToolTip("Folder watcher: inactive")

    def log(self, message: str, level: str = "info") -> None:
        logger.log(level, message)

    @staticmethod
    def _mid_tone() -> QColor:
        app = QApplication.instance()
        if app is None:
            return QColor(128, 128, 128)
        p = app.palette()
        tc = p.color(QPalette.ColorRole.Text)
        bc = p.color(QPalette.ColorRole.Base)
        return QColor(
            int(tc.red() * 0.4 + bc.red() * 0.6),
            int(tc.green() * 0.4 + bc.green() * 0.6),
            int(tc.blue() * 0.4 + bc.blue() * 0.6),
        )

    def _insert_tag(
        self, cursor: QTextCursor, prefix: str, tag_color: QColor | None
    ) -> None:
        tag_fmt = QTextCharFormat()
        tag_fmt.setFontWeight(QFont.Weight.Bold)
        if tag_color:
            tag_fmt.setForeground(tag_color)
        cursor.insertText(f"{prefix} ", tag_fmt)

    def _insert_timestamp(self, cursor: QTextCursor, timestamp: str) -> None:
        ts_fmt = QTextCharFormat()
        ts_fmt.setForeground(self._mid_tone())
        cursor.insertText(f"[{timestamp}] ", ts_fmt)

    def _dedup_key(self, level: str, message: str) -> tuple:
        return (level, re.sub(r"\d+", "#", message))

    def _write_console(self, message: str, level: str = "info") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix, tag_color = LEVEL_TAGS.get(level, ("[INF]", None))

        level_msg_colors = {
            "info": config.log_info_color,
            "warning": config.log_warn_color,
            "error": config.log_error_color,
        }
        msg_color = level_msg_colors.get(level, config.log_info_color)

        current_key = self._dedup_key(level, message)
        cursor = self.console.textCursor()

        if current_key == self._last_message:
            self._repeat_count += 1
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.movePosition(
                QTextCursor.MoveOperation.PreviousBlock, QTextCursor.MoveMode.MoveAnchor
            )
            cursor.movePosition(
                QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
            )
            cursor.removeSelectedText()
            self._insert_tag(cursor, prefix, tag_color)
            self._insert_timestamp(cursor, timestamp)
            msg_fmt = QTextCharFormat()
            if not self._native_theme and msg_color:
                msg_fmt.setForeground(QColor(msg_color))
            cursor.insertText(f"{message} x{self._repeat_count + 1}", msg_fmt)
            cursor.insertText("\n")
        else:
            self._last_message = current_key
            self._repeat_count = 0
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._insert_tag(cursor, prefix, tag_color)
            self._insert_timestamp(cursor, timestamp)
            msg_fmt = QTextCharFormat()
            if not self._native_theme and msg_color:
                msg_fmt.setForeground(QColor(msg_color))
            cursor.insertText(f"{message}\n", msg_fmt)

        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    def log_colored(
        self, segments: list[tuple[str, Optional[str | QTextCharFormat]]]
    ) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._insert_tag(cursor, "[INF]", None)
        self._insert_timestamp(cursor, timestamp)
        for text, fmt_or_color in segments:
            fmt = QTextCharFormat()
            if fmt_or_color is None:
                pass
            elif isinstance(fmt_or_color, str):
                fmt.setForeground(QColor(fmt_or_color))
            else:
                fmt = fmt_or_color
            cursor.insertText(text, fmt)
        cursor.insertText("\n")
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    def _update_rate_bar(self) -> None:
        count, next_available = _workshop_limiter_state()
        self.rate_label.setText(f"Workshop: {count}/{WORKSHOP_RATE_LIMIT}")
        self.queue_label.setText(f" Queued: {len(icon_queue)}")
        if next_available is not None:
            remaining = int(next_available - time.time())
            if remaining > 0:
                mins, secs = divmod(remaining, 60)
                self.rate_timer_label.setText(f"Cooldown: {mins}m {secs}s")
                if self._native_theme:
                    self.rate_timer_label.setStyleSheet("color: palette(text);")
                else:
                    self.rate_timer_label.setStyleSheet(
                        f"color: {config.log_warn_color or 'palette(text)'};"
                    )
                self.rate_timer_label.show()
            else:
                self.rate_timer_label.hide()
        else:
            self.rate_timer_label.hide()
