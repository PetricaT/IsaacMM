"""Mod info panel and preview widgets."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Optional

from PySide6.QtCore import (
    QByteArray,
    QDateTime,
    QEvent,
    QFileInfo,
    QLocale,
    QPoint,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImageReader,
    QMovie,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileIconProvider,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import config, game_versions, logger, paths
from .components.controller_ui import (
    BUTTON_SIZE,
    ICON_SIZE,
    AxisScroller,
    ControllerButtonIcon,
    ControllerRouter,
)
from .components.file_utils import open_path, open_url
from .components.modlist import normalize_mod_name
from .components.preview import PreviewWidget
from .components.text_utils import bbcode_to_html
from .components.workshop import (
    _check_workshop_rate_limit,
    _dequeue_details,
    _dequeue_workshop,
    _download_workshop_icon,
    _enqueue_details,
    _enqueue_workshop,
    _fetch_workshop_details,
    _get_details_from_cache,
    _is_permanent_failure,
    _is_recent_failure,
    _mark_details_pending,
    _mark_pending,
    _prune_failures,
    _record_failure,
    _requeue_details,
    _requeue_workshop,
    _set_details_in_cache,
    _unmark_details_pending,
    _unmark_pending,
)
from .worker import ManagedWorker


def _format_date(ts: Optional[float]) -> str:
    if not ts:
        return "?"
    try:
        if config.date_format:
            return datetime.fromtimestamp(ts).strftime(config.date_format)
        qdt = QDateTime.fromSecsSinceEpoch(int(ts))
        return QLocale().toString(qdt, QLocale.FormatType.ShortFormat)
    except (OSError, ValueError):
        return "?"


class ConflictTreeWidget(QTreeWidget):
    merge_requested = Signal(str)  # relative file path

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self._imagediff_path: str | None = None

    def _find_imagediff(self) -> str | None:
        if self._imagediff_path is not None:
            return self._imagediff_path
        candidates = [
            shutil.which("imagediff"),
            os.path.expanduser("~/.local/bin/imagediff"),
            "/usr/local/bin/imagediff",
            "/usr/bin/imagediff",
        ]
        for path in candidates:
            if path and os.path.isfile(path):
                self._imagediff_path = path
                return path
        return None

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self.itemAt(pos)
        if item is None or item.childCount():
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return
        _conflict_folder, relative_path = data
        if not relative_path.lower().endswith(".png"):
            return
        imagediff = self._find_imagediff()
        if imagediff is None:
            logger.log("debug", "imagediff not found on PATH (checked PATH, ~/.local/bin, /usr/local/bin, /usr/bin)")
            return
        logger.log("debug", f"imagediff found at {imagediff}")
        menu = QMenu(self)
        action = menu.addAction("Merge with imagediff")
        action.triggered.connect(lambda: self.merge_requested.emit(relative_path))
        menu.exec(self.viewport().mapToGlobal(pos))


class ModInfoPanel(QWidget):
    log_message = Signal(str, str)  # message, level

    PRIORITY_ICON_NAMES: list[str] = [
        "title",
        "thumbnail",
        "Thumbnail",
        "icon",
        "images",
        "modicon",
        "logo",
        "spider thumbnail",
    ]
    IMAGE_EXTENSIONS: set[str] = {".png", ".jpg", ".jpeg", ".gif"}

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._movie = QMovie()
        self._movie.setScaledSize(QSize(128, 128))
        self._mod_path: Optional[str] = None
        self._workshop_id_str: Optional[str] = None
        self._icon_worker = ManagedWorker(parent=self)
        self._icon_worker.finished.connect(self._on_icon_done)
        self._icon_worker.error.connect(self._on_icon_error)
        self._icon_queue_timer = QTimer(self)
        self._icon_queue_timer.setSingleShot(True)
        self._icon_queue_timer.timeout.connect(self._process_icon_queue)
        self._details_worker = ManagedWorker(parent=self)
        self._details_worker.finished.connect(self._on_details_done)
        self._details_worker.error.connect(self._on_details_error)
        self._details_queue_timer = QTimer(self)
        self._details_queue_timer.setSingleShot(True)
        self._details_queue_timer.timeout.connect(self._process_details_queue)
        self._init_icons()
        modinfo_label = QLabel("<b>Mod Info</b>")
        modinfo_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(modinfo_label)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(128, 128)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(
            f"border: 1px solid {config.icon_border_color or 'palette(mid)'};"
        )

        self.tags_box = QListWidget()
        self.tags_box.setMaximumHeight(128)
        self.tags_box.setSelectionMode(QAbstractItemView.NoSelection)
        self.tags_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tags_box.setFlow(QListWidget.LeftToRight)
        self.tags_box.setWrapping(True)
        self.tags_box.setSpacing(4)

        self.workshop_button = QPushButton("Steam Workshop")
        self.workshop_button.clicked.connect(self._open_workshop)
        self.workshop_button.setEnabled(False)

        self.folder_button = QPushButton("Open Folder")
        self.folder_button.clicked.connect(self._open_folder)
        self.folder_button.setEnabled(False)

        button_column = QVBoxLayout()
        button_column.addWidget(self.workshop_button)
        button_column.addWidget(self.folder_button)

        self.created_label = QLabel()
        self.updated_label = QLabel()
        self.updated_label.setTextFormat(Qt.RichText)

        self.dates_widget = QWidget()
        dates_layout = QVBoxLayout(self.dates_widget)
        dates_layout.setContentsMargins(0, 0, 0, 0)
        dates_layout.setSpacing(2)
        dates_layout.addWidget(self.created_label)
        dates_layout.addWidget(self.updated_label)
        self.dates_widget.setVisible(False)

        right_column = QVBoxLayout()
        right_column.addWidget(self.tags_box)
        right_column.addWidget(self.dates_widget)
        right_column.addStretch()

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.icon_label)
        top_layout.addLayout(right_column, 1)
        top_layout.addLayout(button_column)

        self._top_container = QWidget()
        self._top_container.setLayout(top_layout)
        self._top_container.setFixedHeight(148)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.stop_preview)

        self._controller_dpad_icons: list[QLabel] = []

        self._left_dpad_icon = QLabel()
        self._left_dpad_icon.setFixedSize(BUTTON_SIZE, ICON_SIZE)
        self._left_dpad_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._left_dpad_icon.hide()
        self.tabs.setCornerWidget(self._left_dpad_icon, Qt.Corner.TopLeftCorner)
        self._controller_dpad_icons.append(self._left_dpad_icon)

        self._right_dpad_icon = QLabel()
        self._right_dpad_icon.setFixedSize(BUTTON_SIZE, ICON_SIZE)
        self._right_dpad_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._right_dpad_icon.hide()
        self.tabs.setCornerWidget(self._right_dpad_icon, Qt.Corner.TopRightCorner)
        self._controller_dpad_icons.append(self._right_dpad_icon)

        self._load_dpad_icons()

        self.description_text = QTextBrowser()
        self.description_text.setPlaceholderText("Select a mod to view its description")
        self.description_text.setOpenExternalLinks(False)
        self.description_text.anchorClicked.connect(self._open_link)
        self.tabs.addTab(self.description_text, "Description")

        self.conflicts_tree = ConflictTreeWidget()
        self.conflicts_tree.setHeaderLabels(["Mod", "File"])
        self.conflicts_tree.setRootIsDecorated(True)
        self.conflicts_tree.setAlternatingRowColors(True)
        self.conflicts_tree.header().setStretchLastSection(False)
        self.conflicts_tree.header().setSectionResizeMode(0, QHeaderView.Interactive)
        self.conflicts_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.conflicts_tree.header().resizeSection(0, 200)
        self.conflicts_tree.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.conflicts_tree.itemDoubleClicked.connect(self._open_conflict_file)
        self.conflicts_tree.viewport().installEventFilter(self)
        self.conflicts_tree.viewport().setMouseTracking(True)
        self._preview = PreviewWidget(self)
        QApplication.instance().applicationStateChanged.connect(
            lambda state: (
                self._preview.stop()
                if state == Qt.ApplicationState.ApplicationInactive
                else None
            )
        )
        self.conflicts_tree.verticalScrollBar().valueChanged.connect(
            self._on_preview_tree_scroll
        )
        self.tabs.addTab(self.conflicts_tree, "Conflicts")
        self.conflicts_tree.merge_requested.connect(self._on_merge_requested)

        self.files_tree = QTreeWidget()
        self.files_tree.setHeaderLabels(["Name"])
        self.files_tree.setRootIsDecorated(True)
        self.files_tree.setAlternatingRowColors(True)
        self.files_tree.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.files_tree.itemDoubleClicked.connect(self._open_file)
        self.files_tree.viewport().installEventFilter(self)
        self.files_tree.viewport().setMouseTracking(True)
        self.files_tree.verticalScrollBar().valueChanged.connect(
            self._on_preview_tree_scroll
        )
        self.tabs.addTab(self.files_tree, "Files")

        self.folder_label = QPushButton()
        self.folder_label.setFlat(True)
        self.folder_label.setStyleSheet(
            f"QPushButton {{ color: {config.folder_label_color or 'palette(text)'}; text-align: left; border: none; }}"
        )
        self.folder_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_label.clicked.connect(self._open_folder)

        layout.addWidget(self._top_container)
        layout.addWidget(self.tabs)
        layout.addWidget(self.folder_label)

    def _init_icons(self) -> None:
        self._folder_icon = QIcon.fromTheme("folder")
        self._file_icon_provider = QFileIconProvider()
        theme_pm = QIcon.fromTheme("image-x-generic").pixmap(128, 128)
        if not theme_pm.isNull():
            self._placeholder = theme_pm
        else:
            self._placeholder = QPixmap(
                os.path.join(paths.BASE_DIR, "assets", "ui", "no_image.png")
            )

    def _get_file_icon(self, full_path: str) -> QIcon:
        return self._file_icon_provider.icon(QFileInfo(full_path))

    def refresh_icons(self) -> None:
        self._init_icons()
        self._update_tree_icons(self.files_tree.invisibleRootItem())
        self._update_tree_icons(self.conflicts_tree.invisibleRootItem())
        self._show_placeholder()

    def _update_tree_icons(self, parent: QTreeWidgetItem) -> None:
        for i in range(parent.childCount()):
            item = parent.child(i)
            if item.childCount():
                item.setIcon(0, self._folder_icon)
                self._update_tree_icons(item)

    def show_mod_info(
        self,
        mod_name: str,
        mod_folder: Optional[str] = None,
        check_state=None,
        conflicts: Optional[dict] = None,
    ) -> None:
        if not mod_folder:
            for loaded_mod in config.loaded_mods:
                if loaded_mod[0] == mod_name:
                    mod_folder = loaded_mod[1]
                    break

        if not mod_folder:
            self.clear()
            return

        self.tabs.setEnabled(True)
        full_mod_path = os.path.join(config.mods_path, mod_folder)
        self._mod_path = full_mod_path
        self.folder_button.setEnabled(True)

        icon_path = None
        try:
            directory_entries = os.listdir(full_mod_path)
            file_name_set = set(directory_entries)
            for priority_name in self.PRIORITY_ICON_NAMES:
                for image_extension in self.IMAGE_EXTENSIONS:
                    candidate = f"{priority_name}{image_extension}"
                    if candidate in file_name_set:
                        icon_path = os.path.join(full_mod_path, candidate)
                        break
                if icon_path:
                    break
            if icon_path is None:
                for file_name in directory_entries:
                    if os.path.splitext(file_name.lower())[1] in self.IMAGE_EXTENSIONS:
                        icon_path = os.path.join(full_mod_path, file_name)
                        break
        except OSError:
            pass

        self._stop_movie()
        if icon_path:
            if icon_path.lower().endswith(".gif") and config.animate_icons:
                self._movie.setFileName(icon_path)
                if self._movie.isValid():
                    self.icon_label.setMovie(self._movie)
                    self._movie.start()
                else:
                    self._show_placeholder()
            else:
                loaded_pixmap = QPixmap(icon_path)
                if not loaded_pixmap.isNull():
                    self.icon_label.setPixmap(
                        loaded_pixmap.scaled(
                            128,
                            128,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.FastTransformation,
                        )
                    )
                else:
                    self._show_placeholder()
        else:
            if not config.download_icons or not self._try_download_icon(
                mod_folder, mod_name
            ):
                self._show_placeholder()

        self.conflicts_tree.clear()
        if conflicts:
            for conflict_mod_name, conflict_data in sorted(conflicts.items()):
                conflict_folder = conflict_data["folder"]
                overwrite_color = (
                    config.win_color
                    if conflict_data["overwrites"]
                    else config.lose_color
                )
                mod_tree_item = QTreeWidgetItem([conflict_mod_name, ""])
                mod_tree_item.setForeground(0, QColor(overwrite_color))
                fnt = mod_tree_item.font(0)
                fnt.setBold(True)
                mod_tree_item.setFont(0, fnt)
                self._populate_file_tree(
                    mod_tree_item, conflict_data["files"], conflict_folder
                )
                self.conflicts_tree.addTopLevelItem(mod_tree_item)
            self.conflicts_tree.expandAll()

        overwritten_files: set[str] = set()
        if conflicts:
            for conflict_data in conflicts.values():
                if not conflict_data["overwrites"]:
                    for f in conflict_data["files"]:
                        overwritten_files.add(f.replace("\\", "/"))

        self.files_tree.clear()
        root_item = QTreeWidgetItem([mod_folder])
        root_item.setIcon(0, self._folder_icon)
        root_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        self.files_tree.addTopLevelItem(root_item)
        self._populate_mod_files(
            root_item, full_mod_path, "", mod_folder, overwritten_files
        )
        self.files_tree.expandAll()

        try:
            metadata_tree = ET.parse(os.path.join(full_mod_path, "metadata.xml"))
            xml_root = metadata_tree.getroot()
            description_element = xml_root.find("description")
            if description_element is not None and description_element.text:
                self.description_text.setHtml(
                    bbcode_to_html(description_element.text.strip())
                )
            else:
                self.description_text.setHtml("(no description)")

            self.tags_box.clear()
            tags_element = xml_root.find("tags")
            if tags_element is not None:
                tag_elements = tags_element.findall("tag")
            else:
                tag_elements = xml_root.findall("tag")
            for tag_element in tag_elements:
                tag_id = tag_element.get("id", "")
                if not tag_id:
                    continue
                tag_item = QListWidgetItem(tag_id)
                if config.tag_bg:
                    tag_item.setBackground(QColor(config.tag_bg))
                if config.tag_fg:
                    tag_item.setForeground(QColor(config.tag_fg))
                self.tags_box.addItem(tag_item)

        except Exception as exc:
            logger.log("error", f"Failed to load mod description: {exc}")
            self.description_text.setHtml("(could not load description)")

        self.folder_label.setText(f"Folder: {mod_folder}")

        workshop_match = paths.WORKSHOP_ID_RE.search(mod_folder)
        self._workshop_id_str = workshop_match.group(1) if workshop_match else None
        self._workshop_id = (
            int(self._workshop_id_str) if self._workshop_id_str else None
        )
        self.workshop_button.setEnabled(self._workshop_id is not None)

        if self._workshop_id_str is not None:
            self._update_workshop_dates(self._workshop_id_str)
            if _get_details_from_cache(self._workshop_id_str) is None:
                if _enqueue_details(self._workshop_id_str):
                    if not self._details_queue_timer.isActive():
                        self._process_details_queue()
        else:
            self.dates_widget.setVisible(False)

    def _show_placeholder(self) -> None:
        self._stop_movie()
        self.icon_label.setPixmap(
            self._placeholder.scaled(
                128,
                128,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )

    def _stop_movie(self) -> None:
        self._movie.stop()

    def _try_download_icon(self, mod_folder: str, mod_name: str = "") -> bool:
        ws_match = paths.WORKSHOP_ID_RE.search(mod_folder)
        if not ws_match:
            return False
        ws_id = ws_match.group(1)
        normalized_name = normalize_mod_name(mod_name or mod_folder)
        cache_dir = os.path.join(paths.cache_dir, "icons")
        cached_path = os.path.join(cache_dir, f"{ws_id}.png")

        if os.path.isfile(cached_path):
            loaded = QPixmap(cached_path)
            if not loaded.isNull():
                self.icon_label.setPixmap(
                    loaded.scaled(
                        128,
                        128,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.FastTransformation,
                    )
                )
                return True

        _prune_failures()
        if _is_permanent_failure(ws_id):
            return False
        if _is_recent_failure(ws_id):
            return False

        if _enqueue_workshop(ws_id, normalized_name):
            if not self._icon_queue_timer.isActive():
                self._process_icon_queue()
        return False

    def _process_icon_queue(self) -> None:
        if not config.download_icons:
            return
        if self._icon_worker.is_running:
            return

        item = _dequeue_workshop()
        if item is None:
            return
        ws_id, normalized_name = item

        if not _check_workshop_rate_limit():
            _requeue_workshop(ws_id, normalized_name)
            self._icon_queue_timer.start(2000)
            return

        self.log_message.emit(
            f"Downloading thumbnail for: {normalized_name} {ws_id}", "info"
        )

        cache_dir = os.path.join(paths.cache_dir, "icons")
        cached_path = os.path.join(cache_dir, f"{ws_id}.png")
        self._icon_ws_id = ws_id
        self._icon_cached_path = cached_path
        _mark_pending(ws_id)

        if not self._icon_worker.start(
            _download_workshop_icon,
            ws_id,
            cached_path,
            name="IconDownload",
        ):
            _unmark_pending(ws_id)
            self._icon_queue_timer.start(2000)

    def _on_icon_done(self, actual_path: str) -> None:
        ws_id = self._icon_ws_id
        cached_path = self._icon_cached_path
        _unmark_pending(ws_id)
        img_loaded = False
        if actual_path and actual_path != cached_path:
            reader = QImageReader(actual_path)
            img = reader.read()
            if not img.isNull():
                img.save(cached_path, "PNG")
                try:
                    os.remove(actual_path)
                except OSError:
                    pass
        loaded = QPixmap(cached_path)
        if not loaded.isNull():
            self.icon_label.setPixmap(
                loaded.scaled(
                    128,
                    128,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
            )
            img_loaded = True
        if not img_loaded:
            self._show_placeholder()
        self._icon_queue_timer.start(2000)

    def _on_icon_error(self, msg: str) -> None:
        _unmark_pending(self._icon_ws_id)
        _record_failure(self._icon_ws_id, time.time())
        self.log_message.emit(msg, "warning")
        self._show_placeholder()
        self._icon_queue_timer.start(2000)

    def _update_workshop_dates(self, ws_id: str) -> None:
        cached = _get_details_from_cache(ws_id)
        if cached is None:
            self.dates_widget.setVisible(False)
            return

        self.dates_widget.setVisible(True)

        ts_created = cached.get("time_created")
        ts_updated = cached.get("time_updated")

        if ts_created is None and ts_updated is None:
            self.created_label.setText("Created: —")
            self.created_label.setStyleSheet(
                f"color: {config.folder_label_color or 'palette(text)'};"
            )
            self.updated_label.setText(
                f"<span style='color:{config.workshop_missing_color};'>Not found on Steam Workshop</span>"
            )
            return

        created_str = _format_date(ts_created)
        self.created_label.setText(f"Created: {created_str}")
        self.created_label.setStyleSheet(
            f"color: {config.folder_label_color or 'palette(text)'};"
        )

        updated_str = _format_date(ts_updated) if ts_updated else "Never"

        badge_date = ts_updated or ts_created
        latest_game, previous_major = game_versions.get_outdated_thresholds()
        badge = ""
        color = config.workshop_badge_default
        if latest_game is not None and badge_date:
            try:
                badge_dt = datetime.fromtimestamp(badge_date).date()
                if badge_dt >= latest_game:
                    color = config.workshop_badge_current
                elif previous_major is None or badge_dt >= previous_major:
                    color = config.workshop_badge_possible
                    badge = " (Possibly outdated)"
                else:
                    color = config.workshop_badge_outdated
                    badge = " (OUTDATED)"
            except (OSError, ValueError):
                pass

        self.updated_label.setText(
            f"Updated: {updated_str}<span style='color:{color}; font-weight:bold;'>{badge}</span>"
        )

    def _process_details_queue(self) -> None:
        if not config.download_icons:
            return
        if self._details_worker.is_running:
            return

        ws_id = _dequeue_details()
        if ws_id is None:
            return

        if not _check_workshop_rate_limit():
            _requeue_details(ws_id)
            self._details_queue_timer.start(5000)
            return

        self._details_ws_id = ws_id
        _mark_details_pending(ws_id)

        if not self._details_worker.start(
            _fetch_workshop_details,
            ws_id,
            name="WorkshopDetails",
        ):
            _unmark_details_pending(ws_id)
            self._details_queue_timer.start(2000)

    def _on_details_done(self, result: dict) -> None:
        ws_id = self._details_ws_id
        _unmark_details_pending(ws_id)
        _set_details_in_cache(ws_id, result)
        if self._workshop_id_str == ws_id:
            self._update_workshop_dates(ws_id)
        self._details_queue_timer.start(2000)

    def _on_details_error(self, msg: str) -> None:
        _unmark_details_pending(self._details_ws_id)
        self.log_message.emit(msg, "warning")
        self._details_queue_timer.start(10000)

    def _open_link(self, url: QUrl) -> None:
        if not open_url(url.toString()):
            logger.log("error", f"Failed to open URL: {url}")

    def _open_workshop(self) -> None:
        if self._workshop_id:
            url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={self._workshop_id}"
            if not open_url(url):
                logger.log("error", f"Failed to open workshop page: {url}")

    def _open_folder(self) -> None:
        if self._mod_path and os.path.isdir(self._mod_path):
            if not open_path(self._mod_path):
                logger.log("error", f"Failed to open folder: {self._mod_path}")

    def _populate_file_tree(
        self, parent_item, file_paths: list, conflict_folder: str
    ) -> None:
        path_tree = {}
        for relative_path in file_paths:
            normalized = relative_path.replace("\\", "/")
            parts = normalized.split("/")
            current_level = path_tree
            for segment in parts:
                current_level = current_level.setdefault(segment, {})

        def add_branches(subtree, parent, accumulated_path=""):
            for name in sorted(
                subtree.keys(), key=lambda k: (not subtree[k], k.lower())
            ):
                child_subtree = subtree[name]
                segment_path = (
                    f"{accumulated_path}/{name}" if accumulated_path else name
                )
                if child_subtree:
                    folder_item = QTreeWidgetItem([name, ""])
                    folder_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                    folder_item.setIcon(0, self._folder_icon)
                    parent.addChild(folder_item)
                    add_branches(child_subtree, folder_item, segment_path)
                else:
                    file_item = QTreeWidgetItem(["", name])
                    file_item.setData(
                        0, Qt.ItemDataRole.UserRole, (conflict_folder, segment_path)
                    )
                    file_item.setIcon(
                        0,
                        self._get_file_icon(
                            os.path.join(conflict_folder, segment_path)
                        ),
                    )
                    parent.addChild(file_item)

        add_branches(path_tree, parent_item)

    def _populate_mod_files(
        self,
        parent_item,
        current_path: str,
        relative_prefix: str,
        mod_folder: str,
        overwritten_files: set[str] | None = None,
    ) -> None:
        try:
            entries = sorted(os.listdir(current_path))
        except OSError:
            return
        for entry in entries:
            if entry in config.ignored_items:
                continue
            full_entry = os.path.join(current_path, entry)
            rel_path = f"{relative_prefix}/{entry}" if relative_prefix else entry
            if os.path.isdir(full_entry):
                dir_item = QTreeWidgetItem([entry])
                dir_item.setIcon(0, self._folder_icon)
                dir_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                parent_item.addChild(dir_item)
                self._populate_mod_files(
                    dir_item, full_entry, rel_path, mod_folder, overwritten_files
                )
            else:
                file_item = QTreeWidgetItem([entry])
                file_item.setData(0, Qt.ItemDataRole.UserRole, (mod_folder, rel_path))
                file_item.setIcon(0, self._get_file_icon(full_entry))
                if overwritten_files and rel_path in overwritten_files:
                    font = file_item.font(0)
                    font.setItalic(True)
                    file_item.setFont(0, font)
                parent_item.addChild(file_item)

    def _open_file(self, item, column) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, tuple):
            return
        mod_folder, relative_path = data
        full_path = os.path.join(config.mods_path, mod_folder, relative_path)
        if not os.path.exists(full_path):
            logger.log("warning", f"Path does not exist: {full_path}")
            return
        ext = os.path.splitext(full_path.lower())[1]
        if sys.platform == "darwin" and ext in {".png", ".jpg", ".jpeg", ".gif"}:
            subprocess.Popen(
                ["qlmanage", "-p", full_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        ctrl_pressed = (
            QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier
        )
        if ctrl_pressed:
            if not open_path(os.path.dirname(full_path)):
                logger.log(
                    "error", f"Failed to open folder: {os.path.dirname(full_path)}"
                )
        else:
            if not open_path(full_path):
                logger.log("error", f"Failed to open file: {full_path}")

    def save_column_state(self) -> bytes:
        return bytes(self.conflicts_tree.header().saveState())

    def restore_column_state(self, state_data: QByteArray) -> None:
        if state_data:
            self.conflicts_tree.header().restoreState(state_data)
        self.conflicts_tree.header().setSectionResizeMode(0, QHeaderView.Interactive)
        self.conflicts_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)

    def _on_merge_requested(self, relative_path: str) -> None:
        images: list[str] = []
        found_mods: list[str] = []
        for i in range(self.conflicts_tree.topLevelItemCount()):
            mod_item = self.conflicts_tree.topLevelItem(i)
            mod_name = mod_item.text(0)
            if mod_name == "MERGED":
                continue
            before = len(images)
            self._walk_for_conflict_file(mod_item, relative_path, mod_name, images)
            if len(images) > before:
                found_mods.append(mod_name)
            logger.log(
                "debug",
                f"Merge: scanned top-level {mod_name!r} -> {'MATCH' if len(images) > before else 'no match'}",
            )
        selected_full = os.path.join(self._mod_path, relative_path)
        if os.path.isfile(selected_full):
            images.append(selected_full)
            found_mods.append(os.path.basename(self._mod_path))
            logger.log("debug", f"Merge: added selected mod: {os.path.basename(self._mod_path)}")
        else:
            logger.log(
                "debug",
                f"Merge: selected mod has no file at {selected_full}",
            )
        logger.log(
            "debug",
            f"Merge: collected {len(images)} file(s) for {relative_path!r} "
            f"in {len(found_mods)} mod(s): {found_mods}",
        )
        for fp in images:
            logger.log("debug", f"  Merge candidate: {fp}")
        if len(images) < 2:
            logger.log("warning", "Need at least 2 versions of the image to merge")
            return
        loaded = [e[1] for e in config.loaded_mods]
        images.sort(key=lambda p: (
            loaded.index(os.path.basename(os.path.dirname(p)))
            if os.path.basename(os.path.dirname(p)) in loaded
            else len(loaded)
        ))
        logger.log(
            "debug",
            f"Merge: sorted order: {[os.path.basename(os.path.dirname(p)) for p in images]}",
        )
        merged_dir = os.path.join(config.mods_path, "MERGED")
        os.makedirs(merged_dir, exist_ok=True)
        meta_path = os.path.join(merged_dir, "metadata.xml")
        if not os.path.isfile(meta_path):
            try:
                with open(meta_path, "w", encoding="utf-8") as f:
                    f.write('<?xml version="1.0" encoding="utf-8"?>\n')
                    f.write('<metadata>\n')
                    f.write('  <name>MERGED</name>\n')
                    f.write('  <description>Output folder for imagediff merges</description>\n')
                    f.write('</metadata>\n')
            except OSError:
                pass
        output = os.path.join(merged_dir, relative_path)
        os.makedirs(os.path.dirname(output), exist_ok=True)
        imagediff = self.conflicts_tree._find_imagediff()
        if imagediff is None:
            logger.log("error", "imagediff not found on PATH")
            return
        subprocess.Popen(
            [imagediff, "--output", output, *images],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.log("info", f"Merge: launched imagediff for {relative_path}")

    @staticmethod
    def _walk_for_conflict_file(
        item: QTreeWidgetItem,
        target_path: str,
        mod_name: str,
        images: list[str],
    ) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is not None:
            child_folder, child_path = data
            if child_path == target_path:
                full = os.path.join(config.mods_path, child_folder, target_path)
                if os.path.isfile(full):
                    images.append(full)
                else:
                    logger.log(
                        "debug",
                        f"Merge: {mod_name} claims {target_path} but file not found at {full}",
                    )
                return
        for ci in range(item.childCount()):
            ModInfoPanel._walk_for_conflict_file(
                item.child(ci), target_path, mod_name, images
            )

    def _open_conflict_file(self, item, tree_column: int) -> None:
        conflict_data = item.data(0, Qt.ItemDataRole.UserRole)
        if conflict_data is None:
            return
        conflict_folder, relative_file_path = conflict_data
        full_path = os.path.join(config.mods_path, conflict_folder, relative_file_path)
        if not os.path.exists(full_path):
            logger.log("warning", f"Path does not exist: {full_path}")
            return
        ctrl_pressed = (
            QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier
        )
        if ctrl_pressed:
            if not open_path(os.path.dirname(full_path)):
                logger.log(
                    "error", f"Failed to open folder: {os.path.dirname(full_path)}"
                )
        else:
            if not open_path(full_path):
                logger.log("error", f"Failed to open file: {full_path}")

    def eventFilter(self, obj, event) -> bool:
        tree = None
        if obj is self.conflicts_tree.viewport():
            tree = self.conflicts_tree
        elif obj is self.files_tree.viewport():
            tree = self.files_tree
        if tree is not None:
            if event.type() == QEvent.MouseMove:
                if config.preview_images:
                    item = tree.itemAt(event.pos())
                    if item and not item.childCount():
                        data = item.data(0, Qt.ItemDataRole.UserRole)
                        if data:
                            mod_folder, relative_path = data
                            full_path = os.path.join(
                                config.mods_path, mod_folder, relative_path
                            )
                            if relative_path.lower().endswith((".png", ".anm2")):
                                if self._preview.show_preview(
                                    full_path, event.globalPos()
                                ):
                                    return False
                self._preview.stop()
                return False
            if event.type() == QEvent.Leave:
                self._preview.stop()
                return False
        return super().eventFilter(obj, event)

    def _on_preview_tree_scroll(self) -> None:
        if not config.preview_images:
            return
        cursor = self.mapFromGlobal(self.cursor().pos())
        for tree in (self.conflicts_tree, self.files_tree):
            if tree.viewport().geometry().contains(cursor):
                pos = tree.viewport().mapFrom(self, cursor)
                item = tree.itemAt(pos)
                if item and not item.childCount():
                    data = item.data(0, Qt.ItemDataRole.UserRole)
                    if data:
                        mod_folder, relative_path = data
                        full_path = os.path.join(
                            config.mods_path, mod_folder, relative_path
                        )
                        if relative_path.lower().endswith((".png", ".anm2")):
                            if self._preview.show_preview(
                                full_path, self.cursor().pos()
                            ):
                                return
                self._preview.stop()
                return

    def show_separator(self, separator_name: str, folder: str) -> None:
        self._stop_movie()
        self._preview.stop()
        self._show_placeholder()
        self.description_text.clear()
        self.conflicts_tree.clear()
        self.tags_box.clear()
        self._workshop_id = None
        self._workshop_id_str = None
        self._mod_path = os.path.join(config.mods_path, folder)
        self.folder_button.setEnabled(True)
        self.folder_label.setText(f"Separator: {separator_name}")
        self.workshop_button.setEnabled(False)
        self.dates_widget.setVisible(False)
        self.tabs.setEnabled(False)

    def set_controller(self, controller_mgr, router: ControllerRouter) -> None:
        from .controller import Button

        router.register(
            self,
            {
                Button.NORTH: self._open_workshop,
                Button.WEST: self._open_folder,
                Button.DPAD_LEFT: self._controller_prev_tab,
                Button.DPAD_RIGHT: self._controller_next_tab,
                Button.DPAD_UP: self._controller_scroll_up,
                Button.DPAD_DOWN: self._controller_scroll_down,
            },
        )
        self._controller_icons = []
        for btn_enum, widget in [
            (Button.NORTH, self.workshop_button),
            (Button.WEST, self.folder_button),
        ]:
            icon = ControllerButtonIcon(widget, btn_enum, controller_mgr)
            self._controller_icons.append(icon)
        self._axis_scroller = AxisScroller(self._controller_scroll_with_dir, self)
        controller_mgr.axis_moved.connect(self._axis_scroller.handle_axis)
        controller_mgr.activity_changed.connect(self._on_controller_activity)
        is_active = getattr(controller_mgr, "is_active", True)
        self._on_controller_activity(is_active)

    def set_controller_type(self, gp_type: int) -> None:
        for icon in getattr(self, "_controller_icons", []):
            icon._on_connected("", gp_type)

    def set_controller_active(self, active: bool) -> None:
        for icon in getattr(self, "_controller_icons", []):
            icon._on_activity_changed(active)
        self._on_controller_activity(active)

    def _on_controller_activity(self, active: bool) -> None:
        for lbl in self._controller_dpad_icons:
            lbl.setVisible(active)

    def _load_dpad_icons(self) -> None:
        simple = config.controller_simple_icons
        base = os.path.join(paths.BASE_DIR, "assets", "controller")
        if simple:
            base = os.path.join(base, "simple")

        for lbl, name in (
            (self._left_dpad_icon, "left"),
            (self._right_dpad_icon, "right"),
        ):
            path = os.path.join(base, f"{name}.png")
            pm = QPixmap(path)
            if not pm.isNull():
                scaled = pm.scaled(
                    ICON_SIZE,
                    ICON_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                lbl.setPixmap(scaled)
            else:
                lbl.clear()

    def set_simple_icons(self, enabled: bool) -> None:
        for icon in getattr(self, "_controller_icons", []):
            icon.set_simple_mode(enabled)
        self._load_dpad_icons()

    def _controller_prev_tab(self) -> None:
        i = self.tabs.currentIndex()
        if i > 0:
            self.tabs.setCurrentIndex(i - 1)
            self.tabs.currentWidget().setFocus()

    def _controller_next_tab(self) -> None:
        i = self.tabs.currentIndex()
        if i < self.tabs.count() - 1:
            self.tabs.setCurrentIndex(i + 1)
            self.tabs.currentWidget().setFocus()

    def _controller_trigger_preview(self, tree: QTreeWidget) -> None:
        if not config.preview_images:
            return
        item = tree.currentItem()
        if not item or item.childCount():
            self._preview.stop()
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            self._preview.stop()
            return
        mod_folder, relative_path = data
        full_path = os.path.join(config.mods_path, mod_folder, relative_path)
        if relative_path.lower().endswith((".png", ".anm2")):
            vp = tree.viewport()
            center = vp.mapToGlobal(vp.rect().center())
            self._preview.show_preview(full_path, center, debounce=False)

    def _controller_nav_up(self, w: QWidget) -> None:
        if isinstance(w, QTreeWidget):
            item = w.currentItem()
            if item:
                prev = w.itemAbove(item)
                if prev:
                    w.setCurrentItem(prev)
                    w.scrollToItem(prev)
                    self._controller_trigger_preview(w)
            else:
                first = w.topLevelItem(0)
                if first:
                    w.setCurrentItem(first)
                    w.scrollToItem(first)
                    self._controller_trigger_preview(w)
        else:
            sb = w.verticalScrollBar() if hasattr(w, "verticalScrollBar") else None
            if sb:
                sb.setValue(sb.value() - sb.singleStep())

    def _controller_nav_down(self, w: QWidget) -> None:
        if isinstance(w, QTreeWidget):
            item = w.currentItem()
            if item:
                nxt = w.itemBelow(item)
                if nxt:
                    w.setCurrentItem(nxt)
                    w.scrollToItem(nxt)
                    self._controller_trigger_preview(w)
            else:
                first = w.topLevelItem(0)
                if first:
                    w.setCurrentItem(first)
                    w.scrollToItem(first)
                    self._controller_trigger_preview(w)
        else:
            sb = w.verticalScrollBar() if hasattr(w, "verticalScrollBar") else None
            if sb:
                sb.setValue(sb.value() + sb.singleStep())

    def _controller_scroll_up(self) -> None:
        self._controller_nav_up(self.tabs.currentWidget())

    def _controller_scroll_down(self) -> None:
        self._controller_nav_down(self.tabs.currentWidget())

    def _controller_scroll_with_dir(self, direction: int) -> None:
        focused = QApplication.focusWidget()
        if not focused or not (focused is self or self.isAncestorOf(focused)):
            return
        w = self.tabs.currentWidget()
        if direction < 0:
            self._controller_nav_up(w)
        else:
            self._controller_nav_down(w)

    def clear(self) -> None:
        self._stop_movie()
        self.stop_preview()
        self._show_placeholder()
        self.description_text.clear()
        self.conflicts_tree.clear()
        self.files_tree.clear()
        self.folder_label.setText("")
        self._workshop_id = None
        self._workshop_id_str = None
        self._mod_path = None
        self.workshop_button.setEnabled(False)
        self.folder_button.setEnabled(False)
        self.tags_box.clear()
        self.dates_widget.setVisible(False)
        self.tabs.setEnabled(False)

    def stop_preview(self) -> None:
        if hasattr(self, "_preview"):
            self._preview.stop()
