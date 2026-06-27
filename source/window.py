"""Main application window and entry point."""

from typing import Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from . import config, game_versions, paths, sorter
from .backup import backup_all, get_backup_root
from .components.console import ConsoleWidget
from .components.dialogs import SEPARATOR_ROLE, SettingsDialog
from .components.modlist import SEPARATOR_SUFFIX, ModListPanel
from .components.workshop import (
    _enqueue_details,
    _get_details_from_cache,
    _init_details_cache,
    _init_workshop_limiter,
    _save_details_cache,
    _sync_workshop_limiter,
)
from .widgets import ModInfoPanel
from .worker import WorkerThread
from .controller import (
    ControllerManager,
    BUTTON_BACK,
    BUTTON_START,
    BUTTON_LEFT_SHOULDER,
    BUTTON_RIGHT_SHOULDER,
)
from .components.controller_ui import ControllerRouter, FocusOverlay


class DragApp(QWidget):
    loaded_mods = config.loaded_mods

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._backup_thread = None
        self._masterlist_thread = None
        self._game_versions_thread = None
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
        _init_details_cache()
        game_versions.fetch_initial()
        paths.setup_symlinks()
        self.initUi()
        self._refresh_masterlist_background()
        self._refresh_game_versions_background()
        self._init_controller()

    def closeEvent(self, close_event) -> None:
        s = config.get_settings()
        s.setValue("ui/window_geometry", self.saveGeometry())
        s.setValue("ui/splitter_state", self._splitter.saveState())
        s.setValue(
            "ui/column_state", self.modInfoPanel.conflicts_tree.header().saveState()
        )
        _sync_workshop_limiter()
        _save_details_cache()
        config.flush()
        if self._controller:
            self._controller.cleanup()
        if hasattr(self, '_router'):
            self._router.cleanup()
        for icon in getattr(self.mod_list_panel, '_controller_icons', []):
            icon.cleanup()
        for icon in getattr(self.modInfoPanel, '_controller_icons', []):
            icon.cleanup()
        for ov in getattr(self, '_focus_overlays', []):
            ov.hide()
            ov.setParent(None)
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

        self.modInfoPanel = ModInfoPanel()
        self.modInfoPanel.log_message.connect(self.console_widget.log)

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

        layout.addWidget(horizontal_splitter, 1)
        layout.addWidget(self.console_widget)

        column_state = s.value("ui/column_state")
        if column_state:
            self.modInfoPanel.restore_column_state(column_state)

    def _on_mod_selected(self, mod_name: str, mod_folder: str, conflicts) -> None:
        if mod_folder and mod_folder.endswith(SEPARATOR_SUFFIX):
            self.modInfoPanel.show_separator(mod_name, mod_folder)
            return
        self.modInfoPanel.show_mod_info(mod_name, mod_folder, None, conflicts)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.exec()

    def _maybe_backup(self) -> None:
        if not config.backup_enabled or not config.mods_path:
            return
        if self._backup_thread:
            return
        self.log("Backing up modified mods...")

        thread = WorkerThread(
            backup_all,
            config.mods_path,
            get_backup_root(config.mods_path),
            list(config.loaded_mods),
        )
        thread.finished.connect(lambda: self.log("Backup complete"))
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_backup_thread", None))
        thread.error.connect(lambda msg: self.log(f"Backup failed: {msg}", "error"))
        thread.error.connect(thread.deleteLater)
        thread.error.connect(lambda: setattr(self, "_backup_thread", None))
        self._backup_thread = thread
        thread.start()

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
        thread = WorkerThread(game_versions.fetch_background)
        thread.finished.connect(
            lambda result: self.log("Game versions updated to latest")
            if result is True
            else None
        )
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_game_versions_thread", None))
        thread.error.connect(
            lambda msg: self.log(f"Game versions fetch failed: {msg}", "warning")
        )
        thread.error.connect(thread.deleteLater)
        thread.error.connect(lambda: setattr(self, "_game_versions_thread", None))
        self._game_versions_thread = thread
        thread.start()

    def _batch_fetch_details(self) -> None:
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
            if _enqueue_details(ws_id):
                enqueued += 1

        if enqueued > 0:
            self.log(f"Queued {enqueued} workshop detail fetches", "info")
            self.modInfoPanel._process_details_queue()

    def _fetch_masterlist(self) -> None:
        thread = WorkerThread(sorter.fetch_background)
        thread.finished.connect(
            lambda result: self.log("Masterlist updated to latest version")
            if result is True
            else None
        )
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_masterlist_thread", None))
        thread.error.connect(
            lambda msg: self.log(f"Masterlist fetch failed: {msg}", "warning")
        )
        thread.error.connect(thread.deleteLater)
        thread.error.connect(lambda: setattr(self, "_masterlist_thread", None))
        self._masterlist_thread = thread
        thread.start()

    def getModList(self) -> None:
        self.mod_list_panel.load_mod_list()

    def log(self, message: str, level: str = "info") -> None:
        self.console_widget.log(message, level)

    def log_colored(self, segments: list[tuple[str, Optional[str]]]) -> None:
        self.console_widget.log_colored(segments)

    def _init_controller(self) -> None:
        if not config.controller_enabled:
            return
        try:
            self._controller = ControllerManager(self)
            self._router = ControllerRouter(self._controller)
            self._router.register_global({
                BUTTON_START: self._open_settings,
                BUTTON_BACK: self._toggle_console,
                BUTTON_LEFT_SHOULDER: self._focus_modlist,
                BUTTON_RIGHT_SHOULDER: self._focus_modinfo,
            })
            self._focus_overlays = (
                FocusOverlay(self.modInfoPanel),
                FocusOverlay(self._left_panel),
            )
            self._controller_focus = None
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
        except Exception:
            self.log("Controller support unavailable", "warning")

    def _on_controller_connected(self, name: str, gp_type: int) -> None:
        self.log(f"Controller connected: {name}", "info")
        self.mod_list_panel.set_controller_type(gp_type)
        self.modInfoPanel.set_controller_type(gp_type)

    def _on_controller_disconnected(self) -> None:
        self.log("Controller disconnected", "warning")
        self.mod_list_panel.set_controller_active(False)
        self.modInfoPanel.set_controller_active(False)

    def _on_controller_activity(self, active: bool) -> None:
        self.mod_list_panel.set_controller_active(active)
        self.modInfoPanel.set_controller_active(active)
        if active:
            if self._controller_focus is None:
                self._focus_modlist()
        else:
            for ov in self._focus_overlays:
                ov.hide()
            self._controller_focus = None

    def _toggle_console(self) -> None:
        self.console_widget.setVisible(not self.console_widget.isVisible())

    def _focus_modlist(self) -> None:
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
