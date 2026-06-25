import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from typing import Optional

from PySide6.QtCore import QByteArray, QEvent, QPoint, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImageReader,
    QMovie,
    QPalette,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import config, logger, paths
from .components.file_utils import open_path, open_url
from .components.modlist import normalize_mod_name
from .components.preview import PreviewWidget
from .components.text_utils import bbcode_to_html
from .components.workshop import (
    _check_workshop_rate_limit,
    _dequeue_workshop,
    _download_workshop_icon,
    _enqueue_workshop,
    _failed_workshop_ids,
    _pending_workshop_ids,
    _permanent_failures,
    _prune_failures,
    _requeue_workshop,
)
from .worker import WorkerThread


class ConflictTreeWidget(QTreeWidget):
    pass


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
        self._icon_thread = None
        self._icon_queue_timer = QTimer(self)
        self._icon_queue_timer.setSingleShot(True)
        self._icon_queue_timer.timeout.connect(self._process_icon_queue)
        self.destroyed.connect(
            self._cleanup_threads, Qt.ConnectionType.DirectConnection
        )
        self._placeholder = QPixmap(
            os.path.join(paths.BASE_DIR, "assets", "no_image.png")
        )
        self._folder_icon = QIcon(
            os.path.join(paths.BASE_DIR, "assets", "folder-yellow.png")
        )
        modinfo_label = QLabel("<b>Mod Info</b>")
        modinfo_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(modinfo_label)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(128, 128)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("border: 1px solid gray;")

        self.tags_box = QListWidget()
        self.tags_box.setMaximumHeight(128)
        self.tags_box.setSelectionMode(QAbstractItemView.NoSelection)
        self.tags_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tags_box.setFlow(QListWidget.LeftToRight)
        self.tags_box.setWrapping(True)
        self.tags_box.setSpacing(4)
        self.tags_box.setStyleSheet(
            "QListWidget { border: none; background: transparent; }"
        )

        self.workshop_button = QPushButton("Steam Workshop")
        self.workshop_button.clicked.connect(self._open_workshop)
        self.workshop_button.setEnabled(False)

        self.folder_button = QPushButton("Open Folder")
        self.folder_button.clicked.connect(self._open_folder)
        self.folder_button.setEnabled(False)

        button_column = QVBoxLayout()
        button_column.addWidget(self.workshop_button)
        button_column.addWidget(self.folder_button)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.icon_label)
        top_layout.addWidget(self.tags_box, 1)
        top_layout.addLayout(button_column)

        self.tabs = QTabWidget()

        self.description_text = QTextBrowser()
        self.description_text.setPlaceholderText("Select a mod to view its description")
        self.description_text.setOpenExternalLinks(False)
        self.description_text.anchorClicked.connect(self._open_link)
        self.tabs.addTab(self.description_text, "Description")

        self.conflicts_tree = ConflictTreeWidget()
        self.conflicts_tree.setHeaderLabels(["Mod", "File"])
        self.conflicts_tree.setRootIsDecorated(True)
        self.conflicts_tree.setAlternatingRowColors(True)
        current_palette = self.conflicts_tree.palette()
        base_color = current_palette.color(QPalette.Base)
        alternate_color = (
            base_color.lighter(120)
            if base_color.lightness() < 128
            else base_color.darker(108)
        )
        current_palette.setColor(QPalette.AlternateBase, alternate_color)
        self.conflicts_tree.setPalette(current_palette)
        self.conflicts_tree.header().setStretchLastSection(False)
        self.conflicts_tree.header().resizeSection(1, 350)
        self.conflicts_tree.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.conflicts_tree.itemDoubleClicked.connect(self._open_conflict_file)
        self.conflicts_tree.viewport().installEventFilter(self)
        self.conflicts_tree.viewport().setMouseTracking(True)
        self._preview = PreviewWidget(self)
        self.conflicts_tree.verticalScrollBar().valueChanged.connect(
            self._on_preview_tree_scroll
        )
        self.tabs.addTab(self.conflicts_tree, "Conflicts")

        self.files_tree = QTreeWidget()
        self.files_tree.setHeaderLabels(["Name"])
        self.files_tree.setRootIsDecorated(True)
        self.files_tree.setAlternatingRowColors(True)
        current_palette = self.files_tree.palette()
        base_color = current_palette.color(QPalette.Base)
        alternate_color = (
            base_color.lighter(120)
            if base_color.lightness() < 128
            else base_color.darker(108)
        )
        current_palette.setColor(QPalette.AlternateBase, alternate_color)
        self.files_tree.setPalette(current_palette)
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
            "QPushButton { color: gray; font-size: 10px; text-align: left; border: none; }"
        )
        self.folder_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_label.clicked.connect(self._open_folder)

        layout.addLayout(top_layout)
        layout.addWidget(self.tabs)
        layout.addWidget(self.folder_label)

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
                            Qt.TransformationMode.SmoothTransformation,
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
                    "#65A665" if conflict_data["overwrites"] else "#9E4D4D"
                )
                mod_tree_item = QTreeWidgetItem([conflict_mod_name, ""])
                mod_tree_item.setForeground(0, QColor(overwrite_color))
                self._populate_file_tree(
                    mod_tree_item, conflict_data["files"], conflict_folder
                )
                self.conflicts_tree.addTopLevelItem(mod_tree_item)
            self.conflicts_tree.expandAll()

        self.files_tree.clear()
        root_item = QTreeWidgetItem([mod_folder])
        root_item.setIcon(0, self._folder_icon)
        root_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        self.files_tree.addTopLevelItem(root_item)
        self._populate_mod_files(root_item, full_mod_path, "", mod_folder)
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
                tag_item.setBackground(QColor("#9BB7D4"))
                tag_item.setForeground(QColor("#111111"))
                self.tags_box.addItem(tag_item)

        except Exception as exc:
            logger.log("error", f"Failed to load mod description: {exc}")
            self.description_text.setHtml("(could not load description)")

        self.folder_label.setText(f"Folder: {mod_folder}")

        workshop_match = paths.WORKSHOP_ID_RE.search(mod_folder)
        self._workshop_id = int(workshop_match.group(1)) if workshop_match else None
        self.workshop_button.setEnabled(self._workshop_id is not None)

    def _show_placeholder(self) -> None:
        self._stop_movie()
        self.icon_label.setPixmap(
            self._placeholder.scaled(
                128,
                128,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
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
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return True

        _prune_failures()
        if ws_id in _permanent_failures:
            return False
        last_fail = _failed_workshop_ids.get(ws_id)
        if last_fail is not None:
            return False

        if _enqueue_workshop(ws_id, normalized_name):
            if not self._icon_queue_timer.isActive():
                self._process_icon_queue()
        return False

    def _process_icon_queue(self) -> None:
        if self._icon_thread is not None:
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

        def on_done(actual_path: str):
            _pending_workshop_ids.discard(ws_id)
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
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                img_loaded = True
            if not img_loaded:
                self._show_placeholder()
            self._icon_thread = None
            self._icon_queue_timer.start(2000)

        def on_error(msg: str):
            _pending_workshop_ids.discard(ws_id)
            _failed_workshop_ids[ws_id] = time.time()
            self.log_message.emit(msg, "warning")
            self._show_placeholder()
            self._icon_thread = None
            self._icon_queue_timer.start(2000)

        thread = WorkerThread(_download_workshop_icon, ws_id, cached_path)
        _pending_workshop_ids.add(ws_id)
        thread.finished.connect(on_done)
        thread.error.connect(on_error)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        self._icon_thread = thread

    def _cleanup_threads(self) -> None:
        if self._icon_thread is not None:
            self._icon_thread.quit()
            self._icon_thread.wait(5000)
            self._icon_thread.deleteLater()
            self._icon_thread = None

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
                    parent.addChild(file_item)

        add_branches(path_tree, parent_item)

    def _populate_mod_files(
        self, parent_item, current_path: str, relative_prefix: str, mod_folder: str
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
                self._populate_mod_files(dir_item, full_entry, rel_path, mod_folder)
            else:
                file_item = QTreeWidgetItem([entry])
                file_item.setData(0, Qt.ItemDataRole.UserRole, (mod_folder, rel_path))
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
        self._mod_path = os.path.join(config.mods_path, folder)
        self.folder_button.setEnabled(True)
        self.folder_label.setText(f"Separator: {separator_name}")
        self.workshop_button.setEnabled(False)
        self.tabs.setEnabled(False)

    def clear(self) -> None:
        self._stop_movie()
        self._preview.stop()
        self._show_placeholder()
        self.description_text.clear()
        self.conflicts_tree.clear()
        self.folder_label.setText("")
        self._workshop_id = None
        self._mod_path = None
        self.workshop_button.setEnabled(False)
        self.folder_button.setEnabled(False)
        self.tags_box.clear()
        self.tabs.setEnabled(False)
