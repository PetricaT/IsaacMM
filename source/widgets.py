import html
import os
import re
import xml.etree.ElementTree as ET
from typing import Optional

from PySide6.QtCore import QByteArray, QEvent, QPoint, Qt, QSize, QUrl
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

from . import config, paths


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

        except Exception:
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

    def _open_link(self, url: QUrl) -> None:
        QDesktopServices.openUrl(QUrl(url))

    def _open_workshop(self) -> None:
        if self._workshop_id:
            workshop_url = QUrl(
                f"https://steamcommunity.com/sharedfiles/filedetails/?id={self._workshop_id}"
            )
            QDesktopServices.openUrl(workshop_url)

    def _open_folder(self) -> None:
        if self._mod_path and os.path.isdir(self._mod_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._mod_path))

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

    def save_column_state(self) -> bytes:
        return bytes(self.conflicts_tree.header().saveState())

    def restore_column_state(self, state_data: bytes) -> None:
        if state_data:
            self.conflicts_tree.header().restoreState(QByteArray(state_data))

    def _open_conflict_file(self, item, tree_column: int) -> None:
        conflict_data = item.data(0, Qt.UserRole)
        if conflict_data is None:
            return
        conflict_folder, relative_file_path = conflict_data
        full_path = os.path.join(config.mods_path, conflict_folder, relative_file_path)
        if not os.path.exists(full_path):
            return
        ctrl_pressed = QApplication.keyboardModifiers() & Qt.ControlModifier
        if ctrl_pressed:
            QDesktopServices.openUrl(QUrl.fromLocalFile(full_path))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(full_path)))

    def eventFilter(self, obj, event) -> bool:
        if obj is self.conflicts_tree.viewport():
            if event.type() == QEvent.MouseMove:
                if config.preview_images:
                    item = self.conflicts_tree.itemAt(event.pos())
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
