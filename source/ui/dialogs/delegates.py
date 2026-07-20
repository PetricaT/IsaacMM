from __future__ import annotations

import os
from typing import Any, Optional, Protocol, Union

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QTextCharFormat
from PySide6.QtWidgets import QStyledItemDelegate

from ...core import config


def _colorize(old: str, new: str) -> list[tuple[str, Optional[str]]]:
    i = 0
    while i < len(old) and i < len(new) and old[i] == new[i]:
        i += 1
    segments: list[tuple[str, Optional[str]]] = []
    if old:
        segments.append((old[:i], None))
        if old[i:]:
            segments.append((old[i:], config.lose_color))
    segments.append((" \u2192 ", None))
    if new:
        segments.append((new[:i], None))
        if new[i:]:
            segments.append((new[i:], config.win_color))
    return segments


class SettingsPanelOwner(Protocol):
    def log(self, message: str, level: str = "info") -> None: ...
    def log_colored(
        self, segments: list[tuple[str, Optional[str | QTextCharFormat]]]
    ) -> None: ...
    def getModList(self) -> None: ...

    mod_list_panel: Any
    modInfoPanel: Any
    _backup_thread: Any


CONFLICT_ROLE = Qt.ItemDataRole.UserRole + 1  # 257
SEPARATOR_ROLE = Qt.ItemDataRole.UserRole + 2  # 258
PREV_CHECK_ROLE = Qt.ItemDataRole.UserRole + 3  # 259
OVERWRITTEN_ROLE = Qt.ItemDataRole.UserRole + 4  # 260
NORMALIZED_NAME_ROLE = Qt.ItemDataRole.UserRole + 5  # 261
WINS_ROLE = Qt.ItemDataRole.UserRole + 6  # 262
LOSSES_ROLE = Qt.ItemDataRole.UserRole + 7  # 263
EMPTY_ROLE = Qt.ItemDataRole.UserRole + 8  # 264


class ConflictDelegate(QStyledItemDelegate):
    _empty_pixmap: QPixmap | None = None

    @classmethod
    def _get_empty_pixmap(cls) -> QPixmap | None:
        if cls._empty_pixmap is None:
            from ...core import paths

            path = os.path.join(paths.BASE_DIR, "assets", "ui", "empty.png")
            if os.path.exists(path):
                pm = QPixmap(path)
                if not pm.isNull():
                    cls._empty_pixmap = pm.scaled(
                        16,
                        16,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
        return cls._empty_pixmap

    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)
        if index.data(EMPTY_ROLE):
            pm = self._get_empty_pixmap()
            if pm and not pm.isNull():
                item_rect = option.rect
                x = item_rect.right() - pm.width() - 4
                y = item_rect.top() + (item_rect.height() - pm.height()) // 2
                painter.drawPixmap(x, y, pm)
            return
        wins = index.data(WINS_ROLE)
        losses = index.data(LOSSES_ROLE)
        if not wins and not losses:
            return
        from ...core import config

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        font = QFont()
        default_px = QFont().pixelSize()
        font.setPixelSize(default_px + 2 if default_px > 0 else 14)
        font.setBold(True)
        painter.setFont(font)
        item_rect = option.rect
        size = 16
        gap = 2
        if wins and not losses:
            painter.setPen(QColor(config.win_color))
            x = item_rect.right() - size - 4
            y = item_rect.top() + (item_rect.height() - size) // 2
            painter.drawText(QRect(x, y, size, size), Qt.AlignmentFlag.AlignCenter, "+")
        elif losses and not wins:
            painter.setPen(QColor(config.lose_color))
            x = item_rect.right() - size - 4
            y = item_rect.top() + (item_rect.height() - size) // 2
            painter.drawText(
                QRect(x, y, size, size), Qt.AlignmentFlag.AlignCenter, "\u2212"
            )
        else:
            total_w = size * 2 + gap
            x = item_rect.right() - total_w - 4
            y = item_rect.top() + (item_rect.height() - size) // 2
            painter.setPen(QColor(config.lose_color))
            painter.drawText(
                QRect(x, y, size, size), Qt.AlignmentFlag.AlignCenter, "\u2212"
            )
            painter.setPen(QColor(config.win_color))
            painter.drawText(
                QRect(x + size + gap, y, size, size), Qt.AlignmentFlag.AlignCenter, "+"
            )
        painter.restore()
