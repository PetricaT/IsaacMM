from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from ...core import config


class SeparatorDialog(QDialog):
    def __init__(
        self,
        title: str,
        name: str = "",
        color: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._color = color or config.separator_color
        form_layout = QFormLayout(self)

        self.name_edit = QLineEdit(name)

        self.color_btn = QPushButton()
        self.color_btn.setStyleSheet(
            f"background-color: {self._color}; min-height: 24px; min-width: 60px;"
        )
        self.color_btn.clicked.connect(self._pick_color)

        dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)

        form_layout.addRow("Name:", self.name_edit)
        form_layout.addRow("Color:", self.color_btn)
        form_layout.addRow(dialog_buttons)

    def _pick_color(self) -> None:
        selected_color = QColorDialog.getColor(QColor(self._color), self)
        if selected_color.isValid():
            self._color = selected_color.name()
            self.color_btn.setStyleSheet(
                f"background-color: {self._color}; min-height: 24px; min-width: 60px;"
            )

    @property
    def result_name(self) -> str:
        return self.name_edit.text().strip()

    @property
    def result_color(self) -> str:
        return self._color
