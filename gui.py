from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QListView,
    QAbstractItemView,
    QPushButton,
    QWidget,
    QGridLayout,
    QFileDialog,
    QLineEdit,
)
from PySide6.QtCore import (
    Qt,
    QStringListModel,
    QModelIndex,
    QMimeData,
    QByteArray,
    QDataStream,
    QIODevice,
)
import xml.etree.ElementTree as ET
import toml
import time
import sys
import os
import re


sorted_pattern = re.compile(r"[0-9]{3}\s{1}.*")
exclamation_marks = re.compile(r"\s!{1,12}")

mods_path = ""
cfg_file = ""

version = "v0.2.4"

try:
    # Global Settings & Vars
    # Mods path:    str     - Path to mods folder
    # Remove marks: bool    - Remove exclamation marks from mod names
    #
    cfg_file = toml.load("./config.toml")
    mods_path = cfg_file["paths"]["mods"]
    if mods_path == "":
        print("Mods path malformed, check if path is correct")
        mods_path = ""
    remove_marks = cfg_file["settings"]["remove_marks"]
    if remove_marks == "true":
        remove_marks = True
    else:
        remove_marks = False
except:
    print("Config file not found")
    with open("./config.toml", "w") as f:
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


class DragApp(QWidget):
    global loaded_mods
    loaded_mods = []

    def __init__(self, parent=None):
        super(DragApp, self).__init__(parent)

        self.setWindowTitle(f"Tboi Mod Manager [{version}]")
        self.resize(490, 320)

        self.initUi()

    def initUi(self):
        self.baseLayout = QGridLayout(self)
        # +----------+----------+
        # | ListView | Mod Info |
        # +----------+----------+
        self.modListWidget()

        self.baseLayout.addWidget(self.listView, 0, 0)
        self.baseLayout.addWidget(self.applyOrder, 1, 0)
        self.baseLayout.addWidget(self.autoSort, 1, 1)
        self.baseLayout.addWidget(self.refreshOrder, 2, 1)
        self.baseLayout.addWidget(self.pickModsPath, 2, 0)
        self.baseLayout.addWidget(self.currentPath, 3, 0)
        self.applyOrder.clicked.connect(self.applyModOrder)
        # self.autoSort.clicked.connect(self.autoSortMods)
        self.refreshOrder.clicked.connect(self.getModList)
        self.pickModsPath.clicked.connect(self.setModsPath)

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
        cfg_file = toml.load("./config.toml")
        mods_path = QFileDialog.getExistingDirectory(self)
        cfg_file["paths"]["mods"] = mods_path
        with open("./config.toml", "w") as f:
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
        # Get list of Isaac mods
        print("[DEBUG] Recieved REFRESH signal")
        if mods_path == "":
            return
        mod_list = os.listdir(mods_path)
        try:
            # Hacky macos DS_Store skip
            ds_index = mod_list.index('.DS_Store')
            mod_list.pop(ds_index)
        except:
            pass
        if loaded_mods != []:
            loaded_mods.clear()
            # self.ddm.setStringList('')
            self.ddm.beginResetModel()
            self.ddm.endResetModel()
        try:
            for mod in mod_list:
                mod_xml = ET.parse(f"{mods_path}/{mod}/metadata.xml")
                root = mod_xml.getroot()
                if [root.find("name").text, mod] not in loaded_mods:
                    loaded_mods.append([root.find("name").text, mod])

            loaded_mods.sort()
            self.ddm.setStringList([mod[0] for mod in loaded_mods])
        except FileNotFoundError:
            print("[DEBUG] Current modpath is invalid")

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
