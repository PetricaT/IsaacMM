import os
import xml.etree.ElementTree as ET

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QMovie, QPixmap
from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from . import config, paths


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

        self.state_label = QLabel("Select a mod")
        self.state_label.setAlignment(Qt.AlignCenter)

        self.description_text = QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setPlaceholderText(
            "Select a mod to view its description"
        )

        self.folder_label = QLabel()
        self.folder_label.setStyleSheet("color: gray; font-size: 10px;")
        self.folder_label.setWordWrap(True)

        layout.addWidget(self.icon_label)
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
                self.description_text.setPlainText(desc.text.strip())
            else:
                self.description_text.setPlainText("(no description)")
        except Exception:
            self.description_text.setPlainText("(could not load description)")

        self.folder_label.setText(f"Folder: {mod_folder}")

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

    def clear(self):
        self._stop_movie()
        self._show_placeholder()
        self.state_label.setText("Select a mod")
        self.state_label.setStyleSheet("")
        self.description_text.clear()
        self.folder_label.clear()
