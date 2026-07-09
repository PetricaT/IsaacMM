"""Palette-aware color helpers for native theme integration."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget


def palette_color(
    role: QPalette.ColorRole,
    widget: QWidget | None = None,
    alpha: int = 255,
) -> QColor:
    """Return the palette color for *role*, optionally with alpha."""
    app = QApplication.instance()
    if app is None:
        return QColor(0, 0, 0)
    pal = widget.palette() if widget else app.palette()
    c = pal.color(role)
    if alpha < 255:
        c.setAlpha(alpha)
    return c


def text_color_for_bg(bg: QColor) -> QColor:
    """Return black or white text color for readability on *bg*."""
    l = (0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()) / 255
    return QColor(0, 0, 0) if l > 0.5 else QColor(255, 255, 255)
