import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QSettings, Qt, QThread, QTimer, QUrl
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QPalette,
    QPixmap,
    QStandardItem,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStyledItemDelegate,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

CONFLICT_ROLE = Qt.UserRole + 1
SEPARATOR_ROLE = Qt.UserRole + 2
SEPARATOR_SUFFIX = "_separator"


class ConflictDelegate(QStyledItemDelegate):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        warning_pixmap = QPixmap(os.path.join(paths.BASE_DIR, "assets", "warning.png"))
        self._warning = (
            warning_pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
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

        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
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


from . import config, logger, paths, sorter
from .backup import get_backup_root
from .models import FlatDropModel
from .widgets import ModInfoPanel, _init_workshop_limiter, _workshop_limiter_state, _sync_workshop_limiter, WORKSHOP_RATE_LIMIT

sorted_pattern = re.compile(r"[0-9]{3}\s.*")


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
        browse_mods_btn = QPushButton("Browse...")
        browse_mods_btn.clicked.connect(self._pick_mods_path)
        mods_path_layout.addWidget(self.mods_path_edit, 1)
        mods_path_layout.addWidget(browse_mods_btn)
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
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._pick_backup_path)
        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(self._reset_path)
        backup_path_layout.addWidget(self.backup_path_edit, 1)
        backup_path_layout.addWidget(browse_button)
        backup_path_layout.addWidget(reset_button)
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
        from PySide6.QtWidgets import QStyleFactory
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

    def _pick_accent(self) -> None:
        color = QColorDialog.getColor(QColor(config.accent_color), self)
        if color.isValid():
            config.accent_color = color.name()
            self.accent_btn.setStyleSheet(f"background-color: {config.accent_color};")
            self._save_settings()
            owner_window = self.parent()
            if owner_window and hasattr(owner_window, 'listView'):
                owner_window.listView.setStyleSheet(
                    f"QListView::item:selected {{ background-color: {config.accent_color}; }}"
                )
                owner_window.applyOrder.setStyleSheet(
                    f"background-color : {config.accent_color}"
                )

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
        config.save()

    def _run_backup(self) -> None:
        if not config.mods_path:
            return
        owner_window = self.parent()
        if hasattr(owner_window, '_backup_thread') and owner_window._backup_thread:
            return
        if owner_window and hasattr(owner_window, 'log'):
            owner_window.log("Running manual backup...")

        from .backup import backup_all, get_backup_root
        from .worker import WorkerThread

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
                    if owner_window and hasattr(owner_window, 'log_colored'):
                        owner_window.log_colored([("Added: ", None), (mod_name, "#65A665")])
                    continue
                if old_ver == new_ver:
                    continue
                segments = [(f"{mod_name}: ", None)]
                segments.extend(_colorize(old_ver, new_ver))
                if owner_window and hasattr(owner_window, 'log_colored'):
                    owner_window.log_colored(segments)
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


class DragApp(QWidget):
    loaded_mods = config.loaded_mods

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle(f"Tboi Mod Manager [{paths.version}]")
        s = config.get_settings()
        geom = s.value("ui/window_geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
            self.resize(1161, 550)
        self.pending_toggles: dict = {}
        self._mod_files_cache: dict = {}
        self._populating: bool = False
        self._first_load: bool = True

        _init_workshop_limiter()
        self.initUi()

    def closeEvent(self, close_event) -> None:
        s = config.get_settings()
        s.setValue("ui/window_geometry", self.saveGeometry())
        s.setValue("ui/splitter_state", self._splitter.saveState())
        s.setValue("ui/column_state", self.modInfoPanel.conflicts_tree.header().saveState())
        _sync_workshop_limiter()
        config.save()
        super().closeEvent(close_event)

    def initUi(self) -> None:
        self.baseLayout = QVBoxLayout(self)
        self.console = QPlainTextEdit(self)
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Courier New", 9))
        self.console.setFixedHeight(100)
        self.console.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #333;"
        )
        logger.set_handler(lambda lvl, msg: self._write_console(msg, lvl))

        self.rate_bar = QFrame(self)
        self.rate_bar.setFixedHeight(24)
        self.rate_bar.setStyleSheet(
            "background-color: #252526; border: 1px solid #333; border-top: none;"
        )
        rate_layout = QHBoxLayout(self.rate_bar)
        rate_layout.setContentsMargins(8, 0, 8, 0)
        rate_layout.setSpacing(0)
        self.rate_label = QLabel("Workshop: 0/5")
        self.rate_label.setStyleSheet("color: #d4d4d4; font-size: 11px;")
        self.rate_timer_label = QLabel("—")
        self.rate_timer_label.setStyleSheet("color: #d4d4d4; font-size: 11px;")
        rate_layout.addWidget(self.rate_label)
        rate_layout.addStretch()
        rate_layout.addWidget(self.rate_timer_label)

        self._rate_timer = QTimer(self)
        self._rate_timer.timeout.connect(self._update_rate_bar)
        self._rate_timer.start(1000)
        self._update_rate_bar()
        self.modListWidget()
        self.modInfoPanel = ModInfoPanel()
        self.modInfoPanel.log_message.connect(self.log)

        left_panel = QWidget()
        left_panel_layout = QVBoxLayout(left_panel)
        left_panel_layout.setContentsMargins(0, 0, 0, 0)

        modlist_header_layout = QHBoxLayout()
        modlist_label = QLabel("<b>Mod List</b>")
        modlist_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        menu_button = QPushButton("☰")
        menu_button.setFixedWidth(30)
        overflow_menu = QMenu(menu_button)
        overflow_menu.addAction("Add Separator", self._create_separator)
        overflow_menu.addAction("Export modlist (.csv)", self._export_modlist)
        overflow_menu.addAction("Import modlist (.csv)", self._import_modlist)
        menu_button.setMenu(overflow_menu)
        modlist_header_layout.addWidget(modlist_label, 1)
        modlist_header_layout.addWidget(menu_button)
        left_panel_layout.addLayout(modlist_header_layout)

        left_panel_layout.addWidget(self.listView, 1)

        button_row = QHBoxLayout()
        button_row.addWidget(self.applyOrder)
        button_row.addWidget(self.autoSort)
        button_row.addWidget(self.restoreOrder)
        button_row.addStretch()
        button_row.addWidget(self.settingsBtn)
        left_panel_layout.addLayout(button_row)

        horizontal_splitter = QSplitter(Qt.Horizontal)
        horizontal_splitter.addWidget(left_panel)
        horizontal_splitter.addWidget(self.modInfoPanel)
        horizontal_splitter.setStretchFactor(0, 1)
        horizontal_splitter.setStretchFactor(1, 1)
        s = config.get_settings()
        splitter_state = s.value("ui/splitter_state")
        if splitter_state:
            horizontal_splitter.restoreState(splitter_state)
        self._splitter = horizontal_splitter
        self.baseLayout.addWidget(horizontal_splitter, 1)

        self.baseLayout.addWidget(self.console)
        self.baseLayout.addWidget(self.rate_bar)

        self.applyOrder.clicked.connect(self.applyModOrder)
        self.autoSort.clicked.connect(self.autoSortMods)
        self.restoreOrder.clicked.connect(self.restoreLastOrder)
        self.listView.selectionModel().selectionChanged.connect(
            self.on_mod_selected
        )

        column_state = s.value("ui/column_state")
        if column_state:
            self.modInfoPanel.restore_column_state(column_state)

    def modListWidget(self) -> None:
        self.accent_color = self._get_accent_color_hex()
        self.listView = QListView(self)
        self.listView.setStyleSheet(
            f"QListView::item:selected {{ background-color: {self.accent_color}; }}"
        )
        self.listView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.listView.setDragEnabled(True)
        self.listView.setAcceptDrops(True)
        self.listView.setDropIndicatorShown(True)
        self.listView.setDragDropMode(QAbstractItemView.InternalMove)
        self.listView.setDefaultDropAction(Qt.MoveAction)
        self.listView.setAlternatingRowColors(True)
        current_palette = self.listView.palette()
        base_color = current_palette.color(QPalette.Base)
        alternate_color = (
            base_color.lighter(120) if base_color.lightness() < 128
            else base_color.darker(108)
        )
        current_palette.setColor(QPalette.AlternateBase, alternate_color)
        self.listView.setPalette(current_palette)

        self.model = FlatDropModel()
        self.listView.setModel(self.model)
        self.listView.setItemDelegate(ConflictDelegate(self.listView))
        self.model.itemChanged.connect(self.on_item_changed)
        self.model.rowsInserted.connect(self._on_rows_inserted)

        self.applyOrder = QPushButton("Apply Sort Order")
        self.autoSort = QPushButton("Auto Sort")
        self.restoreOrder = QPushButton("Restore Last Order")
        self.restoreOrder.setEnabled(sorter.load_last_order() is not None)
        self.settingsBtn = QPushButton("Settings")
        self.settingsBtn.clicked.connect(self._open_settings)
        self.listView.doubleClicked.connect(self._on_item_double_clicked)
        self.listView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listView.customContextMenuRequested.connect(self._on_context_menu)

        self.getModList()
        self.applyOrder.setStyleSheet(f"background-color : {self.accent_color}")

    def applyModOrder(self) -> None:
        self.log("Applying sort order...")
        sort_index = 1
        ordered_folders = []
        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            mod_folder = list_item.data(Qt.UserRole)
            ordered_folders.append(mod_folder)
            if list_item.data(SEPARATOR_ROLE):
                continue
            mod_name = list_item.text()
            if sorted_pattern.match(mod_name):
                new_name = f"{sort_index:03} {mod_name[4:]}"
            else:
                new_name = f"{sort_index:03} {mod_name}"
            try:
                metadata_tree = ET.parse(
                    f"{config.mods_path}/{mod_folder}/metadata.xml"
                )
                xml_root = metadata_tree.getroot()
                xml_root.find("name").text = new_name
                metadata_tree.write(
                    f"{config.mods_path}/{mod_folder}/metadata.xml",
                    encoding="utf-8",
                    xml_declaration=True,
                )
                sort_index += 1
            except Exception as exception:
                self.log(f"Writing {mod_folder}: {exception}", "error")
        for folder_name, toggle_state in self.pending_toggles.items():
            disable_file_path = os.path.join(
                config.mods_path, folder_name, "disable.it"
            )
            if toggle_state == Qt.Unchecked:
                try:
                    open(disable_file_path, "a").close()
                except OSError as exception:
                    self.log(f"Disabling {folder_name}: {exception}", "error")
            else:
                try:
                    os.remove(disable_file_path)
                except FileNotFoundError:
                    pass
                except OSError as exception:
                    self.log(f"Enabling {folder_name}: {exception}", "error")
        self.pending_toggles.clear()
        sorter.save_last_order(ordered_folders)
        self.log(f"Applied order for {sort_index - 1} mods")
        self.getModList()

    def restoreLastOrder(self) -> None:
        folder_order = sorter.load_last_order()
        if not folder_order:
            self.log("No saved order to restore")
            return
        self.log("Restoring last saved order...")
        sort_index = 1
        for mod_folder in folder_order:
            if mod_folder.endswith(SEPARATOR_SUFFIX):
                continue
            xml_path = os.path.join(config.mods_path, mod_folder, "metadata.xml")
            if not os.path.exists(xml_path):
                self.log(f"{mod_folder} no longer exists, skipping", "warning")
                continue
            metadata_tree = ET.parse(xml_path)
            xml_root = metadata_tree.getroot()
            mod_name = xml_root.find("name").text
            if sorted_pattern.match(mod_name):
                mod_name = mod_name[4:]
            xml_root.find("name").text = f"{sort_index:03} {mod_name}"
            metadata_tree.write(xml_path, encoding="utf-8", xml_declaration=True)
            sort_index += 1
        self.log(f"Restored order for {sort_index - 1} mods")
        self.getModList()

    def log(self, message: str, level: str = "info") -> None:
        logger.log(level, message)

    def _write_console(self, message: str, level: str = "info") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_colors = {"info": "#d4d4d4", "warning": "#ffa500", "error": "#ff4444"}
        log_color = level_colors.get(level, "#d4d4d4")
        text_cursor = self.console.textCursor()
        text_cursor.movePosition(QTextCursor.MoveOperation.End)
        char_format = QTextCharFormat()
        char_format.setForeground(QColor(log_color))
        text_cursor.insertText(f"[{timestamp}] {message}\n", char_format)
        self.console.setTextCursor(text_cursor)
        self.console.ensureCursorVisible()

    def log_colored(self, segments: list[tuple[str, Optional[str]]]) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        text_cursor = self.console.textCursor()
        text_cursor.movePosition(QTextCursor.MoveOperation.End)
        char_format = QTextCharFormat()
        char_format.setForeground(QColor("#d4d4d4"))
        text_cursor.insertText(f"[{timestamp}] ", char_format)
        for text, color in segments:
            if color:
                char_format.setForeground(QColor(color))
            else:
                char_format.setForeground(QColor("#d4d4d4"))
            text_cursor.insertText(text, char_format)
        text_cursor.insertText("\n", char_format)
        self.console.setTextCursor(text_cursor)
        self.console.ensureCursorVisible()

    def _update_rate_bar(self) -> None:
        count, next_available = _workshop_limiter_state()
        self.rate_label.setText(f"Workshop: {count}/{WORKSHOP_RATE_LIMIT}")
        if next_available is not None:
            remaining = int(next_available - time.time())
            if remaining > 0:
                mins, secs = divmod(remaining, 60)
                self.rate_timer_label.setText(f"Cooldown: {mins}m {secs}s")
                self.rate_timer_label.setStyleSheet("color: #ffa500; font-size: 11px;")
            else:
                self.rate_timer_label.setText("—")
                self.rate_timer_label.setStyleSheet("color: #d4d4d4; font-size: 11px;")
        else:
            self.rate_timer_label.setText("—")
            self.rate_timer_label.setStyleSheet("color: #d4d4d4; font-size: 11px;")

    def getModList(self) -> None:
        if config.mods_path == "":
            self.log("No mods folder set — open Settings to configure one", "warning")
            return

        self._populating = True
        self.model.clear()
        self.pending_toggles.clear()
        self._mod_files_cache.clear()
        config.loaded_mods.clear()

        all_entries = []
        separator_map = {}

        try:
            directory_entries = os.listdir(config.mods_path)
        except OSError as exc:
            self.log(f"Failed to list mods folder: {exc}", "error")
            self._populating = False
            return

        for directory_entry in directory_entries:
            if directory_entry in (".DS_Store", "Thumbs.db"):
                continue
            full_path = os.path.join(config.mods_path, directory_entry)
            if not os.path.isdir(full_path):
                continue

            if directory_entry.endswith(SEPARATOR_SUFFIX):
                separator_xml_path = os.path.join(full_path, "separator.xml")
                try:
                    metadata_tree = ET.parse(separator_xml_path)
                    xml_root = metadata_tree.getroot()
                    separator_name = xml_root.find("name").text
                    color_element = xml_root.find("color")
                    separator_color = (
                        color_element.text if color_element is not None else "#888888"
                    )
                except Exception:
                    separator_name = directory_entry[: -len(SEPARATOR_SUFFIX)]
                    separator_color = "#888888"
                all_entries.append((separator_name, directory_entry))
                separator_map[directory_entry] = separator_color
                continue

            try:
                metadata_tree = ET.parse(
                    os.path.join(full_path, "metadata.xml")
                )
                xml_root = metadata_tree.getroot()
                mod_name = xml_root.find("name").text
                config.loaded_mods.append([mod_name, directory_entry])
                all_entries.append((mod_name, directory_entry))
            except FileNotFoundError:
                continue

        saved_folder_order = sorter.load_last_order()
        if saved_folder_order:
            entries_by_folder = {folder: (name, folder) for name, folder in all_entries}
            ordered_entries = []
            for folder_name in saved_folder_order:
                if folder_name in entries_by_folder:
                    ordered_entries.append(entries_by_folder.pop(folder_name))
            ordered_entries.extend(entries_by_folder.values())
            all_entries = ordered_entries
        else:
            all_entries.sort(key=lambda entry: entry[0].lower())

        for entry_name, entry_folder in all_entries:
            list_item = QStandardItem(entry_name)
            list_item.setData(entry_folder, Qt.UserRole)
            if entry_folder in separator_map:
                separator_color = separator_map[entry_folder]
                list_item.setData(
                    {"name": entry_name, "color": separator_color}, SEPARATOR_ROLE
                )
                list_item.setBackground(QColor(separator_color))
                list_item.setTextAlignment(Qt.AlignCenter)
            else:
                list_item.setCheckable(True)
                disable_file_path = os.path.join(
                    config.mods_path, entry_folder, "disable.it"
                )
                list_item.setCheckState(
                    Qt.Unchecked if os.path.exists(disable_file_path) else Qt.Checked
                )
            self.model.appendRow(list_item)

        self._populating = False
        if self._first_load:
            self._first_load = False
            self.log(
                f"Loaded {len(config.loaded_mods)} mods, {len(separator_map)} separators"
            )
        self._maybe_backup()
        self._update_conflict_indicators()

    def _on_rows_inserted(self, parent, first_row: int, last_row: int) -> None:
        if self._populating:
            return
        QTimer.singleShot(0, self._update_conflict_indicators)

    def _update_conflict_indicators(self) -> None:
        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            if list_item is None:
                continue
            list_item.setData(None, CONFLICT_ROLE)
            separator_data = list_item.data(SEPARATOR_ROLE)
            if separator_data:
                list_item.setBackground(QColor(separator_data["color"]))
                list_item.setTextAlignment(Qt.AlignCenter)

        for first_index in range(self.model.rowCount()):
            first_item = self.model.item(first_index)
            if first_item is None or first_item.data(SEPARATOR_ROLE):
                continue
            for second_index in range(first_index + 1, self.model.rowCount()):
                second_item = self.model.item(second_index)
                if second_item is None or second_item.data(SEPARATOR_ROLE):
                    continue
                common_files = (
                    self._scan_mod_files(first_item.data(Qt.UserRole))
                    & self._scan_mod_files(second_item.data(Qt.UserRole))
                )
                if not common_files:
                    continue
                first_item.setData(True, CONFLICT_ROLE)
                second_item.setData(True, CONFLICT_ROLE)

    def on_mod_selected(self, selected, deselected) -> None:
        if self._populating:
            return

        selected_indexes = self.listView.selectedIndexes()

        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            if list_item.data(SEPARATOR_ROLE):
                separator_data = list_item.data(SEPARATOR_ROLE)
                list_item.setBackground(QColor(separator_data["color"]))
            else:
                list_item.setBackground(QBrush())

        if not selected_indexes:
            self.modInfoPanel.clear()
            return

        selected_item = self.model.itemFromIndex(selected_indexes[0])

        separator_data = selected_item.data(SEPARATOR_ROLE)
        if separator_data:
            self.modInfoPanel.clear()
            separator_folder = selected_item.data(Qt.UserRole)
            self.modInfoPanel._mod_path = os.path.join(
                config.mods_path, separator_folder
            )
            self.modInfoPanel.folder_button.setEnabled(True)
            self.modInfoPanel.folder_label.setText(
                f"Separator: {separator_data['name']} (folder: {separator_folder})"
            )
            return

        mod_folder = selected_item.data(Qt.UserRole)
        current_mod_files = self._scan_mod_files(mod_folder)
        current_mod_index = next(
            (
                index
                for index in range(self.model.rowCount())
                if self.model.item(index).data(Qt.UserRole) == mod_folder
            ),
            -1,
        )

        conflict_mods = {}
        for row_index in range(self.model.rowCount()):
            other_item = self.model.item(row_index)
            other_mod_folder = other_item.data(Qt.UserRole)
            if other_mod_folder == mod_folder:
                continue
            common_files = current_mod_files & self._scan_mod_files(other_mod_folder)
            if not common_files:
                continue
            conflict_mods[other_item.text()] = {
                "folder": other_mod_folder,
                "files": sorted(common_files),
                "overwrites": row_index > current_mod_index,
            }
            if row_index < current_mod_index:
                other_item.setBackground(QColor("#9E4D4D"))
            else:
                other_item.setBackground(QColor("#65A665"))

        self.modInfoPanel.show_mod_info(
            selected_item.text(),
            selected_item.data(Qt.UserRole),
            selected_item.checkState(),
            conflict_mods,
        )

    _CONFLICT_EXTS = {'.png', '.anm2', '.wav', '.lua'}

    def _scan_mod_files(self, mod_folder_name: str) -> set:
        cached_files = self._mod_files_cache.get(mod_folder_name)
        if cached_files is not None:
            return cached_files
        conflict_files = set()
        full_mod_path = os.path.join(config.mods_path, mod_folder_name)
        try:
            for walk_root, walk_dirs, file_names in os.walk(full_mod_path):
                walk_dirs[:] = [
                    directory
                    for directory in walk_dirs
                    if directory not in ('.git', '__pycache__')
                ]
                for file_name in file_names:
                    if file_name in (
                        'metadata.xml', 'disable.it', '.DS_Store', 'Thumbs.db'
                    ):
                        continue
                    file_extension = os.path.splitext(file_name)[1].lower()
                    if file_extension not in self._CONFLICT_EXTS:
                        continue
                    relative_path = os.path.relpath(
                        os.path.join(walk_root, file_name), full_mod_path
                    )
                    if '/' in relative_path or '\\' in relative_path:
                        conflict_files.add(relative_path)
        except OSError as exc:
            self.log(f"Failed to scan mod files for {mod_folder_name}: {exc}", "warning")
        self._mod_files_cache[mod_folder_name] = conflict_files
        return conflict_files

    def on_item_changed(self, list_item) -> None:
        if self._populating:
            return
        mod_folder = list_item.data(Qt.UserRole)
        if mod_folder:
            self.pending_toggles[mod_folder] = list_item.checkState()

    def autoSortMods(self) -> None:
        self.log("Running auto-sort...")
        mod_data_list = []
        separators = []
        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            separator_data = list_item.data(SEPARATOR_ROLE)
            if separator_data:
                separators.append(
                    {
                        "name": list_item.text(),
                        "folder": list_item.data(Qt.UserRole),
                        "color": separator_data["color"],
                        "index": len(mod_data_list),
                    }
                )
            else:
                mod_data_list.append(
                    {
                        "name": list_item.text(),
                        "folder": list_item.data(Qt.UserRole),
                        "checked": list_item.checkState(),
                    }
                )

        auto_sorted_mods = sorter.auto_sort(
            [[mod["name"], mod["folder"]] for mod in mod_data_list],
            config.mods_path,
        )

        self._populating = True
        self.model.clear()
        self._mod_files_cache.clear()

        ordered_list = list(auto_sorted_mods)
        for separator_entry in separators:
            insert_position = min(separator_entry["index"], len(ordered_list))
            ordered_list.insert(
                insert_position, (separator_entry["name"], separator_entry["folder"])
            )

        mod_data_lookup = {mod["folder"]: mod for mod in mod_data_list}
        separator_lookup = {sep["folder"]: sep for sep in separators}
        for entry_name, entry_folder in ordered_list:
            if entry_folder in separator_lookup:
                separator_entry = separator_lookup[entry_folder]
                list_item = QStandardItem(entry_name)
                list_item.setData(entry_folder, Qt.UserRole)
                list_item.setData(
                    {"name": entry_name, "color": separator_entry["color"]},
                    SEPARATOR_ROLE,
                )
                list_item.setBackground(QColor(separator_entry["color"]))
                list_item.setTextAlignment(Qt.AlignCenter)
            else:
                mod_info = mod_data_lookup.get(entry_folder, {})
                list_item = QStandardItem(entry_name)
                list_item.setCheckable(True)
                list_item.setCheckState(mod_info.get("checked", Qt.Checked))
                list_item.setData(entry_folder, Qt.UserRole)
            self.model.appendRow(list_item)

        config.loaded_mods = [
            [entry_name, entry_folder]
            for entry_name, entry_folder in ordered_list
            if entry_folder not in separator_lookup
        ]
        self._populating = False
        self.log(f"Auto-sort complete ({len(config.loaded_mods)} mods)")
        self._maybe_backup()
        self._update_conflict_indicators()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.exec()

    def _maybe_backup(self) -> None:
        if not config.backup_enabled or not config.mods_path:
            return
        if hasattr(self, '_backup_thread') and self._backup_thread:
            return
        self.log("Backing up modified mods...")
        from .backup import backup_all, get_backup_root
        from .worker import WorkerThread

        thread = WorkerThread(
            backup_all,
            config.mods_path,
            get_backup_root(config.mods_path),
            config.loaded_mods,
        )
        thread.finished.connect(lambda: self.log("Backup complete"))
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, '_backup_thread', None))
        self._backup_thread = thread
        thread.start()

    def _create_separator(self) -> None:
        dialog = SeparatorDialog("Create Separator", parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        separator_name = dialog.result_name
        separator_color = dialog.result_color
        if not separator_name:
            return
        separator_folder = f"{separator_name}{SEPARATOR_SUFFIX}"
        separator_folder_path = os.path.join(config.mods_path, separator_folder)
        try:
            os.makedirs(separator_folder_path, exist_ok=True)
            xml_root = ET.Element("separator")
            ET.SubElement(xml_root, "name").text = separator_name
            ET.SubElement(xml_root, "color").text = separator_color
            xml_tree = ET.ElementTree(xml_root)
            xml_tree.write(
                os.path.join(separator_folder_path, "separator.xml"),
                encoding="utf-8",
                xml_declaration=True,
            )
            self.log(f"Created separator '{separator_name}'")
            self._save_current_order()
            self.getModList()
        except OSError as exception:
            self.log(f"Creating separator: {exception}", "error")

    def _export_modlist(self) -> None:
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export Modlist", "", "CSV files (*.csv);;All files (*)"
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".csv") and "*.csv" in selected_filter:
            file_path += ".csv"
        items = []
        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            if list_item.data(SEPARATOR_ROLE):
                continue
            items.append((list_item.data(Qt.UserRole), list_item.text()))
        try:
            from .modlist_io import export_modlist_csv
            count = export_modlist_csv(file_path, items)
            self.log(f"Exported {count} mods to {file_path}")
        except OSError as exception:
            self.log(f"Exporting modlist: {exception}", "error")

    def _import_modlist(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Modlist", "", "CSV files (*.csv);;All files (*)"
        )
        if not file_path:
            return
        try:
            from .modlist_io import import_modlist_csv

            known_mods = {}
            for row_index in range(self.model.rowCount()):
                list_item = self.model.item(row_index)
                if list_item.data(SEPARATOR_ROLE):
                    continue
                folder = list_item.data(Qt.UserRole)
                ws_id = paths.WORKSHOP_ID_RE.search(folder)
                known_mods[folder] = (ws_id.group(1) if ws_id else None, list_item.text())

            imported_folders = import_modlist_csv(file_path, known_mods)
        except Exception as exception:
            self.log(f"Failed to import modlist: {exception}", "error")
            return

        all_folders = set(f for f, _ in known_mods.items())
        new_order = imported_folders + [f for f in all_folders if f not in imported_folders]

        sort_index = 1
        for mod_folder in new_order:
            if mod_folder.endswith(SEPARATOR_SUFFIX):
                continue
            xml_path = os.path.join(config.mods_path, mod_folder, "metadata.xml")
            try:
                metadata_tree = ET.parse(xml_path)
                xml_root = metadata_tree.getroot()
                mod_name = xml_root.find("name").text
                if sorted_pattern.match(mod_name):
                    mod_name = mod_name[4:]
                xml_root.find("name").text = f"{sort_index:03} {mod_name}"
                metadata_tree.write(xml_path, encoding="utf-8", xml_declaration=True)
                sort_index += 1
            except Exception as exception:
                self.log(f"Writing {mod_folder}: {exception}", "error")

        sorter.save_last_order(new_order)
        self.log(f"Imported {sort_index - 1} mods from CSV")
        self.getModList()

    def _on_item_double_clicked(self, index) -> None:
        list_item = self.model.itemFromIndex(index)
        if list_item.data(SEPARATOR_ROLE):
            self._edit_separator(list_item)
            return
        ctrl_held = QApplication.keyboardModifiers() & Qt.ControlModifier
        if ctrl_held:
            mod_folder = list_item.data(Qt.UserRole)
            if not mod_folder:
                return
            folder_path = os.path.join(config.mods_path, mod_folder)
            if not os.path.isdir(folder_path):
                self.log(f"Folder does not exist: {folder_path}", "warning")
                return
            from .widgets import open_path
            if not open_path(folder_path):
                self.log(f"Failed to open folder: {folder_path}", "error")

    def _edit_separator(self, list_item) -> None:
        separator_data = list_item.data(SEPARATOR_ROLE)
        old_separator_folder = list_item.data(Qt.UserRole)
        dialog = SeparatorDialog(
            "Edit Separator",
            name=separator_data["name"],
            color=separator_data["color"],
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        new_separator_name = dialog.result_name
        new_separator_color = dialog.result_color
        if not new_separator_name:
            return
        new_separator_folder = f"{new_separator_name}{SEPARATOR_SUFFIX}"
        if old_separator_folder != new_separator_folder:
            try:
                os.rename(
                    os.path.join(config.mods_path, old_separator_folder),
                    os.path.join(config.mods_path, new_separator_folder),
                )
            except OSError as exc:
                self.log(f"Failed to rename separator folder: {exc}", "error")
                return
        separator_xml_path = os.path.join(
            config.mods_path, new_separator_folder, "separator.xml"
        )
        xml_root = ET.Element("separator")
        ET.SubElement(xml_root, "name").text = new_separator_name
        ET.SubElement(xml_root, "color").text = new_separator_color
        xml_tree = ET.ElementTree(xml_root)
        xml_tree.write(separator_xml_path, encoding="utf-8", xml_declaration=True)
        self.log(f"Updated separator '{new_separator_name}'")
        self._save_current_order()
        self.getModList()

    def _on_context_menu(self, position) -> None:
        index = self.listView.indexAt(position)
        if not index or not index.isValid():
            return
        list_item = self.model.itemFromIndex(index)
        if not list_item.data(SEPARATOR_ROLE):
            return
        context_menu = QMenu(self)
        context_menu.setStyleSheet("QMenu { border: 1px solid palette(mid); }")
        context_menu.addAction("Edit", lambda: self._edit_separator(list_item))
        context_menu.addAction("Delete", lambda: self._delete_separator(list_item))
        context_menu.exec(self.listView.viewport().mapToGlobal(position))

    def _delete_separator(self, list_item) -> None:
        separator_folder = list_item.data(Qt.UserRole)
        folder_path = os.path.join(config.mods_path, separator_folder)
        try:
            import shutil
            shutil.rmtree(folder_path)
            self.log(f"Deleted separator '{list_item.text()}'")
            self._save_current_order()
            self.getModList()
        except OSError as exception:
            self.log(f"Deleting separator: {exception}", "error")

    def _save_current_order(self) -> None:
        ordered_folders = []
        for row_index in range(self.model.rowCount()):
            ordered_folders.append(
                self.model.item(row_index).data(Qt.UserRole)
            )
        sorter.save_last_order(ordered_folders)

    def _get_accent_color_hex(self) -> str:
        return config.accent_color
