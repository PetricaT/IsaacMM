import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QStyledItemDelegate,
    QStyleFactory,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import config, logger, paths
from ..backup import backup_all, get_backup_root
from ..worker import WorkerThread
from .file_utils import open_path

CONFLICT_ROLE = Qt.ItemDataRole.UserRole + 1
SEPARATOR_ROLE = Qt.ItemDataRole.UserRole + 2


class ConflictDelegate(QStyledItemDelegate):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        warning_pixmap = QPixmap(os.path.join(paths.BASE_DIR, "assets", "warning.png"))
        self._warning = (
            warning_pixmap.scaled(
                16,
                16,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if not warning_pixmap.isNull() else None
        )

    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)
        if self._warning is None:
            return
        if not index.data(CONFLICT_ROLE):
            return
        item_rect = option.rect
        icon_x = item_rect.right() - self._warning.width() - 4
        icon_y = item_rect.top() + (item_rect.height() - self._warning.height()) // 2
        painter.drawPixmap(icon_x, icon_y, self._warning)


class SeparatorDialog(QDialog):
    def __init__(
        self, title: str, name: str = "", color: str = "#888888", parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._color = color
        form_layout = QFormLayout(self)

        self.name_edit = QLineEdit(name)

        self.color_btn = QPushButton()
        self.color_btn.setStyleSheet(
            f"background-color: {color}; min-height: 24px; min-width: 60px;"
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


class SettingsDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.setMinimumHeight(395)

        main_layout = QVBoxLayout(self)
        tabs = QTabWidget()

        behavior_tab = QWidget()
        behavior_layout = QVBoxLayout(behavior_tab)

        setup_group = QGroupBox("Setup")
        setup_layout = QFormLayout(setup_group)
        mods_path_layout = QHBoxLayout()
        self.mods_path_edit = QLineEdit()
        detected_mods = paths.find_isaac_mods_folder() or ""
        self.mods_path_edit.setPlaceholderText(detected_mods if detected_mods else "(not set)")
        if config.mods_path == detected_mods or not config.mods_path:
            self.mods_path_edit.setText("")
        else:
            self.mods_path_edit.setText(config.mods_path)
        self.mods_path_edit.editingFinished.connect(self._save_settings)
        self.mods_path_edit.textChanged.connect(self._update_open_buttons)
        browse_mods_btn = QPushButton("Browse...")
        browse_mods_btn.clicked.connect(self._pick_mods_path)
        self.open_mods_btn = QPushButton("\u2197")
        self.open_mods_btn.setFixedWidth(28)
        self.open_mods_btn.clicked.connect(self._open_mods_folder)
        mods_path_layout.addWidget(self.mods_path_edit, 1)
        mods_path_layout.addWidget(browse_mods_btn)
        mods_path_layout.addWidget(self.open_mods_btn)
        setup_layout.addRow("Mods folder:", mods_path_layout)
        behavior_layout.addWidget(setup_group)

        backup_group = QGroupBox("Backup")
        backup_layout = QFormLayout(backup_group)
        self.backup_check = QCheckBox("Back up mods on apply / auto-sort")
        self.backup_check.setChecked(config.backup_enabled)
        self.backup_check.toggled.connect(self._save_settings)
        backup_layout.addRow(self.backup_check)

        backup_path_layout = QHBoxLayout()
        self.backup_path_edit = QLineEdit()
        default_backup = get_backup_root(config.mods_path) if config.mods_path else ""
        self.backup_path_edit.setPlaceholderText(default_backup)
        self.backup_path_edit.setText(config.backup_path or "")
        self.backup_path_edit.editingFinished.connect(self._save_settings)
        self.backup_path_edit.textChanged.connect(self._update_open_buttons)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._pick_backup_path)
        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(self._reset_path)
        self.open_backup_btn = QPushButton("\u2197")
        self.open_backup_btn.setFixedWidth(28)
        self.open_backup_btn.clicked.connect(self._open_backup_folder)
        backup_path_layout.addWidget(self.backup_path_edit, 1)
        backup_path_layout.addWidget(browse_button)
        backup_path_layout.addWidget(reset_button)
        backup_path_layout.addWidget(self.open_backup_btn)
        backup_layout.addRow("Backup location:", backup_path_layout)

        run_backup_button = QPushButton("Run backup now")
        run_backup_button.clicked.connect(self._run_backup)
        backup_layout.addRow(run_backup_button)
        behavior_layout.addWidget(backup_group)

        display_group = QGroupBox("Display")
        display_layout = QFormLayout(display_group)
        self.animate_check = QCheckBox("Animate mod icons (GIF)")
        self.animate_check.setChecked(config.animate_icons)
        self.animate_check.toggled.connect(self._save_settings)
        display_layout.addRow(self.animate_check)

        self.preview_check = QCheckBox("Image tooltip preview")
        self.preview_check.setChecked(config.preview_images)
        self.preview_check.toggled.connect(self._save_settings)
        display_layout.addRow(self.preview_check)

        self.download_icons_check = QCheckBox("Download missing icons from workshop")
        self.download_icons_check.setChecked(config.download_icons)
        self.download_icons_check.toggled.connect(self._save_settings)
        display_layout.addRow(self.download_icons_check)
        behavior_layout.addWidget(display_group)

        logging_group = QGroupBox("Logging")
        logging_layout = QFormLayout(logging_group)
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItem("Debug", "debug")
        self.log_level_combo.addItem("Info", "info")
        self.log_level_combo.addItem("Warning", "warning")
        self.log_level_combo.addItem("Error", "error")
        index = self.log_level_combo.findData(config.log_level)
        if index >= 0:
            self.log_level_combo.setCurrentIndex(index)
        self.log_level_combo.currentIndexChanged.connect(self._save_settings)
        logging_layout.addRow("Log level:", self.log_level_combo)
        behavior_layout.addWidget(logging_group)

        behavior_layout.addStretch()
        tabs.addTab(behavior_tab, "Behavior")

        theme_tab = QWidget()
        theme_layout = QFormLayout(theme_tab)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Fusion", "fusion")
        self.theme_combo.addItem("Native (platform default)", "native")
        for style_key in QStyleFactory.keys():
            lower = style_key.lower()
            if lower not in ("fusion",):
                self.theme_combo.addItem(style_key, lower)
        index = self.theme_combo.findData(config.theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        self.theme_combo.currentIndexChanged.connect(self._save_settings)

        self.accent_btn = QPushButton()
        self.accent_btn.setFixedWidth(60)
        self.accent_btn.setStyleSheet(f"background-color: {config.accent_color};")
        self.accent_btn.clicked.connect(self._pick_accent)

        theme_layout.addRow("Theme:", self.theme_combo)
        theme_layout.addRow("Accent color:", self.accent_btn)
        tabs.addTab(theme_tab, "Theme")

        main_layout.addWidget(tabs)
        self._update_open_buttons()

    def _pick_accent(self) -> None:
        color = QColorDialog.getColor(QColor(config.accent_color), self)
        if color.isValid():
            config.accent_color = color.name()
            self.accent_btn.setStyleSheet(f"background-color: {config.accent_color};")
            self._save_settings()
            owner_window = self.parentWidget()
            if owner_window is not None:
                update_style = getattr(owner_window, "update_accent_style", None)
                if callable(update_style):
                    update_style(color.name())

    def _pick_mods_path(self) -> None:
        starting = config.mods_path if config.mods_path and os.path.isdir(config.mods_path) else ""
        folder = QFileDialog.getExistingDirectory(self, "Select Mods Folder", starting)
        if folder:
            self.mods_path_edit.setText(folder)
            self._save_settings()

    def _pick_backup_path(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select backup folder")
        if folder:
            if "backup" not in os.path.basename(folder).lower():
                folder = os.path.join(folder, "backup")
                os.makedirs(folder, exist_ok=True)
            self.backup_path_edit.setText(folder)
            self._save_settings()

    def _update_open_buttons(self) -> None:
        mods_folder = self.mods_path_edit.text().strip()
        if not mods_folder:
            mods_folder = paths.find_isaac_mods_folder() or ""
        self.open_mods_btn.setEnabled(bool(mods_folder) and os.path.isdir(mods_folder))

        backup_folder = self.backup_path_edit.text().strip()
        if not backup_folder:
            backup_folder = get_backup_root(config.mods_path) if config.mods_path else ""
        self.open_backup_btn.setEnabled(bool(backup_folder) and os.path.isdir(backup_folder))

    def _open_mods_folder(self) -> None:
        folder = self.mods_path_edit.text().strip()
        if not folder:
            detected = paths.find_isaac_mods_folder()
            folder = detected or ""
        if folder and os.path.isdir(folder):
            open_path(folder)

    def _open_backup_folder(self) -> None:
        folder = self.backup_path_edit.text().strip()
        if not folder:
            folder = get_backup_root(config.mods_path) if config.mods_path else ""
        if folder and os.path.isdir(folder):
            open_path(folder)

    def _reset_path(self) -> None:
        self.backup_path_edit.clear()
        self._save_settings()

    def _save_settings(self) -> None:
        prev_backup = config.backup_enabled
        prev_mods = config.mods_path
        config.backup_enabled = self.backup_check.isChecked()
        text = self.backup_path_edit.text().strip()
        config.backup_path = text if text else None
        config.animate_icons = self.animate_check.isChecked()
        config.preview_images = self.preview_check.isChecked()
        config.download_icons = self.download_icons_check.isChecked()
        config.log_level = self.log_level_combo.currentData()
        mods_text = self.mods_path_edit.text().strip()
        if mods_text:
            config.mods_path = mods_text
        else:
            detected = paths.find_isaac_mods_folder()
            config.mods_path = detected or config.mods_path
        new_theme = self.theme_combo.currentData()
        if new_theme != config.theme:
            config.theme = new_theme
            app = QApplication.instance()
            if app:
                style_name = getattr(config, "_native_style", None) if new_theme == "native" else new_theme
                if style_name:
                    app.setStyle(style_name)
        if config.mods_path != prev_mods:
            owner_window = self.parent()
            if owner_window and hasattr(owner_window, 'getModList'):
                owner_window.getModList()
        owner_window = self.parent()
        if owner_window and hasattr(owner_window, 'log') and config.backup_enabled != prev_backup:
            owner_window.log(f"Backup {'enabled' if config.backup_enabled else 'disabled'}")
        self._update_open_buttons()
        config.save()

    def _run_backup(self) -> None:
        if not config.mods_path:
            return
        owner_window = self.parent()
        if hasattr(owner_window, '_backup_thread') and owner_window._backup_thread:
            return
        if owner_window and hasattr(owner_window, 'log'):
            owner_window.log("Running manual backup...")

        def _colorize(old: str, new: str) -> list[tuple[str, Optional[str]]]:
            i = 0
            while i < len(old) and i < len(new) and old[i] == new[i]:
                i += 1
            segments: list[tuple[str, Optional[str]]] = []
            if old:
                segments.append((old[:i], None))
                if old[i:]:
                    segments.append((old[i:], "#9E4D4D"))
            segments.append((" \u2192 ", None))
            if new:
                segments.append((new[:i], None))
                if new[i:]:
                    segments.append((new[i:], "#65A665"))
            return segments

        def _on_finished(results: list[tuple[str, str, str]]) -> None:
            for mod_name, old_ver, new_ver in results:
                if old_ver == "?":
                    log_colored = getattr(owner_window, 'log_colored', None)
                    if log_colored:
                        log_colored([("Added: ", None), (mod_name, "#65A665")])
                    continue
                if old_ver == new_ver:
                    continue
                segments = [(f"{mod_name}: ", None)]
                segments.extend(_colorize(old_ver, new_ver))
                log_colored = getattr(owner_window, 'log_colored', None)
                if log_colored:
                    log_colored(segments)
            if owner_window and hasattr(owner_window, 'log'):
                owner_window.log("Manual backup complete")

        def _on_error(error_msg: str) -> None:
            if owner_window and hasattr(owner_window, 'log'):
                owner_window.log(f"Backup failed: {error_msg}", "error")

        thread = WorkerThread(
            backup_all,
            config.mods_path,
            get_backup_root(config.mods_path),
            config.loaded_mods,
        )
        thread.finished.connect(_on_finished)
        thread.error.connect(_on_error)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(owner_window, '_backup_thread', None))
        owner_window._backup_thread = thread
        thread.start()
