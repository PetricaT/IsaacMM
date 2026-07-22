"""Compact status-bar progress widget with an adjacent message label.

Usage example::

    from source.ui.widgets.progress import StatusBarProgress

    progress = StatusBarProgress(parent=some_widget)
    progress.set_message("Checking for updates\u2026")
    progress.set_indeterminate()          # bouncing bar
    progress.set_progress(42)             # determinate 42 %
    progress.finish()                     # hide + reset
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget


class StatusBarProgress(QWidget):
    """A small progress bar + message label meant for status bars.

    The widget is **hidden by default**.  Call :meth:`start` or any
    ``set_*`` method to make it visible; call :meth:`finish` to hide
    and reset it.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(4)

        self._message = QLabel()
        self._message.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._message.setStyleSheet("color: palette(text);")
        self._message.setMinimumWidth(60)
        layout.addWidget(self._message)

        self._bar = QProgressBar()
        self._bar.setTextVisible(False)
        self._bar.setFixedWidth(100)
        self._bar.setFixedHeight(8)
        layout.addWidget(self._bar)

    # -- public API -----------------------------------------------------------

    def set_message(self, text: str) -> None:
        """Update the message label text and show the widget."""
        self._message.setText(text)
        self.setVisible(bool(text))

    def set_progress(self, value: int, maximum: int = 100) -> None:
        """Switch to determinate mode and set the progress value."""
        self._bar.setRange(0, maximum)
        self._bar.setValue(min(value, maximum))
        self.setVisible(True)

    def set_indeterminate(self) -> None:
        """Switch to indeterminate (bouncing) mode."""
        self._bar.setRange(0, 0)
        self.setVisible(True)

    def set_value(self, value: int) -> None:
        """Update the current value (must already be in determinate mode)."""
        self._bar.setValue(value)

    def set_tool_tip(self, tip: str) -> None:
        """Set a tooltip shown on hover."""
        self._bar.setToolTip(tip)
        self._message.setToolTip(tip)

    def start(self, message: str = "", indeterminate: bool = True) -> None:
        """Convenience: set message + start bar and show the widget."""
        self.set_message(message)
        if indeterminate:
            self.set_indeterminate()

    def finish(self) -> None:
        """Reset and hide the widget."""
        self._bar.reset()
        self._message.clear()
        self.setVisible(False)
