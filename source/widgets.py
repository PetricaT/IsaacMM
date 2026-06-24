import html
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import deque
from typing import Optional

import certifi

from . import config, logger, paths
from .worker import WorkerThread

from PySide6.QtCore import QByteArray, QEvent, QPoint, Qt, QSize, QUrl, Signal
from PySide6.QtGui import (
    QColor, QDesktopServices, QIcon, QMovie, QPalette, QPixmap,
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

_ssl_context = ssl.create_default_context(cafile=certifi.where())

_WORKSHOP_LIMITER: deque = deque()
WORKSHOP_RATE_LIMIT: int = 5
WORKSHOP_RATE_WINDOW: int = 1200
WORKSHOP_RETRY_COOLDOWN: int = 1200
_failed_workshop_ids: dict[str, float] = {}
_permanent_failures: set[str] = set()
_pending_workshop_ids: set[str] = set()


def _init_workshop_limiter() -> None:
    now = time.time()
    _WORKSHOP_LIMITER.clear()
    for ts in config.workshop_timestamps:
        if ts >= now - WORKSHOP_RATE_WINDOW:
            _WORKSHOP_LIMITER.append(ts)
    _permanent_failures.clear()
    _permanent_failures.update(config.dead_workshop_ids)


def _sync_workshop_limiter() -> None:
    config.workshop_timestamps = list(_WORKSHOP_LIMITER)


def _workshop_limiter_state() -> tuple[int, Optional[float]]:
    now = time.time()
    while _WORKSHOP_LIMITER and _WORKSHOP_LIMITER[0] < now - WORKSHOP_RATE_WINDOW:
        _WORKSHOP_LIMITER.popleft()
    count = len(_WORKSHOP_LIMITER)
    next_available = None
    if count >= WORKSHOP_RATE_LIMIT:
        next_available = _WORKSHOP_LIMITER[0] + WORKSHOP_RATE_WINDOW
    return count, next_available


def _prune_failures() -> None:
    cutoff = time.time() - WORKSHOP_RETRY_COOLDOWN
    for ws_id in list(_failed_workshop_ids):
        if _failed_workshop_ids[ws_id] < cutoff:
            del _failed_workshop_ids[ws_id]


def _check_workshop_rate_limit() -> bool:
    now = time.time()
    while _WORKSHOP_LIMITER and _WORKSHOP_LIMITER[0] < now - WORKSHOP_RATE_WINDOW:
        _WORKSHOP_LIMITER.popleft()
    if len(_WORKSHOP_LIMITER) >= WORKSHOP_RATE_LIMIT:
        return False
    _WORKSHOP_LIMITER.append(now)
    return True


def _fetch_workshop_preview_url(ws_id: str) -> str:
    data = {"itemcount": 1, "publishedfileids[0]": ws_id}
    payload = urllib.parse.urlencode(data).encode()
    try:
        req = urllib.request.Request(
            "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
            data=payload,
            headers={"User-Agent": "IsaacMM/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context) as resp:
            result = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"workshop {ws_id}: API request failed: {exc}")

    details = result.get("response", {}).get("publishedfiledetails", [])
    if not details:
        raise RuntimeError(f"workshop {ws_id}: no publishedfiledetails in API response")

    match details[0].get("result", 0):
        case 1:
            return details[0]["preview_url"]
        case 9:
            raise FileNotFoundError(f"workshop {ws_id}: file not found (result=9)")
        case other:
            raise RuntimeError(f"workshop {ws_id}: API returned result={other} (expected 1)")


def _download_workshop_icon(ws_id: str, cached_path: str) -> str:
    if not _check_workshop_rate_limit():
        raise RuntimeError("rate_limited")

    try:
        preview_url = _fetch_workshop_preview_url(ws_id)

        req_img = urllib.request.Request(
            preview_url, headers={"User-Agent": "IsaacMM/1.0"}
        )
        with urllib.request.urlopen(req_img, timeout=10, context=_ssl_context) as resp_img:
            img_data = resp_img.read()

        os.makedirs(os.path.dirname(cached_path), exist_ok=True)
        with open(cached_path, "wb") as f:
            f.write(img_data)

        return ws_id
    except FileNotFoundError:
        _permanent_failures.add(ws_id)
        config.dead_workshop_ids = sorted(_permanent_failures)
        config.save()
        raise RuntimeError(f"workshop {ws_id}: file not found (permanent)")
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            now = time.time()
            for _ in range(WORKSHOP_RATE_LIMIT):
                _WORKSHOP_LIMITER.append(now)
            raise RuntimeError("rate_limited")
        raise RuntimeError(f"workshop {ws_id}: image download failed: {exc}")
    except Exception as exc:
        raise RuntimeError(f"workshop {ws_id}: {exc}")


def open_path(path: str) -> bool:
    if sys.platform.startswith("linux"):
        env = os.environ.copy()
        env.pop("LD_LIBRARY_PATH", None)
        env.pop("APPDIR", None)
        env.pop("APPIMAGE", None)
        proc = subprocess.Popen(["xdg-open", path], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.communicate(timeout=5)
        if proc.returncode != 0:
            return False
        return True
    elif sys.platform == "darwin":
        proc = subprocess.Popen(["open", path],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.communicate(timeout=5)
        return proc.returncode == 0
    else:
        return QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def open_url(url: str) -> bool:
    if sys.platform.startswith("linux"):
        env = os.environ.copy()
        env.pop("LD_LIBRARY_PATH", None)
        env.pop("APPDIR", None)
        env.pop("APPIMAGE", None)
        proc = subprocess.Popen(["xdg-open", url], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.communicate(timeout=5)
        if proc.returncode != 0:
            return False
        return True
    elif sys.platform == "darwin":
        proc = subprocess.Popen(["open", url],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.communicate(timeout=5)
        return proc.returncode == 0
    else:
        return QDesktopServices.openUrl(QUrl(url))


def bbcode_to_html(input_text: str) -> str:
    text = html.escape(input_text)
    text = re.sub(r'\[b\](.*?)\[/b\]', r'<b>\1</b>', text, flags=re.DOTALL)
    text = re.sub(r'\[i\](.*?)\[/i\]', r'<i>\1</i>', text, flags=re.DOTALL)
    text = re.sub(r'\[u\](.*?)\[/u\]', r'<u>\1</u>', text, flags=re.DOTALL)
    text = re.sub(r'\[h1\](.*?)\[/h1\]', r'<h1>\1</h1>', text, flags=re.DOTALL)
    text = re.sub(r'\[h2\](.*?)\[/h2\]', r'<h2>\1</h2>', text, flags=re.DOTALL)
    text = re.sub(r'\[h3\](.*?)\[/h3\]', r'<h3>\1</h3>', text, flags=re.DOTALL)
    text = re.sub(r'\[url=([^\]]+)\](.*?)\[/url\]', r'<a href="\1">\2</a>', text, flags=re.DOTALL)
    text = re.sub(r'\[url\](.*?)\[/url\]', r'<a href="\1">\1</a>', text, flags=re.DOTALL)
    text = re.sub(r'\[img\](.*?)\[/img\]', r'<img src="\1">', text, flags=re.DOTALL)
    text = re.sub(r'\[list\]', '<ul>', text)
    text = re.sub(r'\[/list\]', '</ul>', text)
    text = re.sub(r'\[\*\]', '<li>', text)
    text = text.replace('\n', '<br>')
    return f"<html><body style='font-size: 12pt;'>{text}</body></html>"


class ConflictTreeWidget(QTreeWidget):
    pass


class ModInfoPanel(QWidget):
    log_message = Signal(str, str)  # message, level

    PRIORITY_ICON_NAMES: list[str] = [
        "title", "thumbnail", "Thumbnail", "icon", "images", "modicon", "logo",
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
        self._icon_threads: set = set()
        self.destroyed.connect(self._cleanup_threads, Qt.DirectConnection)
        self._placeholder = QPixmap(
            os.path.join(paths.BASE_DIR, "assets", "no_image.png")
        )
        self._folder_icon = QIcon(
            os.path.join(paths.BASE_DIR, "assets", "folder-yellow.png")
        )
        modinfo_label = QLabel("<b>Mod Info</b>")
        modinfo_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(modinfo_label)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(128, 128)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("border: 1px solid gray;")

        self.tags_box = QListWidget()
        self.tags_box.setMaximumHeight(128)
        self.tags_box.setSelectionMode(QAbstractItemView.NoSelection)
        self.tags_box.setFocusPolicy(Qt.NoFocus)
        self.tags_box.setFlow(QListWidget.LeftToRight)
        self.tags_box.setWrapping(True)
        self.tags_box.setSpacing(4)
        self.tags_box.setStyleSheet("QListWidget { border: none; background: transparent; }")

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
        self.description_text.setPlaceholderText(
            "Select a mod to view its description"
        )
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
            base_color.lighter(120) if base_color.lightness() < 128
            else base_color.darker(108)
        )
        current_palette.setColor(QPalette.AlternateBase, alternate_color)
        self.conflicts_tree.setPalette(current_palette)
        self.conflicts_tree.header().setStretchLastSection(False)
        self.conflicts_tree.header().resizeSection(1, 350)
        self.conflicts_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.conflicts_tree.itemDoubleClicked.connect(self._open_conflict_file)
        self.conflicts_tree.viewport().installEventFilter(self)
        self.conflicts_tree.viewport().setMouseTracking(True)
        self._preview_label = QLabel(self, Qt.ToolTip | Qt.FramelessWindowHint)
        self._preview_label.setStyleSheet("border: 1px solid #888; background: #fff; padding: 2px;")
        self._preview_label.hide()
        self._preview_path: str | None = None
        self.tabs.addTab(self.conflicts_tree, "Conflicts")

        self.files_tree = QTreeWidget()
        self.files_tree.setHeaderLabels(["Name"])
        self.files_tree.setRootIsDecorated(True)
        self.files_tree.setAlternatingRowColors(True)
        current_palette = self.files_tree.palette()
        base_color = current_palette.color(QPalette.Base)
        alternate_color = (
            base_color.lighter(120) if base_color.lightness() < 128
            else base_color.darker(108)
        )
        current_palette.setColor(QPalette.AlternateBase, alternate_color)
        self.files_tree.setPalette(current_palette)
        self.files_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.files_tree.itemDoubleClicked.connect(self._open_file)
        self.files_tree.viewport().installEventFilter(self)
        self.files_tree.viewport().setMouseTracking(True)
        self.tabs.addTab(self.files_tree, "Files")

        self.folder_label = QPushButton()
        self.folder_label.setFlat(True)
        self.folder_label.setStyleSheet(
            "QPushButton { color: gray; font-size: 10px; text-align: left; border: none; }"
        )
        self.folder_label.setCursor(Qt.PointingHandCursor)
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
        if mod_folder is None:
            for loaded_mod in config.loaded_mods:
                if loaded_mod[0] == mod_name:
                    mod_folder = loaded_mod[1]
                    break

        if mod_folder is None:
            self.clear()
            return

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
                            128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation
                        )
                    )
                else:
                    self._show_placeholder()
        else:
            if not config.download_icons or not self._try_download_icon(mod_folder):
                self._show_placeholder()

        self.conflicts_tree.clear()
        if conflicts:
            for conflict_mod_name, conflict_data in sorted(conflicts.items()):
                conflict_folder = conflict_data["folder"]
                overwrite_color = "#65A665" if conflict_data["overwrites"] else "#9E4D4D"
                mod_tree_item = QTreeWidgetItem([conflict_mod_name, ""])
                mod_tree_item.setForeground(0, QColor(overwrite_color))
                self._populate_file_tree(mod_tree_item, conflict_data["files"], conflict_folder)
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
                self.description_text.setHtml(bbcode_to_html(description_element.text.strip()))
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
                128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )

    def _stop_movie(self) -> None:
        self._movie.stop()

    def _try_download_icon(self, mod_folder: str) -> bool:
        ws_match = paths.WORKSHOP_ID_RE.search(mod_folder)
        if not ws_match:
            return False
        ws_id = ws_match.group(1)
        cache_dir = os.path.join(paths.cache_dir, "icons")
        cached_path = os.path.join(cache_dir, f"{ws_id}.png")

        if os.path.isfile(cached_path):
            loaded = QPixmap(cached_path)
            if not loaded.isNull():
                self.icon_label.setPixmap(
                    loaded.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                return True

        _prune_failures()
        if ws_id in _permanent_failures:
            return False
        if ws_id in _pending_workshop_ids:
            return False
        last_fail = _failed_workshop_ids.get(ws_id)
        if last_fail is not None:
            return False

        if self._icon_thread is not None:
            try:
                self._icon_thread.finished.disconnect()
                self._icon_thread.error.disconnect()
            except RuntimeError:
                pass
            self._icon_thread.quit()

        def on_done(_result):
            _pending_workshop_ids.discard(ws_id)
            loaded = QPixmap(cached_path)
            if not loaded.isNull():
                self.icon_label.setPixmap(
                    loaded.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )

        def on_error(msg: str):
            _pending_workshop_ids.discard(ws_id)
            _failed_workshop_ids[ws_id] = time.time()
            self.log_message.emit(msg, "warning")
            self._show_placeholder()

        thread = WorkerThread(_download_workshop_icon, ws_id, cached_path)
        _pending_workshop_ids.add(ws_id)
        thread.finished.connect(on_done)
        thread.error.connect(on_error)
        thread.finished.connect(lambda: self._on_thread_done(thread))
        thread.finished.connect(thread.deleteLater)
        thread.start()
        self._icon_threads.add(thread)
        self._icon_thread = thread
        return False

    def _on_thread_done(self, thread) -> None:
        self._icon_threads.discard(thread)
        if self._icon_thread is thread:
            self._icon_thread = None

    def _cleanup_threads(self) -> None:
        for thread in self._icon_threads:
            thread.quit()
            thread.wait(5000)
            thread.deleteLater()
        self._icon_threads.clear()
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

    def _populate_file_tree(self, parent_item, file_paths: list, conflict_folder: str) -> None:
        path_tree = {}
        for relative_path in file_paths:
            normalized = relative_path.replace("\\", "/")
            parts = normalized.split("/")
            current_level = path_tree
            for segment in parts:
                current_level = current_level.setdefault(segment, {})

        def add_branches(subtree, parent, accumulated_path=""):
            for name in sorted(subtree.keys(), key=lambda k: (not subtree[k], k.lower())):
                child_subtree = subtree[name]
                segment_path = f"{accumulated_path}/{name}" if accumulated_path else name
                if child_subtree:
                    folder_item = QTreeWidgetItem([name, ""])
                    folder_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                    folder_item.setIcon(0, self._folder_icon)
                    parent.addChild(folder_item)
                    add_branches(child_subtree, folder_item, segment_path)
                else:
                    file_item = QTreeWidgetItem(["", name])
                    file_item.setData(0, Qt.UserRole, (conflict_folder, segment_path))
                    parent.addChild(file_item)

        add_branches(path_tree, parent_item)

    def _populate_mod_files(self, parent_item, current_path: str, relative_prefix: str, mod_folder: str) -> None:
        try:
            entries = sorted(os.listdir(current_path))
        except OSError:
            return
        for entry in entries:
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
                file_item.setData(0, Qt.UserRole, (mod_folder, rel_path))
                parent_item.addChild(file_item)

    def _open_file(self, item, column) -> None:
        data = item.data(0, Qt.UserRole)
        if not data or not isinstance(data, tuple):
            return
        mod_folder, relative_path = data
        full_path = os.path.join(config.mods_path, mod_folder, relative_path)
        if not os.path.exists(full_path):
            logger.log("warning", f"Path does not exist: {full_path}")
            return
        ext = os.path.splitext(full_path.lower())[1]
        if sys.platform == "darwin" and ext in {".png", ".jpg", ".jpeg", ".gif"}:
            subprocess.Popen(["qlmanage", "-p", full_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        ctrl_pressed = QApplication.keyboardModifiers() & Qt.ControlModifier
        if ctrl_pressed:
            if not open_path(os.path.dirname(full_path)):
                logger.log("error", f"Failed to open folder: {os.path.dirname(full_path)}")
        else:
            if not open_path(full_path):
                logger.log("error", f"Failed to open file: {full_path}")

    def save_column_state(self) -> bytes:
        return bytes(self.conflicts_tree.header().saveState())

    def restore_column_state(self, state_data: QByteArray) -> None:
        if state_data:
            self.conflicts_tree.header().restoreState(state_data)

    def _open_conflict_file(self, item, tree_column: int) -> None:
        conflict_data = item.data(0, Qt.UserRole)
        if conflict_data is None:
            return
        conflict_folder, relative_file_path = conflict_data
        full_path = os.path.join(config.mods_path, conflict_folder, relative_file_path)
        if not os.path.exists(full_path):
            logger.log("warning", f"Path does not exist: {full_path}")
            return
        ctrl_pressed = QApplication.keyboardModifiers() & Qt.ControlModifier
        if ctrl_pressed:
            if not open_path(os.path.dirname(full_path)):
                logger.log("error", f"Failed to open folder: {os.path.dirname(full_path)}")
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
                        self._show_preview(item, event.globalPos())
                        return False
                self._preview_label.hide()
                return False
            if event.type() == QEvent.Leave:
                self._preview_label.hide()
                return False
        return super().eventFilter(obj, event)

    def _show_preview(self, item, global_pos: QPoint) -> None:
        data = item.data(0, Qt.UserRole)
        if not data:
            self._preview_label.hide()
            return
        conflict_folder, relative_path = data
        if not relative_path.lower().endswith(".png"):
            self._preview_label.hide()
            return
        full_path = os.path.join(config.mods_path, conflict_folder, relative_path)
        if not os.path.exists(full_path):
            self._preview_label.hide()
            return
        if self._preview_path != full_path:
            pixmap = QPixmap(full_path)
            if pixmap.isNull():
                self._preview_label.hide()
                return
            scaled = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.FastTransformation)
            self._preview_label.setPixmap(scaled)
            self._preview_label.adjustSize()
            self._preview_path = full_path
        self._preview_label.move(global_pos + QPoint(15, 15))
        self._preview_label.show()

    def clear(self) -> None:
        self._stop_movie()
        self._show_placeholder()
        self.description_text.clear()
        self.conflicts_tree.clear()
        self._preview_label.hide()
        self._preview_path = None
        self.folder_label.setText("")
        self._workshop_id = None
        self._mod_path = None
        self.workshop_button.setEnabled(False)
        self.folder_button.setEnabled(False)
        self.tags_box.clear()
