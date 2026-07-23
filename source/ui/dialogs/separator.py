from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core import config


class SeparatorDialog(QDialog):
    def __init__(
        self,
        title: str,
        name: str = "",
        color: str = "",
        existing_names: Optional[set[str]] = None,
        allow_name: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        # 350, 190
        self.setMinimumSize(350, 130)
        self._color = color or config.separator_color
        self._existing_names = existing_names or set()
        self._allow_name = allow_name

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 6)
        main_layout.setSpacing(6)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)

        self._warning_label = QLabel()
        self._warning_label.setStyleSheet("color: #EAB308;")
        self._warning_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._warning_label.setText(" ")
        self._warning_label.setMinimumHeight(self._warning_label.sizeHint().height())

        self.name_edit = QLineEdit(name)
        self.name_edit.textChanged.connect(self._validate_name)

        self.color_btn = QPushButton()
        self.color_btn.setStyleSheet(
            f"background-color: {self._color}; min-height: 24px; min-width: 60px;"
        )
        self.color_btn.clicked.connect(self._pick_color)

        form_layout.addRow("", self._warning_label)
        form_layout.addRow("Name:", self.name_edit)
        form_layout.addRow("Color:", self.color_btn)

        main_layout.addLayout(form_layout)
        main_layout.addStretch()

        dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok_btn = dialog_buttons.button(QDialogButtonBox.StandardButton.Ok)
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(dialog_buttons)

        self._validate_name(name)

    def _validate_name(self, text: str) -> None:
        name = text.strip()
        if name and name in self._existing_names and name != self._allow_name:
            self._warning_label.setText("\u26A0 A separator with this name already exists!")
            self._ok_btn.setEnabled(False)
        else:
            self._warning_label.setText(" ")
            self._ok_btn.setEnabled(True)

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
