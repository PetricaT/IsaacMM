"""Qt data models used by the mod list."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtGui import QStandardItemModel


class FlatDropModel(QStandardItemModel):
    drop_about_to_happen = Signal()

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
        self.drop_about_to_happen.emit()
        return super().dropMimeData(data, action, row, column, parent)
