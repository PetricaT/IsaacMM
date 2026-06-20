from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QStandardItemModel


class FlatDropModel(QStandardItemModel):
    def dropMimeData(self, data, action, row, column, parent):
        if parent.isValid():
            row = parent.row() + 1
            parent = QModelIndex()
        return super().dropMimeData(data, action, row, column, parent)
