"""Standalone status bar widget for the bottom of the window."""

from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QStyle, QWidget

from ...core import config
from ...mods.folder_watcher import ModFolderWatcher
from ...mods.workshop import (
    WORKSHOP_RATE_LIMIT,
    _workshop_limiter_state,
    icon_queue,
)
from ..widgets.progress import StatusBarProgress


class StatusBar(QFrame):
    """Persistent status bar at the bottom of the main window.

    Contains: workshop rate, queue count, progress bar, watcher dot, cooldown timer.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._watcher = None
        self._native_theme = config.active_theme == "System"

        rf = self.fontMetrics()
        self.setFixedHeight(rf.height() + 10)
        if not self._native_theme:
            self.setStyleSheet(
                f"background-color: {config.rate_bar_bg or 'palette(window)'}; "
                f"border: 1px solid {config.console_border or 'palette(mid)'};"
            )

        layout = QHBoxLayout(self)
        margin = self.style().pixelMetric(QStyle.PM_LayoutLeftMargin)
        layout.setContentsMargins(margin, 0, margin, 0)
        layout.setSpacing(0)

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

        layout.addWidget(self.rate_label)
        layout.addWidget(self.queue_label)
        layout.addStretch()

        self._progress = StatusBarProgress()
        layout.addWidget(self._progress)

        self._watcher_dot = QLabel("\u25cf")
        self._watcher_dot.setToolTip("Folder watcher: inactive")
        self._watcher_dot.setStyleSheet("color: palette(mid);")
        layout.addWidget(self._watcher_dot)

        layout.addWidget(self.rate_timer_label)

        self._rate_timer = QTimer(self)
        self._rate_timer.timeout.connect(self._update_rate_bar)
        self._rate_timer.start(1000)
        self._update_rate_bar()

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
