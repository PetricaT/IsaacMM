"""Qt data models used by the mod list."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QStandardItemModel


class FlatDropModel(QStandardItemModel):
    def dropMimeData(
        self,
        data,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        if parent.isValid():
            row = parent.row() + 1
            parent = QModelIndex()
        return super().dropMimeData(data, action, row, column, parent)
