import os
import re
import sys
import xml.etree.ElementTree as ET

import toml
from PySide6.QtCore import QModelIndex, QSize, Qt
from PySide6.QtGui import (
    QIcon,
    QMovie,
    QPalette,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

sorted_pattern = re.compile(r"[0-9]{3}\s{1}.*")
exclamation_marks = re.compile(r"\s!{1,12}")

mods_path = ""
cfg_file = ""

version = "v0.2.4"

# Try to resolve to .local/share/IsaacMM (if Linux/MacOS), .AppData/IsaacMM (if Windows
# and .AppData/IsaacMM doesn't exist
if sys.platform == "win32":
    appdata = os.path.expanduser("~") + "/AppData/IsaacMM"
elif sys.platform == "darwin":
    appdata = os.path.expanduser("~") + "/Library/Application Support/IsaacMM"
else:
    appdata = os.path.expanduser("~") + "/.local/share/IsaacMM"

try:
    # Global Settings & Vars
    # Mods path:    str     - Path to mods folder
    # Remove marks: bool    - Remove exclamation marks from mod names
    #
    cfg_file = toml.load(f"{appdata}/config.toml")
    mods_path = cfg_file["paths"]["mods"]
    if mods_path == "":
        print("Mods path malformed, check if path is correct")
        mods_path = ""
    remove_marks = cfg_file["settings"]["remove_marks"]
    if remove_marks == "true":
        remove_marks = True
    else:
        remove_marks = False
except FileNotFoundError:
    print("Config file not found")
    os.makedirs(appdata, exist_ok=True)
    with open(f"{appdata}/config.toml", "w") as f:
        f.write("[paths]\n")
        isaac_folder = re.compile(r".*Binding of Isaac.*")
        # Linux: /home/USERNAME/.local/share/Steam/steamapps/common/The Binding of Isaac Rebirth/mods/
        # MacOS: /Users/USERNAME/Library/Application Support/Binding of Isaac Afterbirth+ Mods/
        if sys.platform == "darwin":
            # Official MacOS support was dropped, so we know the path is permanently this, we can just guess it.
            f.write(
                f"mods='{os.path.expanduser('~/Library/Application Support/Binding of Isaac Afterbirth+ Mods')}'\n"
            )
        elif sys.platform == "linux":
            # Linux is a bit more complicated, as the path can be different depending on the user's setup.
            # We can check the Steam library folders to find the correct path.
            steam_path = os.path.expanduser("~/.steam/steam/steamapps/common/")
            for folder in os.listdir(steam_path):
                if isaac_folder.match(folder):
                    f.write(f"mods='{steam_path}{folder}/mods'\n")
        else:
            # Sadly, Linux support is weird, and Windows is a shot in the dark.
            f.write("mods=''\n")
        f.write("[settings]\n")
        f.write("remove_marks=false\n")
        f.close


class FlatDropModel(QStandardItemModel):
    def dropMimeData(self, data, action, row, column, parent):
        if parent.isValid():
            row = parent.row() + 1
            parent = QModelIndex()
        return super().dropMimeData(data, action, row, column, parent)


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
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "no_image.png")
        )
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(128, 128)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("border: 1px solid gray;")

        self.state_label = QLabel("Select a mod")
        self.state_label.setAlignment(Qt.AlignCenter)

        self.description_text = QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setPlaceholderText("Select a mod to view its description")

        self.folder_label = QLabel()
        self.folder_label.setStyleSheet("color: gray; font-size: 10px;")
        self.folder_label.setWordWrap(True)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.state_label)
        layout.addWidget(self.description_text)
        layout.addWidget(self.folder_label)

    def show_mod_info(self, mod_name, mod_folder=None, check_state=None):
        if mod_folder is None:
            for mod in loaded_mods:
                if mod[0] == mod_name:
                    mod_folder = mod[1]
                    break

        if mod_folder is None:
            self.clear()
            return

        mod_path = os.path.join(mods_path, mod_folder)

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


class DragApp(QWidget):
    global loaded_mods
    loaded_mods = []

    def __init__(self, parent=None):
        super(DragApp, self).__init__(parent)

        self.setWindowTitle(f"Tboi Mod Manager [{version}]")
        self.resize(800, 400)
        self.previous_mods_path = ""
        self.pending_toggles = {}
        self._populating = False

        self.initUi()

    def initUi(self):
        self.baseLayout = QGridLayout(self)
        self.modListWidget()
        self.modInfoPanel = ModInfoPanel()

        # Left: list view; Right: mod info panel
        self.baseLayout.addWidget(self.listView, 0, 0, 5, 1)
        self.baseLayout.addWidget(self.modInfoPanel, 0, 1, 7, 1)

        btn_row_1 = QHBoxLayout()
        btn_row_1.addWidget(self.applyOrder)
        btn_row_1.addWidget(self.autoSort)
        self.baseLayout.addLayout(btn_row_1, 5, 0)

        btn_row_2 = QHBoxLayout()
        btn_row_2.addWidget(self.pickModsPath)
        btn_row_2.addWidget(self.refreshOrder)
        self.baseLayout.addLayout(btn_row_2, 6, 0)

        self.baseLayout.addWidget(self.currentPath, 7, 0)

        self.baseLayout.setColumnStretch(0, 1)
        self.baseLayout.setColumnStretch(1, 1)

        self.applyOrder.clicked.connect(self.applyModOrder)
        self.refreshOrder.clicked.connect(self.getModList)
        self.pickModsPath.clicked.connect(self.setModsPath)
        self.listView.selectionModel().selectionChanged.connect(
            self.on_mod_selected
        )

    def modListWidget(self):
        self.accent_color = self.get_accent_color_hex()
        self.listView = QListView(self)
        self.listView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.listView.setDragEnabled(True)
        self.listView.setAcceptDrops(True)
        self.listView.setDropIndicatorShown(True)
        self.listView.setDragDropMode(QAbstractItemView.InternalMove)
        self.listView.setDefaultDropAction(Qt.MoveAction)

        self.model = FlatDropModel()
        self.listView.setModel(self.model)
        self.model.itemChanged.connect(self.on_item_changed)

        self.getModList()
        self.applyOrder = QPushButton("Apply Sort Order")
        self.autoSort = QPushButton("Auto Sort")
        self.refreshOrder = QPushButton("Refresh")
        self.pickModsPath = QPushButton("Select Mods Folder")
        self.currentPath = QLineEdit(f"{mods_path}")
        self.currentPath.setReadOnly(True)

        self.applyOrder.setStyleSheet(f"background-color : {self.accent_color}")

        if mods_path == "" or loaded_mods == []:
            self.pickModsPath.setStyleSheet("background-color : red")
        else:
            self.pickModsPath.setStyleSheet("background-color: auto")

    def setModsPath(self):
        print("Presenting file dialog")
        cfg_file = toml.load(f"{appdata}/config.toml")
        mods_path = QFileDialog.getExistingDirectory(self)
        cfg_file["paths"]["mods"] = mods_path
        with open(f"{appdata}/config.toml", "w") as f:
            toml.dump(cfg_file, f)
        self.currentPath.setText(f"{mods_path}")

    def applyModOrder(self):
        i = 1
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            mod_name = item.text()
            mod_folder = item.data(Qt.UserRole)
            if sorted_pattern.match(mod_name):
                new_name = f"{i:03} {mod_name[4:]}"
            else:
                new_name = f"{i:03} {mod_name}"
            mod_xml = ET.parse(f"{mods_path}/{mod_folder}/metadata.xml")
            root = mod_xml.getroot()
            root.find("name").text = new_name
            mod_xml.write(
                f"{mods_path}/{mod_folder}/metadata.xml",
                encoding="utf-8",
                xml_declaration=True,
            )
            i += 1
        for folder, state in self.pending_toggles.items():
            disable_path = os.path.join(mods_path, folder, "disable.it")
            if state == Qt.Unchecked:
                open(disable_path, "a").close()
            else:
                try:
                    os.remove(disable_path)
                except FileNotFoundError:
                    pass
        self.pending_toggles.clear()
        self.getModList()

    def getModList(self):
        if mods_path == "":
            return

        self._populating = True
        self.model.clear()
        self.pending_toggles.clear()
        loaded_mods.clear()

        mod_list = os.listdir(mods_path)
        try:
            ds_index = mod_list.index(".DS_Store")
            mod_list.pop(ds_index)
        except ValueError:
            pass

        for mod_folder in mod_list:
            try:
                mod_xml = ET.parse(f"{mods_path}/{mod_folder}/metadata.xml")
                root = mod_xml.getroot()
                name = root.find("name").text
                loaded_mods.append([name, mod_folder])
            except FileNotFoundError:
                continue

        loaded_mods.sort(key=lambda x: x[0])

        for name, mod_folder in loaded_mods:
            item = QStandardItem(name)
            item.setCheckable(True)
            disable_path = os.path.join(mods_path, mod_folder, "disable.it")
            item.setCheckState(
                Qt.Unchecked if os.path.exists(disable_path) else Qt.Checked
            )
            item.setData(mod_folder, Qt.UserRole)
            self.model.appendRow(item)

        self.previous_mods_path = mods_path
        self._populating = False

    def on_mod_selected(self, selected, deselected):
        indexes = self.listView.selectedIndexes()
        if indexes:
            item = self.model.itemFromIndex(indexes[0])
            self.modInfoPanel.show_mod_info(
                item.text(), item.data(Qt.UserRole), item.checkState()
            )
        else:
            self.modInfoPanel.clear()

    def on_item_changed(self, item):
        if self._populating:
            return
        folder = item.data(Qt.UserRole)
        if folder:
            self.pending_toggles[folder] = item.checkState()

    def disable_unimplemented(self):
        unimplemented_buttons = [self.autoSort]
        for button in unimplemented_buttons:
            button.setEnabled(False)
            button.setToolTip("Not implemented yet")

    def get_accent_color_hex(self):
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        palette = app.palette()
        accent_color = palette.color(QPalette.ColorRole.Highlight)
        return accent_color.name()


def set_icon(app):
    if sys.platform == "win32":
        app.setWindowIcon(QIcon("assets/icon.ico"))
    elif sys.platform == "darwin":
        app.setWindowIcon(QIcon("assets/icon.icns"))
    else:
        app.setWindowIcon(QIcon("assets/icon.png"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("fusion")
    set_icon(app)
    window = DragApp()
    window.getModList()
    window.disable_unimplemented()
    window.show()
    sys.exit(app.exec())
