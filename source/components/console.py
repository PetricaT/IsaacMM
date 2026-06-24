import time
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from .. import logger
from .workshop import _workshop_limiter_state, WORKSHOP_RATE_LIMIT


class ConsoleWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.console = QPlainTextEdit(self)
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Courier New", 9))
        self.console.setFixedHeight(100)
        self.console.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #333;"
        )
        logger.set_handler(lambda lvl, msg: self._write_console(msg, lvl))

        self.rate_bar = QFrame(self)
        self.rate_bar.setFixedHeight(24)
        self.rate_bar.setStyleSheet(
            "background-color: #252526; border: 1px solid #333; border-top: none;"
        )
        rate_layout = QHBoxLayout(self.rate_bar)
        rate_layout.setContentsMargins(8, 0, 8, 0)
        rate_layout.setSpacing(0)
        self.rate_label = QLabel("Workshop: 0/5")
        self.rate_label.setStyleSheet("color: #d4d4d4; font-size: 11px;")
        self.rate_timer_label = QLabel("—")
        self.rate_timer_label.setStyleSheet("color: #d4d4d4; font-size: 11px;")
        rate_layout.addWidget(self.rate_label)
        rate_layout.addStretch()
        rate_layout.addWidget(self.rate_timer_label)

        self._rate_timer = QTimer(self)
        self._rate_timer.timeout.connect(self._update_rate_bar)
        self._rate_timer.start(1000)
        self._update_rate_bar()

        layout.addWidget(self.console)
        layout.addWidget(self.rate_bar)

    def log(self, message: str, level: str = "info") -> None:
        logger.log(level, message)

    def _write_console(self, message: str, level: str = "info") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_colors = {"info": "#d4d4d4", "warning": "#ffa500", "error": "#ff4444"}
        log_color = level_colors.get(level, "#d4d4d4")
        text_cursor = self.console.textCursor()
        text_cursor.movePosition(QTextCursor.MoveOperation.End)
        char_format = QTextCharFormat()
        char_format.setForeground(QColor(log_color))
        text_cursor.insertText(f"[{timestamp}] {message}\n", char_format)
        self.console.setTextCursor(text_cursor)
        self.console.ensureCursorVisible()

    def log_colored(self, segments: list[tuple[str, Optional[str]]]) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        text_cursor = self.console.textCursor()
        text_cursor.movePosition(QTextCursor.MoveOperation.End)
        char_format = QTextCharFormat()
        char_format.setForeground(QColor("#d4d4d4"))
        text_cursor.insertText(f"[{timestamp}] ", char_format)
        for text, color in segments:
            if color:
                char_format.setForeground(QColor(color))
            else:
                char_format.setForeground(QColor("#d4d4d4"))
            text_cursor.insertText(text, char_format)
        text_cursor.insertText("\n", char_format)
        self.console.setTextCursor(text_cursor)
        self.console.ensureCursorVisible()

    def _update_rate_bar(self) -> None:
        count, next_available = _workshop_limiter_state()
        self.rate_label.setText(f"Workshop: {count}/{WORKSHOP_RATE_LIMIT}")
        if next_available is not None:
            remaining = int(next_available - time.time())
            if remaining > 0:
                mins, secs = divmod(remaining, 60)
                self.rate_timer_label.setText(f"Cooldown: {mins}m {secs}s")
                self.rate_timer_label.setStyleSheet("color: #ffa500; font-size: 11px;")
            else:
                self.rate_timer_label.setText("—")
                self.rate_timer_label.setStyleSheet("color: #d4d4d4; font-size: 11px;")
        else:
            self.rate_timer_label.setText("—")
            self.rate_timer_label.setStyleSheet("color: #d4d4d4; font-size: 11px;")
