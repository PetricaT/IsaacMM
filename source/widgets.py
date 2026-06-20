import html
import os
import re
import xml.etree.ElementTree as ET

from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QMovie, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from . import config, paths

def bbcode_to_html(text):
    text = html.escape(text)
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


class ModInfoPanel(QWidget):
    PRIORITY_ICON_NAMES = [
        "title",
        "thumbnail",
        "Thumbnail",
        "icon",
        "images",
        "modicon",
        "logo",
        "spider thumbnail",
    ]
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif"}

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._movie = None
        self._placeholder = QPixmap(
            os.path.join(paths.BASE_DIR, "assets", "no_image.png")
        )
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

        top_row = QHBoxLayout()
        top_row.addWidget(self.icon_label)
        top_row.addWidget(self.tags_box, 1)
        top_row.addWidget(self.workshop_button)

        self.state_label = QLabel("Select a mod")
        self.state_label.setAlignment(Qt.AlignCenter)

        self.description_text = QTextBrowser()
        self.description_text.setPlaceholderText(
            "Select a mod to view its description"
        )
        self.description_text.setOpenExternalLinks(False)
        self.description_text.anchorClicked.connect(self._open_link)

        self.folder_label = QLabel()
        self.folder_label.setStyleSheet("color: gray; font-size: 10px;")
        self.folder_label.setWordWrap(True)

        layout.addLayout(top_row)
        layout.addWidget(self.state_label)
        layout.addWidget(self.description_text)
        layout.addWidget(self.folder_label)

    def show_mod_info(self, mod_name, mod_folder=None, check_state=None):
        if mod_folder is None:
            for mod in config.loaded_mods:
                if mod[0] == mod_name:
                    mod_folder = mod[1]
                    break

        if mod_folder is None:
            self.clear()
            return

        mod_path = os.path.join(config.mods_path, mod_folder)

        icon_path = None
        try:
            files = os.listdir(mod_path)
            file_set = set(files)
            for name in self.PRIORITY_ICON_NAMES:
                for ext in self.IMAGE_EXTENSIONS:
                    candidate = f"{name}{ext}"
                    if candidate in file_set:
                        icon_path = os.path.join(mod_path, candidate)
                        break
                if icon_path:
                    break
            if icon_path is None:
                for f in files:
                    if os.path.splitext(f.lower())[1] in self.IMAGE_EXTENSIONS:
                        icon_path = os.path.join(mod_path, f)
                        break
        except OSError:
            pass

        self._stop_movie()
        if icon_path:
            if icon_path.lower().endswith(".gif"):
                movie = QMovie(icon_path)
                movie.setScaledSize(QSize(128, 128))
                if movie.isValid():
                    self._movie = movie
                    self.icon_label.setMovie(movie)
                    movie.start()
                else:
                    self._show_placeholder()
            else:
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    self.icon_label.setPixmap(
                        pixmap.scaled(
                            128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation
                        )
                    )
                else:
                    self._show_placeholder()
        else:
            self._show_placeholder()

        if check_state is not None:
            disabled = check_state == Qt.Unchecked
        else:
            disabled = os.path.exists(os.path.join(mod_path, "disable.it"))
        if disabled:
            self.state_label.setText("Disabled")
            self.state_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.state_label.setText("Enabled")
            self.state_label.setStyleSheet("color: green; font-weight: bold;")

        try:
            tree = ET.parse(os.path.join(mod_path, "metadata.xml"))
            root = tree.getroot()
            desc = root.find("description")
            if desc is not None and desc.text:
                self.description_text.setHtml(bbcode_to_html(desc.text.strip()))
            else:
                self.description_text.setHtml("(no description)")

            self.tags_box.clear()
            tags_el = root.find("tags")
            if tags_el is not None:
                tag_iter = tags_el.findall("tag")
            else:
                tag_iter = root.findall("tag")
            for tag in tag_iter:
                tid = tag.get("id", "")
                if not tid:
                    continue
                item = QListWidgetItem(tid)
                item.setBackground(QColor("#9BB7D4"))
                item.setForeground(QColor("#111111"))
                self.tags_box.addItem(item)

        except Exception:
            self.description_text.setHtml("(could not load description)")

        self.folder_label.setText(f"Folder: {mod_folder}")

        m = paths.WORKSHOP_ID_RE.search(mod_folder)
        self._workshop_id = int(m.group(1)) if m else None
        self.workshop_button.setEnabled(self._workshop_id is not None)

    def _show_placeholder(self):
        self._stop_movie()
        self.icon_label.setPixmap(
            self._placeholder.scaled(
                128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )

    def _stop_movie(self):
        if self._movie is not None:
            self._movie.stop()
            self._movie = None

    def _open_link(self, url):
        QDesktopServices.openUrl(QUrl(url))

    def _open_workshop(self):
        if self._workshop_id:
            url = QUrl(f"https://steamcommunity.com/sharedfiles/filedetails/?id={self._workshop_id}")
            QDesktopServices.openUrl(url)

    def clear(self):
        self._stop_movie()
        self._show_placeholder()
        self.state_label.setText("Select a mod")
        self.state_label.setStyleSheet("")
        self.description_text.clear()
        self.folder_label.clear()
        self._workshop_id = None
        self.workshop_button.setEnabled(False)
        self.tags_box.clear()
