"""Console widget for log output display."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional, Union

from PySide6.QtGui import QColor, QFont, QPalette, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core import config, logger

LEVEL_TAGS = {
    "debug": ("[DBG]", QColor("#3B82F6")),
    "info": ("[INF]", None),
    "warning": ("[WRN]", QColor("#EAB308")),
    "error": ("[ERR]", QColor("#EF4444")),
}


class ConsoleWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
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

        layout.addWidget(self.console)

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
