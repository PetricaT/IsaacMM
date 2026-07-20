from __future__ import annotations

import os
import shutil

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QMenu, QTreeWidget, QTreeWidgetItem, QWidget

from ...core import logger


class ConflictTreeWidget(QTreeWidget):
    merge_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self._imagediff_path: str | None = None

    def _find_imagediff(self) -> str | None:
        if self._imagediff_path is not None:
            return self._imagediff_path
        candidates = [
            shutil.which("imagediff"),
            os.path.expanduser("~/.local/bin/imagediff"),
            "/usr/local/bin/imagediff",
            "/usr/bin/imagediff",
        ]
        for path in candidates:
            if path and os.path.isfile(path):
                self._imagediff_path = path
                return path
        return None

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self.itemAt(pos)
        if item is None or item.childCount():
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return
        _conflict_folder, relative_path = data
        if not relative_path.lower().endswith(".png"):
            return
        imagediff = self._find_imagediff()
        if imagediff is None:
            logger.log(
                "debug",
                "imagediff not found on PATH (checked PATH, ~/.local/bin, /usr/local/bin, /usr/bin)",
            )
            return
        logger.log("debug", f"imagediff found at {imagediff}")
        menu = QMenu(self)
        action = menu.addAction("Merge with imagediff")
        action.triggered.connect(lambda: self.merge_requested.emit(relative_path))
        menu.exec(self.viewport().mapToGlobal(pos))
