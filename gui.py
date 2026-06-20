import os
import re
import sys
import xml.etree.ElementTree as ET

import toml
from PySide6.QtCore import (
    QByteArray,
    QDataStream,
    QIODevice,
    QMimeData,
    QModelIndex,
    QStringListModel,
    Qt,
)
from PySide6.QtGui import QIcon, QPalette, QPixmap
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


class DragDropListModel(QStringListModel):
    def __init__(self, parent=None):
        super(DragDropListModel, self).__init__(parent)

        self.myMimeTypes = "application/json"

    def supportedDropActions(self):
        return Qt.MoveAction

    def flags(self, index):
        defaultFlags = QStringListModel.flags(self, index)

        if index.isValid():
            return Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled | defaultFlags
        else:
            return Qt.ItemIsDropEnabled | defaultFlags

    def mimeTypes(self):
        return [self.myMimeTypes]

    def mimeData(self, indexes):
        mmData = QMimeData()
        encodedData = QByteArray()
        stream = QDataStream(encodedData, QIODevice.WriteOnly)

        for index in indexes:
            if index.isValid():
                text = self.data(index, Qt.DisplayRole)
                stream << text

        mmData.setData(self.myMimeTypes, encodedData)
        return mmData

    def canDropMimeData(self, data, action, row, column, parent):
        if data.hasFormat(self.myMimeTypes) is False:
            return False
        if column > 0:
            return False
        return True

    def dropMimeData(self, data, action, row, column, parent):
        if self.canDropMimeData(data, action, row, column, parent) is False:
            return False

        if action == Qt.IgnoreAction:
            return True

        beginRow = -1
        if row != -1:
            beginRow = row
        elif parent.isValid():
            beginRow = parent.row()
        else:
            beginRow = self.rowCount(QModelIndex())

        encodedData = data.data(self.myMimeTypes)
        stream = QDataStream(encodedData, QIODevice.ReadOnly)
        newItems = []
        rows = 0

        while stream.atEnd() is False:
            text = stream.readQString()
            newItems.append(str(text))
            rows += 1

        self.insertRows(beginRow, rows, QModelIndex())
        for text in newItems:
            idx = self.index(beginRow, 0, QModelIndex())
            self.setData(idx, text)
            beginRow += 1

        return True


class ModInfoPanel(QWidget):
    PRIORITY_ICON_NAMES = [
        "title",
        "thumbnail",
        "icon",
        "modicon",
        "logo",
        "spider thumbnail",
    ]
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif"}

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(128, 128)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("border: 1px solid gray;")

        self.state_label = QLabel("Select a mod")
        self.state_label.setAlignment(Qt.AlignCenter)

        self.description_text = QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setPlaceholderText("Select a mod to view its description")

        layout.addWidget(self.icon_label)
        layout.addWidget(self.state_label)
        layout.addWidget(self.description_text)

    def show_mod_info(self, mod_name):
        mod_folder = None
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

        if icon_path:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                self.icon_label.setPixmap(
                    pixmap.scaled(
                        128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                )
            else:
                self.icon_label.setText("No icon")
        else:
            self.icon_label.setText("No icon")

        disable_path = os.path.join(mod_path, "disable.it")
        if os.path.exists(disable_path):
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

    def clear(self):
        self.icon_label.clear()
        self.icon_label.setText("No icon")
        self.state_label.setText("Select a mod")
        self.state_label.setStyleSheet("")
        self.description_text.clear()


class DragApp(QWidget):
    global loaded_mods
    loaded_mods = []

    def __init__(self, parent=None):
        super(DragApp, self).__init__(parent)

        self.setWindowTitle(f"Tboi Mod Manager [{version}]")
        self.resize(800, 400)
        self.previous_mods_path = ""

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
        self.ddm = DragDropListModel()
        self.listView.setModel(self.ddm)

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
        names_array = []
        for mod in loaded_mods:
            names_array.append(mod[0])
        for mod in self.ddm.stringList():
            mod_index = names_array.index(mod)  # index of mod in big array
            mod_path = loaded_mods[mod_index][1]
            if sorted_pattern.match(mod):
                # Mod was sorted previously, replace prefix
                mod_name = f"{i:03} {mod[4:]}"
            else:
                mod_name = f"{i:03} {mod}"
            mod_xml = ET.parse(f"{mods_path}/{mod_path}/metadata.xml")
            root = mod_xml.getroot()
            root.find("name").text = mod_name
            mod_xml.write(
                f"{mods_path}/{mod_path}/metadata.xml",
                encoding="utf-8",
                xml_declaration=True,
            )
            i += 1
        self.getModList()

    def getModList(self):
        # If path is unset, return
        if mods_path == "":
            return
        # Get list of Isaac mods
        mod_list = os.listdir(mods_path)
        try:
            # Hacky macos DS_Store skip
            ds_index = mod_list.index(".DS_Store")
            mod_list.pop(ds_index)
        except ValueError:
            pass
        # If path has changed, refresh the list
        reset_model = False
        if mods_path != self.previous_mods_path:
            loaded_mods.clear()
            self.ddm.beginResetModel()
            self.previous_mods_path = mods_path
            reset_model = True
        for mod in mod_list:
            try:
                mod_xml = ET.parse(f"{mods_path}/{mod}/metadata.xml")
                root = mod_xml.getroot()
                if [root.find("name").text, mod] not in loaded_mods:
                    loaded_mods.append([root.find("name").text, mod])
            except FileNotFoundError:
                continue
        loaded_mods.sort()
        if reset_model:
            self.ddm.endResetModel()
        self.ddm.setStringList([mod[0] for mod in loaded_mods])

    def on_mod_selected(self, selected, deselected):
        indexes = self.listView.selectedIndexes()
        if indexes:
            mod_name = indexes[0].data(Qt.DisplayRole)
            self.modInfoPanel.show_mod_info(mod_name)
        else:
            self.modInfoPanel.clear()

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
