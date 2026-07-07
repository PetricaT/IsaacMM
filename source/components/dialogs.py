"""Dialog windows: settings, separator editing, etc."""
from __future__ import annotations


import os
from datetime import datetime
from typing import Optional, Protocol, Any

from PySide6.QtCore import QDateTime, QLocale, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStyledItemDelegate,
    QStyleFactory,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import config, logger, paths
from ..backup import backup_all, get_backup_root
from ..worker import ManagedWorker
from .file_utils import open_path
from .controller_ui import ICON_SIZE, BUTTON_SIZE


def _colorize(old: str, new: str) -> list[tuple[str, Optional[str]]]:
    i = 0
    while i < len(old) and i < len(new) and old[i] == new[i]:
        i += 1
    segments: list[tuple[str, Optional[str]]] = []
    if old:
        segments.append((old[:i], None))
        if old[i:]:
            segments.append((old[i:], config.lose_color))
    segments.append((" \u2192 ", None))
    if new:
        segments.append((new[:i], None))
        if new[i:]:
            segments.append((new[i:], config.win_color))
    return segments


class SettingsPanelOwner(Protocol):
    def log(self, message: str, level: str = "info") -> None: ...
    def log_colored(self, segments: list[tuple[str, Optional[str]]]) -> None: ...
    def getModList(self) -> None: ...
    mod_list_panel: Any
    modInfoPanel: Any
    _backup_thread: Any
    
def _btn_qss(color: str) -> str:
    return f"background-color: {color};"

try:
    from ..controller import GamepadType
    _HAS_SDL = True
except ImportError:
    GamepadType = object
    _HAS_SDL = False

CONFLICT_ROLE = Qt.ItemDataRole.UserRole + 1  # 257
SEPARATOR_ROLE = Qt.ItemDataRole.UserRole + 2  # 258
PREV_CHECK_ROLE = Qt.ItemDataRole.UserRole + 3  # 259
OVERWRITTEN_ROLE = Qt.ItemDataRole.UserRole + 4  # 260
NORMALIZED_NAME_ROLE = Qt.ItemDataRole.UserRole + 5  # 261
WINS_ROLE = Qt.ItemDataRole.UserRole + 6  # 262
LOSSES_ROLE = Qt.ItemDataRole.UserRole + 7  # 263
EMPTY_ROLE = Qt.ItemDataRole.UserRole + 8  # 264


class ConflictDelegate(QStyledItemDelegate):
    _empty_pixmap: QPixmap | None = None

    @classmethod
    def _get_empty_pixmap(cls) -> QPixmap | None:
        if cls._empty_pixmap is None:
            from .. import paths
            path = os.path.join(paths.BASE_DIR, "assets", "ui", "empty.png")
            if os.path.exists(path):
                pm = QPixmap(path)
                if not pm.isNull():
                    cls._empty_pixmap = pm.scaled(
                        16, 16, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
        return cls._empty_pixmap

    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)
        if index.data(EMPTY_ROLE):
            pm = self._get_empty_pixmap()
            if pm and not pm.isNull():
                item_rect = option.rect
                x = item_rect.right() - pm.width() - 4
                y = item_rect.top() + (item_rect.height() - pm.height()) // 2
                painter.drawPixmap(x, y, pm)
            return
        wins = index.data(WINS_ROLE)
        losses = index.data(LOSSES_ROLE)
        if not wins and not losses:
            return
        from .. import config
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        font = QFont()
        font.setPixelSize(14)
        font.setBold(True)
        painter.setFont(font)
        item_rect = option.rect
        size = 16
        gap = 2
        if wins and not losses:
            painter.setPen(QColor(config.win_color))
            x = item_rect.right() - size - 4
            y = item_rect.top() + (item_rect.height() - size) // 2
            painter.drawText(QRect(x, y, size, size), Qt.AlignmentFlag.AlignCenter, "+")
        elif losses and not wins:
            painter.setPen(QColor(config.lose_color))
            x = item_rect.right() - size - 4
            y = item_rect.top() + (item_rect.height() - size) // 2
            painter.drawText(QRect(x, y, size, size), Qt.AlignmentFlag.AlignCenter, "\u2212")
        else:
            total_w = size * 2 + gap
            x = item_rect.right() - total_w - 4
            y = item_rect.top() + (item_rect.height() - size) // 2
            painter.setPen(QColor(config.lose_color))
            painter.drawText(QRect(x, y, size, size), Qt.AlignmentFlag.AlignCenter, "\u2212")
            painter.setPen(QColor(config.win_color))
            painter.drawText(QRect(x + size + gap, y, size, size), Qt.AlignmentFlag.AlignCenter, "+")
        painter.restore()


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


class SettingsPanel(QWidget):
    closed = Signal()

    def __init__(self, owner: SettingsPanelOwner, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._owner = owner

        main_layout = QVBoxLayout(self)

        base = os.path.join(paths.BASE_DIR, "assets", "controller")

        header = QHBoxLayout()
        done_btn = QPushButton("\u2190 Back")
        done_btn.clicked.connect(self.closed.emit)
        header.addWidget(done_btn)

        self._back_icon = QLabel()
        self._back_icon.setFixedSize(ICON_SIZE, ICON_SIZE)
        self._back_icon.hide()
        header.addWidget(self._back_icon)
        header.addStretch()
        main_layout.addLayout(header)

        tabs = QTabWidget()
        self._tabs = tabs
        self._ctrl_buttons: dict[int, callable] = {}

        self._left_tab_icon = QLabel()
        self._left_tab_icon.setFixedSize(BUTTON_SIZE, ICON_SIZE)
        self._left_tab_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = QPixmap(os.path.join(base, "left_shoulder.png"))
        if not pm.isNull():
            self._left_tab_icon.setPixmap(
                pm.scaled(ICON_SIZE, ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
            )
        self._left_tab_icon.hide()
        tabs.setCornerWidget(self._left_tab_icon, Qt.Corner.TopLeftCorner)

        self._right_tab_icon = QLabel()
        self._right_tab_icon.setFixedSize(BUTTON_SIZE, ICON_SIZE)
        self._right_tab_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = QPixmap(os.path.join(base, "right_shoulder.png"))
        if not pm.isNull():
            self._right_tab_icon.setPixmap(
                pm.scaled(ICON_SIZE, ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
            )
        self._right_tab_icon.hide()
        tabs.setCornerWidget(self._right_tab_icon, Qt.Corner.TopRightCorner)

        behavior_tab = QWidget()
        behavior_layout = QVBoxLayout(behavior_tab)

        setup_group = QGroupBox("Setup")
        setup_layout = QFormLayout(setup_group)
        mods_path_layout = QHBoxLayout()
        self.mods_path_edit = QLineEdit()
        detected_mods = paths.find_isaac_mods_folder() or ""
        self.mods_path_edit.setPlaceholderText(
            detected_mods if detected_mods else "(not set)"
        )
        if config.mods_path == detected_mods or not config.mods_path:
            self.mods_path_edit.setText("")
        else:
            self.mods_path_edit.setText(config.mods_path)
        self.mods_path_edit.editingFinished.connect(self._save_settings)
        self.mods_path_edit.textChanged.connect(self._update_open_buttons)
        browse_mods_btn = QPushButton("Browse...")
        browse_mods_btn.clicked.connect(self._pick_mods_path)
        self.open_mods_btn = QPushButton("\u2197")
        self.open_mods_btn.setFixedWidth(BUTTON_SIZE)
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
        self.open_backup_btn.setFixedWidth(BUTTON_SIZE)
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

        updates_group = QGroupBox("Updates")
        updates_layout = QVBoxLayout(updates_group)
        self.update_check_btn = QPushButton("Check for Updates")
        self.update_check_btn.clicked.connect(self._check_updates)
        updates_layout.addWidget(self.update_check_btn)
        self._update_status_label = QLabel(f"Current version: {paths.version}")
        updates_layout.addWidget(self._update_status_label)
        behavior_layout.addWidget(updates_group)

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

        self.animate_anm2_check = QCheckBox("Animate .anm2 preview")
        self.animate_anm2_check.setChecked(config.animate_anm2_preview)
        self.animate_anm2_check.toggled.connect(self._save_settings)
        display_layout.addRow(self.animate_anm2_check)

        self.download_icons_check = QCheckBox("Download missing icons from workshop")
        self.download_icons_check.setChecked(config.download_icons)
        self.download_icons_check.toggled.connect(self._save_settings)
        display_layout.addRow(self.download_icons_check)

        date_format_layout = QHBoxLayout()
        self.date_format_combo = QComboBox()
        self.date_format_combo.addItem("System locale (auto)", "")
        self.date_format_combo.addItem("YYYY-MM-DD", "%Y-%m-%d")
        self.date_format_combo.addItem("DD/MM/YYYY", "%d/%m/%Y")
        self.date_format_combo.addItem("MM/DD/YYYY", "%m/%d/%Y")
        self.date_format_combo.addItem("DD.MM.YYYY", "%d.%m.%Y")
        self.date_format_combo.addItem("YYYY/MM/DD", "%Y/%m/%d")
        index = self.date_format_combo.findData(config.date_format)
        if index >= 0:
            self.date_format_combo.setCurrentIndex(index)
        self.date_format_combo.currentIndexChanged.connect(self._save_settings)
        date_format_layout.addWidget(self.date_format_combo)
        self.date_preview_label = QLabel()
        self.date_preview_label.setStyleSheet(f"color: {config.folder_label_color};")
        date_format_layout.addWidget(self.date_preview_label)
        date_format_layout.addStretch()
        display_layout.addRow("Date format:", date_format_layout)
        self._update_date_preview()
        behavior_layout.addWidget(display_group)

        paths_group = QGroupBox("Paths")
        paths_layout = QHBoxLayout(paths_group)
        self.open_config_btn = QPushButton("Open Config")
        self.open_config_btn.clicked.connect(lambda: open_path(paths.config_dir))
        self.open_data_btn = QPushButton("Open Data")
        self.open_data_btn.clicked.connect(lambda: open_path(paths.appdata))
        self.open_cache_btn = QPushButton("Open Cache")
        self.open_cache_btn.clicked.connect(lambda: open_path(paths.cache_dir))
        paths_layout.addWidget(self.open_config_btn)
        paths_layout.addWidget(self.open_data_btn)
        paths_layout.addWidget(self.open_cache_btn)
        behavior_layout.addWidget(paths_group)

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
        theme_main_layout = QVBoxLayout(theme_tab)
        theme_main_layout.setContentsMargins(0, 0, 0, 0)

        top_widget = QWidget()
        theme_layout = QFormLayout(top_widget)
        theme_layout.setVerticalSpacing(4)
        theme_layout.setContentsMargins(9, 9, 9, 4)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Native (platform default)", "native")
        self.theme_combo.addItem("Fusion (cross-platform)", "fusion")
        for style_key in QStyleFactory.keys():
            lower = style_key.lower()
            if lower not in ("fusion",):
                self.theme_combo.addItem(style_key, lower)
        index = self.theme_combo.findData(config.theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        self.theme_combo.currentIndexChanged.connect(self._save_settings)

        self.preset_combo = QComboBox()
        for name in config.THEME_PRESETS:
            label = name.replace("_", " ").title()
            self.preset_combo.addItem(label, name)
        idx = self.preset_combo.findData(config.theme_preset)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)

        theme_layout.addRow("Qt Style:", self.theme_combo)
        theme_layout.addRow("Preset:", self.preset_combo)

        self.system_icons_check = QCheckBox("Use system icons (KDE/desktop theme)")
        self.system_icons_check.setChecked(config.use_system_icons)
        self.system_icons_check.toggled.connect(self._save_settings)
        theme_layout.addRow(self.system_icons_check)

        theme_main_layout.addWidget(top_widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_inner = QWidget()
        scroll_layout = QFormLayout(scroll_inner)
        scroll_layout.setVerticalSpacing(6)
        scroll_layout.setContentsMargins(12, 6, 12, 12)

        self.accent_btn = QPushButton()
        self.accent_btn.setFixedWidth(60)
        self.accent_btn.setStyleSheet(_btn_qss(config.accent_color))
        self.accent_btn.clicked.connect(self._pick_accent)
        scroll_layout.addRow("Accent color:", self.accent_btn)

        self.disabled_mod_btn = QPushButton()
        self.disabled_mod_btn.setFixedWidth(60)
        self.disabled_mod_btn.setStyleSheet(
            _btn_qss(config.disabled_mod_color))
        self.disabled_mod_btn.clicked.connect(self._pick_disabled_mod_color)
        scroll_layout.addRow("Disabled mod color:", self.disabled_mod_btn)

        self.win_btn = QPushButton()
        self.win_btn.setFixedWidth(60)
        self.win_btn.setStyleSheet(_btn_qss(config.win_color))
        self.win_btn.clicked.connect(self._pick_win_color)
        scroll_layout.addRow("Win (conflict +):", self.win_btn)

        self.lose_btn = QPushButton()
        self.lose_btn.setFixedWidth(60)
        self.lose_btn.setStyleSheet(_btn_qss(config.lose_color))
        self.lose_btn.clicked.connect(self._pick_lose_color)
        scroll_layout.addRow("Lose (conflict \u2212):", self.lose_btn)

        sep_label = QLabel("<b>\u2014 Mod List \u2014</b>")
        scroll_layout.addRow(sep_label)
        self._add_colors(scroll_layout, [
            ("Separator color:", "separator_color"),
        ])

        mi_label = QLabel("<b>\u2014 Mod Info \u2014</b>")
        scroll_layout.addRow(mi_label)
        self._add_colors(scroll_layout, [
            ("Folder label:", "folder_label_color"),
            ("Icon border:", "icon_border_color"),
            ("Tag background:", "tag_bg"),
            ("Tag text:", "tag_fg"),
            ("Dpad indicators:", "dpad_color"),
            ("Workshop missing:", "workshop_missing_color"),
            ("Workshop current:", "workshop_badge_current"),
            ("Workshop possible:", "workshop_badge_possible"),
            ("Workshop outdated:", "workshop_badge_outdated"),
            ("Workshop default:", "workshop_badge_default"),
        ])

        c_label = QLabel("<b>\u2014 Console \u2014</b>")
        scroll_layout.addRow(c_label)
        self._add_colors(scroll_layout, [
            ("Background:", "console_bg"),
            ("Text:", "console_fg"),
            ("Border:", "console_border"),
            ("Rate bar bg:", "rate_bar_bg"),
            ("Log info:", "log_info_color"),
            ("Log warn:", "log_warn_color"),
            ("Log error:", "log_error_color"),
        ])

        p_label = QLabel("<b>\u2014 Preview \u2014</b>")
        scroll_layout.addRow(p_label)
        self._add_colors(scroll_layout, [
            ("Border:", "preview_border"),
            ("Background:", "preview_bg"),
        ])

        scroll_layout.addRow(QLabel(""))  # bottom spacer
        scroll.setWidget(scroll_inner)
        theme_main_layout.addWidget(scroll, 1)
        tabs.addTab(theme_tab, "Theme")

        controller_tab = QWidget()
        controller_layout = QVBoxLayout(controller_tab)

        ctrl_group = QGroupBox("Controller")
        ctrl_form = QFormLayout(ctrl_group)
        self.ctrl_enable_check = QCheckBox("Enable controller support")
        self.ctrl_enable_check.setChecked(config.controller_enabled)
        self.ctrl_enable_check.toggled.connect(self._save_settings)
        ctrl_form.addRow(self.ctrl_enable_check)

        ctrl_info_group = QGroupBox("Controller Info")
        ctrl_info_layout = QFormLayout(ctrl_info_group)
        self.ctrl_name_label = QLabel("Not connected")
        self.ctrl_type_label = QLabel("-")
        ctrl_info_layout.addRow("Name:", self.ctrl_name_label)
        ctrl_info_layout.addRow("Type:", self.ctrl_type_label)
        controller_layout.addWidget(ctrl_group)
        controller_layout.addWidget(ctrl_info_group)
        controller_layout.addStretch()

        ctrl_deadzone_group = QGroupBox("Dead Zone")
        ctrl_deadzone_layout = QFormLayout(ctrl_deadzone_group)
        deadzone_layout = QHBoxLayout()
        self.ctrl_deadzone_slider = QSlider(Qt.Orientation.Horizontal)
        self.ctrl_deadzone_slider.setRange(0, 32768)
        self.ctrl_deadzone_slider.setValue(config.controller_deadzone)
        self.ctrl_deadzone_slider.valueChanged.connect(self._save_settings)
        self.ctrl_deadzone_label = QLabel(str(config.controller_deadzone))
        self.ctrl_deadzone_slider.valueChanged.connect(
            lambda v: self.ctrl_deadzone_label.setText(str(v))
        )
        deadzone_layout.addWidget(self.ctrl_deadzone_slider, 1)
        deadzone_layout.addWidget(self.ctrl_deadzone_label)
        ctrl_deadzone_layout.addRow("Axis dead zone:", deadzone_layout)
        controller_layout.addWidget(ctrl_deadzone_group)

        tabs.addTab(controller_tab, "Controller")

        accessibility_tab = QWidget()
        accessibility_layout = QVBoxLayout(accessibility_tab)

        a11y_group = QGroupBox("Controller Icons")
        a11y_form = QFormLayout(a11y_group)
        self.simple_icons_check = QCheckBox("Use simple controller icons")
        self.simple_icons_check.setChecked(config.controller_simple_icons)
        self.simple_icons_check.toggled.connect(self._save_settings)
        a11y_form.addRow(self.simple_icons_check)
        accessibility_layout.addWidget(a11y_group)
        accessibility_layout.addStretch()
        tabs.addTab(accessibility_tab, "Accessibility")

        main_layout.addWidget(tabs)
        self._update_open_buttons()
        self._update_controller_info()

    def _set_back_icon(self, gamepad_type: int) -> None:
        dir_map = {2: "xbox", 3: "xbox", 4: "ps", 5: "ps", 6: "ps"}
        subdir = dir_map.get(gamepad_type, "xbox")
        base = os.path.join(paths.BASE_DIR, "assets", "controller")
        pm = QPixmap(os.path.join(base, subdir, "EAST.png"))
        if pm.isNull():
            pm = QPixmap(os.path.join(base, "EAST.png"))
        if pm.isNull():
            pm = QPixmap(os.path.join(base, "select.png"))
        self._back_icon.setPixmap(
            pm.scaled(ICON_SIZE, ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                      Qt.TransformationMode.SmoothTransformation)
        )

    def connect_controller(self, controller_mgr) -> None:
        from ..controller import Button
        self._ctrl_buttons = {
            Button.LEFT_SHOULDER: self._ctrl_prev_tab,
            Button.RIGHT_SHOULDER: self._ctrl_next_tab,
            Button.DPAD_UP: self._ctrl_focus_prev,
            Button.DPAD_DOWN: self._ctrl_focus_next,
            Button.SOUTH: self._ctrl_activate,
            Button.EAST: self._ctrl_close,
            Button.BACK: self._ctrl_close,
        }
        controller_mgr.button_down.connect(self._on_controller_button)
        controller_mgr.activity_changed.connect(self._on_controller_activity)
        self._set_back_icon(getattr(controller_mgr, 'gamepad_type', 0))
        is_active = getattr(controller_mgr, 'is_active', True)
        self._on_controller_activity(is_active)

    def disconnect_controller(self, controller_mgr) -> None:
        try:
            controller_mgr.button_down.disconnect(self._on_controller_button)
        except Exception:
            pass
        try:
            controller_mgr.activity_changed.disconnect(self._on_controller_activity)
        except Exception:
            pass
        self._back_icon.hide()
        self._left_tab_icon.hide()
        self._right_tab_icon.hide()

    def _ctrl_close(self) -> None:
        self.closed.emit()

    def _on_controller_activity(self, active: bool) -> None:
        if active:
            self._back_icon.show()
            self._left_tab_icon.show()
            self._right_tab_icon.show()
        else:
            self._back_icon.hide()
            self._left_tab_icon.hide()
            self._right_tab_icon.hide()

    def _on_controller_button(self, button: int) -> None:
        handler = getattr(self, '_ctrl_buttons', {}).get(button)
        if handler:
            handler()

    def _ctrl_prev_tab(self) -> None:
        i = self._tabs.currentIndex()
        if i > 0:
            self._tabs.setCurrentIndex(i - 1)
            self._tabs.currentWidget().focusNextChild()

    def _ctrl_next_tab(self) -> None:
        i = self._tabs.currentIndex()
        if i < self._tabs.count() - 1:
            self._tabs.setCurrentIndex(i + 1)
            self._tabs.currentWidget().focusNextChild()

    def _ctrl_focus_prev(self) -> None:
        w = QApplication.focusWidget()
        if isinstance(w, (QSlider, QSpinBox)):
            if isinstance(w, QSlider):
                w.setValue(w.value() - w.singleStep())
            else:
                w.setValue(w.value() - w.singleStep())
        else:
            w = self._tabs.currentWidget()
            if w:
                w.focusPreviousChild()

    def _ctrl_focus_next(self) -> None:
        w = QApplication.focusWidget()
        if isinstance(w, (QSlider, QSpinBox)):
            if isinstance(w, QSlider):
                w.setValue(w.value() + w.singleStep())
            else:
                w.setValue(w.value() + w.singleStep())
        else:
            w = self._tabs.currentWidget()
            if w:
                w.focusNextChild()

    def _ctrl_activate(self) -> None:
        w = QApplication.focusWidget()
        if isinstance(w, QAbstractButton):
            w.animateClick()
        elif isinstance(w, QComboBox):
            w.showPopup()

    def _update_controller_info(self) -> None:
        ctrl = getattr(self._owner, '_controller', None)
        if ctrl and ctrl.is_connected:
            self.ctrl_name_label.setText(ctrl.gamepad_name)
            type_names = {
                0: "Unknown", 1: "Standard", 2: "Xbox 360", 3: "Xbox One",
                4: "PS3", 5: "PS4", 6: "PS5", 7: "Switch Pro",
            }
            self.ctrl_type_label.setText(type_names.get(ctrl.gamepad_type, str(ctrl.gamepad_type)))
        else:
            self.ctrl_name_label.setText("Not connected")
            self.ctrl_type_label.setText("-")

    def _add_colors(self, layout: QFormLayout, pairs: list[tuple[str, str]]) -> None:
        for label, attr in pairs:
            btn = QPushButton()
            btn.setFixedWidth(60)
            current = getattr(config, attr)
            if current:
                btn.setStyleSheet(_btn_qss(current))
            btn.clicked.connect(lambda checked, a=attr, b=btn: self._pick_color(a, b))
            setattr(self, f"_theme_{attr}", btn)
            layout.addRow(label, btn)

    def _pick_color(self, attr: str, btn: QPushButton) -> None:
        current = getattr(config, attr)
        if not current:
            current = self.palette().color(QPalette.ButtonText).name()
        color = QColorDialog.getColor(QColor(current), self)
        if color.isValid():
            setattr(config, attr, color.name())
            btn.setStyleSheet(_btn_qss(color.name()))
            self._save_settings()

    def _apply_preset(self) -> None:
        name = self.preset_combo.currentData()
        config.apply_preset(name)
        self._sync_theme_buttons()
        self._save_settings()

    def _sync_theme_buttons(self) -> None:
        btn_map = {
            "accent_color": "accent_btn",
            "disabled_mod_color": "disabled_mod_btn",
            "win_color": "win_btn",
            "lose_color": "lose_btn",
        }
        for attr, btn_name in btn_map.items():
            btn = getattr(self, btn_name, None)
            if btn:
                c = getattr(config, attr)
                if c:
                    btn.setStyleSheet(_btn_qss(c))
        for attr in dir(self):
            if attr.startswith("_theme_"):
                btn = getattr(self, attr)
                config_attr = attr[len("_theme_"):]
                c = getattr(config, config_attr)
                if c:
                    btn.setStyleSheet(_btn_qss(c))

    def _pick_accent(self) -> None:
        current = config.accent_color
        if not current:
            current = self.palette().color(QPalette.Highlight).name()
        color = QColorDialog.getColor(QColor(current), self)
        if color.isValid():
            config.accent_color = color.name()
            self.accent_btn.setStyleSheet(_btn_qss(config.accent_color))
            self._save_settings()
            if self._owner is not None:
                update_style = getattr(self._owner, "update_accent_style", None)
                if callable(update_style):
                    update_style(color.name())

    def _pick_disabled_mod_color(self) -> None:
        current = config.disabled_mod_color or self.palette().color(QPalette.Disabled, QPalette.Text).name()
        color = QColorDialog.getColor(QColor(current), self)
        if color.isValid():
            config.disabled_mod_color = color.name()
            self.disabled_mod_btn.setStyleSheet(
                _btn_qss(config.disabled_mod_color))
            self._save_settings()

    def _pick_win_color(self) -> None:
        color = QColorDialog.getColor(QColor(config.win_color), self)
        if color.isValid():
            config.win_color = color.name()
            self.win_btn.setStyleSheet(_btn_qss(config.win_color))
            self._save_settings()

    def _pick_lose_color(self) -> None:
        color = QColorDialog.getColor(QColor(config.lose_color), self)
        if color.isValid():
            config.lose_color = color.name()
            self.lose_btn.setStyleSheet(_btn_qss(config.lose_color))
            self._save_settings()

    def _pick_mods_path(self) -> None:
        starting = (
            config.mods_path
            if config.mods_path and os.path.isdir(config.mods_path)
            else ""
        )
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

    def _update_date_preview(self) -> None:
        fmt = self.date_format_combo.currentData()
        if fmt:
            preview = datetime.now().strftime(fmt)
        else:
            preview = QLocale().toString(
                QDateTime.currentDateTime(), QLocale.FormatType.ShortFormat
            )
        self.date_preview_label.setText(f"Preview: {preview}")

    def _update_open_buttons(self) -> None:
        mods_folder = self.mods_path_edit.text().strip()
        if not mods_folder:
            mods_folder = paths.find_isaac_mods_folder() or ""
        self.open_mods_btn.setEnabled(bool(mods_folder) and os.path.isdir(mods_folder))

        backup_folder = self.backup_path_edit.text().strip()
        if not backup_folder:
            backup_folder = (
                get_backup_root(config.mods_path) if config.mods_path else ""
            )
        self.open_backup_btn.setEnabled(
            bool(backup_folder) and os.path.isdir(backup_folder)
        )

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
        prev_ctrl = config.controller_enabled
        prev_simple = config.controller_simple_icons
        config.backup_enabled = self.backup_check.isChecked()
        text = self.backup_path_edit.text().strip()
        config.backup_path = text if text else None
        config.animate_icons = self.animate_check.isChecked()
        config.animate_anm2_preview = self.animate_anm2_check.isChecked()
        config.preview_images = self.preview_check.isChecked()
        config.download_icons = self.download_icons_check.isChecked()
        config.log_level = self.log_level_combo.currentData()
        logger.set_level(config.log_level)
        config.date_format = self.date_format_combo.currentData()
        config.controller_enabled = self.ctrl_enable_check.isChecked()
        config.controller_deadzone = self.ctrl_deadzone_slider.value()
        config.controller_simple_icons = self.simple_icons_check.isChecked()
        config.use_system_icons = self.system_icons_check.isChecked()
        config.theme_preset = self.preset_combo.currentData()
        self._update_date_preview()
        mods_text = self.mods_path_edit.text().strip()
        if mods_text:
            config.mods_path = mods_text
        else:
            detected = paths.find_isaac_mods_folder()
            config.mods_path = detected or config.mods_path
        new_theme = self.theme_combo.currentData()
        if new_theme != config.theme:
            config.theme = new_theme
            style_name = (
                getattr(config, "_native_style", None)
                if new_theme == "native"
                else new_theme
            )
            if style_name:
                apply_fn = getattr(self._owner, "apply_qt_theme", None)
                if callable(apply_fn):
                    apply_fn(style_name)
        if config.mods_path != prev_mods:
            get_mod_list = getattr(self._owner, "getModList", None)
            if callable(get_mod_list):
                get_mod_list()
        log = getattr(self._owner, "log", None)
        if callable(log) and config.backup_enabled != prev_backup:
            log(f"Backup {'enabled' if config.backup_enabled else 'disabled'}")
        if config.controller_simple_icons != prev_simple:
            if hasattr(self._owner, 'mod_list_panel'):
                self._owner.mod_list_panel.set_simple_icons(config.controller_simple_icons)
            if hasattr(self._owner, 'modInfoPanel'):
                self._owner.modInfoPanel.set_simple_icons(config.controller_simple_icons)
        if config.use_system_icons != getattr(self, '_prev_system_icons', False):
            self._prev_system_icons = config.use_system_icons
            if hasattr(self._owner, 'modInfoPanel'):
                self._owner.modInfoPanel.refresh_icons()
        self._update_open_buttons()
        self._update_controller_info()
        config.save()

    def _run_backup(self) -> None:
        if not config.mods_path:
            return
        owner = self._owner
        if owner is None:
            return

        bw = getattr(owner, "_backup_worker", None)
        if bw is None or bw.is_running:
            return

        log = getattr(owner, "log", None)
        if callable(log):
            log("Running manual backup...")

        owner._manual_backup = True
        bw.start(
            backup_all,
            config.mods_path,
            get_backup_root(config.mods_path),
            list(config.loaded_mods),
            name="Backup",
        )

    def _check_updates(self) -> None:
        owner = self._owner
        if owner is None:
            return
        check = getattr(owner, "_check_for_updates_interactive", None)
        if callable(check):
            check()
