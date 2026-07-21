from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


def scaled_pixmap(
    pm: QPixmap,
    size: int,
    mode: Qt.TransformationMode = Qt.TransformationMode.SmoothTransformation,
) -> QPixmap:
    return pm.scaled(
        size, size, Qt.AspectRatioMode.KeepAspectRatio, mode
    )


def load_scaled_pixmap(
    path: str,
    size: int,
    mode: Qt.TransformationMode = Qt.TransformationMode.SmoothTransformation,
) -> Optional[QPixmap]:
    pm = QPixmap(path)
    if pm.isNull():
        return None
    return scaled_pixmap(pm, size, mode)
