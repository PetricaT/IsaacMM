"""Main application window and entry point."""

from __future__ import annotations

import os
import sys
from typing import Optional, Union

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QPixmap, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import config, paths
from ..core.notifications import send_notification
from ..core.worker import ManagedWorker
from ..mods import game_versions, sorter
from ..mods.backup import backup_all, get_backup_root
from ..mods.folder_watcher import ModFolderWatcher
from ..mods.workshop import (
    _get_details_from_cache,
    _init_workshop_limiter,
    details_queue,
)
from ..controller.controller import (
    Button,
    ControllerManager,
)
from ..controller.controller_ui import ICON_SIZE, ControllerRouter, FocusOverlay
from .pixmap_utils import scaled_pixmap
from ..theme import theme
from ..updater.update_dialog import UpdateDialog
from ..updater.updater import (
    get_download_asset,
    get_latest_release,
    is_appimage,
    is_newer_version,
)
from .dialogs.delegates import SEPARATOR_ROLE, _colorize
from .dialogs.settings import SettingsPanel
from .panels.console import ConsoleWidget
from .panels.mod_info import ModInfoPanel
from .panels.mod_list import SEPARATOR_SUFFIX, ModListPanel


class DragApp(QWidget):
    loaded_mods = config.loaded_mods
    FOCUS_QSS = """
QComboBox:focus, QSpinBox:focus, QLineEdit:focus {
    border: 2px solid palette(highlight);
}
QCheckBox:focus {
    outline: 2px solid palette(highlight);
}
QSlider:focus {
    border: 1px solid palette(highlight);
}
QPushButton:focus {
    border: 2px solid palette(highlight);
}
"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.installEventFilter(self)
        self._backup_worker = ManagedWorker(parent=self)
        self._masterlist_worker = ManagedWorker(parent=self)
        self._game_versions_worker = ManagedWorker(parent=self)
        self._manual_backup = False
        self._theme_qss = ""
        self._backup_worker.finished.connect(self._on_backup_finished)
        self._backup_worker.error.connect(
            lambda m: self.log(f"Backup failed: {m}", "error")
        )
        self._masterlist_worker.finished.connect(
            lambda r: (
                self.log("Masterlist updated to latest version") if r is True else None
            )
        )
        self._masterlist_worker.error.connect(
            lambda m: self.log(f"Masterlist fetch failed: {m}", "warning")
        )
        self._game_versions_worker.finished.connect(
            lambda r: self.log("Game versions updated to latest") if r is True else None
        )
        self._game_versions_worker.error.connect(
            lambda m: self.log(f"Game versions fetch failed: {m}", "warning")
        )
        self._update_worker = ManagedWorker(parent=self)
        self._update_worker.finished.connect(self._on_update_check_done)
        self._update_worker.error.connect(
            lambda m: self.log(f"Update check failed: {m}", "warning")
        )
        self._controller = None
        self._router = None

        self.setWindowTitle(f"Tboi Mod Manager [{paths.version}]")
        s = config.get_settings()
        geom = s.value("ui/window_geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
            self.resize(1161, 550)

        _init_workshop_limiter()
        game_versions.fetch_initial()
        # Windows requires admin rights for symlinking
        if sys.platform != "win32":
            paths.setup_symlinks()
        self.initUi()
        self._refresh_masterlist_background()
        self._refresh_game_versions_background()
        self._load_base_qss()
        self._init_controller()
        if config.check_updates_on_startup:
            QTimer.singleShot(5000, self._check_for_updates_silent)

    def apply_qt_theme(self, style_name: str) -> None:
        if getattr(self, "_applying_theme", False):
            return
        self._applying_theme = True
        try:
            app = QApplication.instance()
            if not app:
                return
            app.setStyle(style_name)
            qss = self._base_qss
            if self._controller and self._controller.is_active:
                qss = qss + self.FOCUS_QSS
            app.setStyleSheet("")
            app.setStyleSheet(qss)
            for widget in app.allWidgets():
                if type(widget) is QWidget:
                    widget.setAutoFillBackground(True)
            for widget in app.allWidgets():
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
        finally:
            self._applying_theme = False

    def _apply_theme_data(
        self,
        palette: Optional[QPalette] = None,
        theme_qss: str = "",
    ) -> None:
        """Apply a full theme (palette + QSS) through the safe repaint cycle.

        Uses the same ``setStyleSheet("")`` → ``setStyleSheet(qss)`` +
        unpolish/polish pattern as :meth:`apply_qt_theme` to avoid Qt crashes.
        """
        if getattr(self, "_applying_theme", False):
            return
        self._applying_theme = True
        self._theme_qss = theme_qss
        try:
            app = QApplication.instance()
            if not app:
                return
            if palette is not None:
                app.setPalette(palette)
            qss = self._base_qss + theme_qss
            if self._controller and self._controller.is_active:
                qss = qss + self.FOCUS_QSS
            app.setStyleSheet("")
            app.setStyleSheet(qss)
            for widget in app.allWidgets():
                if type(widget) is QWidget:
                    widget.setAutoFillBackground(True)
            for widget in app.allWidgets():
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
        finally:
            self._applying_theme = False

    def closeEvent(self, close_event) -> None:
        self._folder_watcher.stop()
        s = config.get_settings()
        s.setValue("ui/window_geometry", self.saveGeometry())
        s.setValue("ui/splitter_state", self._splitter.saveState())
        s.setValue("ui/vsplitter_state", self._vsplitter.saveState())
        s.setValue(
            "ui/column_state", self.modInfoPanel.conflicts_tree.header().saveState()
        )
        config.flush()
        if self._controller:
            self._controller.cleanup()
        if hasattr(self, "_router"):
            self._router.cleanup()
        for icon in getattr(self.mod_list_panel, "_controller_icons", []):
            icon.cleanup()
        for icon in getattr(self.modInfoPanel, "_controller_icons", []):
            icon.cleanup()
        for ov in getattr(self, "_focus_overlays", []):
            ov.hide()
            ov.setParent(None)
        for lbl, _ in getattr(self, "_shoulder_indicators", []):
            lbl.hide()
            lbl.setParent(None)
        self._backup_worker.wait(15000)
        self._masterlist_worker.wait(5000)
        self._game_versions_worker.wait(5000)
        self._update_worker.wait(5000)
        if hasattr(self, "mod_list_panel"):
            self.mod_list_panel.shutdown()
        if hasattr(self, "modInfoPanel"):
            self.modInfoPanel.shutdown()
        super().closeEvent(close_event)

    def initUi(self) -> None:
        layout = QVBoxLayout(self)

        self.console_widget = ConsoleWidget()

        self.mod_list_panel = ModListPanel()
        self.mod_list_panel.mod_selected.connect(self._on_mod_selected)
        self.mod_list_panel.log_message.connect(self.console_widget.log)
        self.mod_list_panel.open_settings.connect(self._open_settings)
        self.mod_list_panel.mods_loaded.connect(self._maybe_backup)
        self.mod_list_panel.mods_loaded.connect(self._batch_fetch_details)

        self._folder_watcher = ModFolderWatcher(self)
        self.mod_list_panel.set_watcher(self._folder_watcher)
        self.console_widget.set_watcher(self._folder_watcher)
        self._start_folder_watcher()

        self.modInfoPanel = ModInfoPanel()
        self.modInfoPanel.log_message.connect(self.console_widget.log)
        self.mod_list_panel.mods_loaded.connect(self.modInfoPanel.populate_data_tab)

        self._left_panel = QWidget()
        left_layout = QVBoxLayout(self._left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.mod_list_panel)

        horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)
        horizontal_splitter.addWidget(self._left_panel)
        horizontal_splitter.addWidget(self.modInfoPanel)
        horizontal_splitter.setStretchFactor(0, 1)
        horizontal_splitter.setStretchFactor(1, 1)
        s = config.get_settings()
        splitter_state = s.value("ui/splitter_state")
        if splitter_state:
            horizontal_splitter.restoreState(splitter_state)
        self._splitter = horizontal_splitter

        vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        vertical_splitter.addWidget(horizontal_splitter)
        vertical_splitter.addWidget(self.console_widget)
        vertical_splitter.setStretchFactor(0, 1)
        vertical_splitter.setStretchFactor(1, 0)
        vstate = s.value("ui/vsplitter_state")
        if vstate:
            vertical_splitter.restoreState(vstate)
        self._vsplitter = vertical_splitter

        main_page = QWidget()
        main_layout = QVBoxLayout(main_page)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(vertical_splitter)

        self._settings_panel = SettingsPanel(self)
        self._settings_panel.closed.connect(self._on_settings_closed)

        self._stack = QStackedWidget()
        self._stack.addWidget(main_page)
        self._stack.addWidget(self._settings_panel)

        layout.addWidget(self._stack)

        column_state = s.value("ui/column_state")
        if column_state:
            self.modInfoPanel.restore_column_state(column_state)

    def _start_folder_watcher(self) -> None:
        if config.mods_path:
            self._folder_watcher.start(config.mods_path)

    def _on_mod_selected(self, mod_name: str, mod_folder: str, conflicts) -> None:
        if mod_folder and mod_folder.endswith(SEPARATOR_SUFFIX):
            self.modInfoPanel.show_separator(mod_name, mod_folder)
            return
        self.modInfoPanel.show_mod_info(mod_name, mod_folder, None, conflicts)

    def _open_settings(self) -> None:
        self.modInfoPanel.stop_preview()
        self._stack.setCurrentWidget(self._settings_panel)
        if self._controller and self._controller.is_connected:
            self._router.unregister_global(
                Button.LEFT_SHOULDER,
                Button.RIGHT_SHOULDER,
                Button.BACK,
            )
            self._settings_panel.connect_controller(self._controller)

    def _on_settings_closed(self) -> None:
        self._stack.setCurrentIndex(0)
        if self._controller and self._controller.is_connected:
            self._settings_panel.disconnect_controller(self._controller)
            self._router.register_global(
                {
                    Button.LEFT_SHOULDER: self._focus_modlist,
                    Button.RIGHT_SHOULDER: self._focus_modinfo,
                    Button.BACK: self._open_settings,
                }
            )

    def _maybe_backup(self) -> None:
        if not config.backup_enabled or not config.mods_path:
            return
        self.log("Backing up modified mods...")
        self._backup_worker.start(
            backup_all,
            config.mods_path,
            get_backup_root(config.mods_path),
            list(config.loaded_mods),
            name="Backup",
        )

    def _on_backup_finished(self, results: list[tuple[str, str, str, str]]) -> None:
        self.log("Backup complete")
        if not self._manual_backup:
            return
        self._manual_backup = False
        for mod_name, old_ver, new_ver, magnitude in results:
            if old_ver == "?":
                self.log_colored([("Added: ", None), (mod_name, config.win_color)])
                continue
            if old_ver == new_ver:
                continue
            segments = [(f"{mod_name}: ", None)]
            segments.extend(_colorize(old_ver, new_ver))
            self.log_colored(segments)
        if results:
            send_notification("Backup complete", f"{len(results)} mod(s) backed up")

    def _check_for_updates_silent(self) -> None:
        if self._update_worker.is_running:
            return
        self._update_worker.start(
            lambda: get_latest_release(config.include_prereleases),
            name="UpdateCheck",
        )

    def _check_for_updates_interactive(self) -> None:
        if self._update_worker.is_running:
            return
        self.log("Checking for updates...")
        self._interactive_update_check = True
        self._update_worker.start(
            lambda: get_latest_release(config.include_prereleases),
            name="UpdateCheck",
        )

    def _on_update_check_done(self, release: dict | None) -> None:
        interactive = getattr(self, "_interactive_update_check", False)
        self._interactive_update_check = False

        if release is None:
            if interactive:
                self.log(
                    "Could not check for updates (no network or API down)", "warning"
                )
            return

        tag = release.get("tag_name", "")
        if not tag or not is_newer_version(tag):
            if interactive:
                self.log(f"You are up to date ({paths.version})")
            self._pending_update = None
            self._notify_settings_update_state()
            return

        self.log(f"Update available: {tag} (you have {paths.version})")
        send_notification("Update available", f"{tag} is ready to download")

        if not interactive:
            self._pending_update = release
            self._notify_settings_update_state()
            return

        self._show_update_dialog(release)

    def _show_update_dialog(self, release: dict) -> None:
        tag = release.get("tag_name", "")
        changelog = release.get("body", "")
        asset = get_download_asset(release)
        download_url = asset["browser_download_url"] if asset else ""

        dialog = UpdateDialog(
            current_version=paths.version,
            new_version=tag,
            changelog=changelog or "",
            download_url=download_url,
            parent=self,
        )
        dialog.exec()

        dl_path = dialog.download_path()
        if dl_path and is_appimage():
            QTimer.singleShot(1500, QApplication.quit)
        self._pending_update = None
        self._notify_settings_update_state()
        self._fetch_masterlist()

    def _apply_pending_update(self) -> None:
        release = getattr(self, "_pending_update", None)
        if release is None:
            return
        self._show_update_dialog(release)

    def _get_pending_update(self) -> dict | None:
        return getattr(self, "_pending_update", None)

    def _notify_settings_update_state(self) -> None:
        if hasattr(self, "_settings_panel"):
            fn = getattr(self._settings_panel, "_refresh_update_state", None)
            if callable(fn):
                fn()

    def _refresh_masterlist_background(self) -> None:
        self._fetch_masterlist()
        self._masterlist_timer = QTimer(self)
        self._masterlist_timer.timeout.connect(self._fetch_masterlist)
        self._masterlist_timer.start(3600000)

    def _refresh_game_versions_background(self) -> None:
        self._fetch_game_versions()
        self._game_versions_timer = QTimer(self)
        self._game_versions_timer.timeout.connect(self._fetch_game_versions)
        self._game_versions_timer.start(3600000)

    def _fetch_game_versions(self) -> None:
        self._game_versions_worker.start(
            game_versions.fetch_background, name="GameVersions"
        )

    def _batch_fetch_details(self) -> None:
        if not config.download_icons:
            return
        enqueued = 0
        for row_index in range(self.mod_list_panel.model.rowCount()):
            list_item = self.mod_list_panel.model.item(row_index)
            if list_item is None or list_item.data(SEPARATOR_ROLE):
                continue
            mod_folder = list_item.data(Qt.ItemDataRole.UserRole)
            if not mod_folder:
                continue
            ws_match = paths.WORKSHOP_ID_RE.search(mod_folder)
            if not ws_match:
                continue
            ws_id = ws_match.group(1)
            if _get_details_from_cache(ws_id) is not None:
                continue
            if details_queue.enqueue(ws_id, key=ws_id):
                enqueued += 1

        if enqueued > 0:
            self.log(f"Queued {enqueued} workshop detail fetches", "info")
            self.modInfoPanel._process_details_queue()

    def _fetch_masterlist(self) -> None:
        self._masterlist_worker.start(sorter.fetch_background, name="Masterlist")

    def getModList(self) -> None:
        self.mod_list_panel.load_mod_list()

    def log(self, message: str, level: str = "info") -> None:
        self.console_widget.log(message, level)

    def log_colored(
        self, segments: list[tuple[str, Optional[str | QTextCharFormat]]]
    ) -> None:
        self.console_widget.log_colored(segments)

    def eventFilter(self, obj, event) -> bool:
        controller = getattr(self, "_controller", None)
        if controller and controller.is_connected:
            etype = event.type()
            if etype in (QEvent.MouseButtonPress, QEvent.KeyPress, QEvent.Wheel):
                self._controller.set_active(False)
        if event.type() == QEvent.Resize:
            for lbl, panel in getattr(self, "_shoulder_indicators", []):
                if obj is panel and lbl.isVisible():
                    self._reposition_shoulder_indicators()
                    break
        return super().eventFilter(obj, event)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.PaletteChange:
            self._load_base_qss()
            self.apply_qt_theme(QApplication.instance().style().name())
            self._refresh_on_theme_change()
        elif event.type() == QEvent.StyleChange:
            self._refresh_on_theme_change()
        elif event.type() == QEvent.ActivationChange and not self.isActiveWindow():
            self.modInfoPanel.stop_preview()
        super().changeEvent(event)

    def _refresh_on_theme_change(self) -> None:
        if hasattr(self, "modInfoPanel"):
            self.modInfoPanel.refresh_icons()

    def _setup_shoulder_indicators(self) -> None:
        SH = ICON_SIZE
        base = os.path.join(paths.BASE_DIR, "assets", "controller")
        self._shoulder_indicators = []

        for panel, btn_name in (
            (self._left_panel, "LEFT_SHOULDER"),
            (self.modInfoPanel, "RIGHT_SHOULDER"),
        ):
            lbl = QLabel(panel)
            lbl.setFixedSize(SH, SH)
            path = os.path.join(base, f"{btn_name}.png")
            pm = QPixmap(path)
            if not pm.isNull():
                lbl.setPixmap(scaled_pixmap(pm, SH))
            lbl.hide()
            panel.installEventFilter(self)
            self._shoulder_indicators.append((lbl, panel))

    def _reposition_shoulder_indicators(self) -> None:
        SH = ICON_SIZE
        for lbl, panel in self._shoulder_indicators:
            if panel is self._left_panel:
                lbl.move(panel.width() - SH - 4, 4)
            else:
                lbl.move(4, 4)
            lbl.raise_()

    def _init_controller(self) -> None:
        if not config.controller_enabled:
            return
        try:
            self._controller = ControllerManager(self)
            self._router = ControllerRouter(self._controller)
            self._router.register_global(
                {
                    Button.BACK: self._open_settings,
                    Button.LEFT_SHOULDER: self._focus_modlist,
                    Button.RIGHT_SHOULDER: self._focus_modinfo,
                }
            )
            self._focus_overlays = (
                FocusOverlay(self.modInfoPanel),
                FocusOverlay(self._left_panel),
            )
            self._controller_focus = None
            self._setup_shoulder_indicators()
            self._controller.connected.connect(self._on_controller_connected)
            self._controller.disconnected.connect(self._on_controller_disconnected)
            self._controller.activity_changed.connect(self._on_controller_activity)
            self.mod_list_panel.set_controller(self._controller, self._router)
            self.modInfoPanel.set_controller(self._controller, self._router)

            if self._controller.is_connected:
                self._on_controller_connected(
                    self._controller.gamepad_name, self._controller.gamepad_type
                )
            if self._controller.is_active:
                self._on_controller_activity(True)
        except Exception as exc:
            self.log(f"Controller support unavailable: {exc}", "warning")

    def _load_base_qss(self) -> None:
        qss_path = os.path.join(paths.BASE_DIR, "assets", "styles.qss")
        if os.path.exists(qss_path):
            with open(qss_path) as f:
                self._base_qss = f.read()
        else:
            self._base_qss = ""
        QApplication.instance().setStyleSheet(self._base_qss)

    def _apply_focus_qss(self, active: bool) -> None:
        if active:
            QApplication.instance().setStyleSheet(
                self._base_qss + self._theme_qss + self.FOCUS_QSS
            )
        else:
            QApplication.instance().setStyleSheet(self._base_qss + self._theme_qss)

    def _on_controller_connected(self, name: str, gp_type: int) -> None:
        self.log(f"Controller connected: {name}", "info")
        self.mod_list_panel.set_controller_type(gp_type)
        self.modInfoPanel.set_controller_type(gp_type)

    def _on_controller_disconnected(self) -> None:
        self.log("Controller disconnected", "warning")
        self._apply_focus_qss(False)
        self.mod_list_panel.set_controller_active(False)
        self.modInfoPanel.set_controller_active(False)

    def _on_controller_activity(self, active: bool) -> None:
        self.mod_list_panel.set_controller_active(active)
        self.modInfoPanel.set_controller_active(active)
        self._apply_focus_qss(active)
        if active:
            self._reposition_shoulder_indicators()
            for lbl, _ in self._shoulder_indicators:
                lbl.show()
            if self._controller_focus is None:
                self._focus_modlist()
        else:
            for ov in self._focus_overlays:
                ov.hide()
            for lbl, _ in self._shoulder_indicators:
                lbl.hide()
            self._controller_focus = None

    def _focus_modlist(self) -> None:
        self.modInfoPanel.stop_preview()
        self._controller_focus = "modlist"
        self._focus_overlays[0].show()
        self._focus_overlays[1].hide()
        lv = self.mod_list_panel.listView
        lv.setFocus()
        if not lv.currentIndex().isValid() and self.mod_list_panel.model.rowCount() > 0:
            lv.setCurrentIndex(self.mod_list_panel.model.index(0, 0))

    def _focus_modinfo(self) -> None:
        self._controller_focus = "modinfo"
        self._focus_overlays[0].hide()
        self._focus_overlays[1].show()
        self.modInfoPanel.setFocus()

    def update_accent_style(self, color: str) -> None:
        self.mod_list_panel.update_accent_color(color)
