from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow, QListView, QAbstractItemView, QPushButton, QWidget, QGridLayout, QFileDialog
from PySide6.QtCore import Qt, QStringListModel, QModelIndex, QMimeData, QByteArray, QDataStream, QIODevice
from PySide6 import QtCore, QtGui, QtWidgets
import xml.etree.ElementTree as ET
import getpass
import toml
import sys
import os
import re 


sorted_pattern = re.compile(r'[0-9]{3}\s{1}.*')

mods_path = ''
cfg_file = ''

version = 'v0.1.1'

try:
    cfg_file = toml.load("./config.toml")
    try:
        mods_path = cfg_file["paths"]["mods"]
    except:
        print("Mods path malformed, check if path is correct")
        mods_path = ''
except:
    print("Config file not found")
    with open('./config.toml', 'w') as f:
        f.write("[paths]\n")
        if sys.platform == 'darwin':
            # official MacOS support was dropped, so we know the path is permanently this, we can just guess it.
            f.write(f"mods='/Users/{getpass.getuser()}/Library/Application Support/Binding of Isaac Afterbirth+ Mods'")
        else:
            # Sadly, Linux support is weird, and Windows is a shot in the dark.
            f.write("mods=''")
        f.close


class DragDropListModel(QStringListModel):
    def __init__(self, parent=None):
        super(DragDropListModel, self).__init__(parent)

        self.myMimeTypes = 'application/json'

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

        self.setWindowTitle(f'Tboi Mod Manager [{version}]')
        self.resize(480, 320)

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

        self.applyOrder.setStyleSheet(f"background-color : {self.accent_color}; color : white;") 

        if mods_path == '':
            self.pickModsPath.setStyleSheet(f"background-color : red; color : white;")
        else:
            self.pickModsPath.setStyleSheet(f"background-color: auto; color: auto")


    def setModsPath(self):
        print('Presenting file dialog')
        cfg_file = toml.load("./config.toml")
        mods_path = QFileDialog.getExistingDirectory(self)
        cfg_file["paths"]["mods"] = mods_path


    def applyModOrder(self):
        i = 1
        names_array = []
        for mod in loaded_mods:
            names_array.append(mod[0])
        for mod in self.ddm.stringList():
            mod_index = names_array.index(mod) # index of mod in big array
            mod_path = loaded_mods[mod_index][1]
            if sorted_pattern.match(mod):
                # Mod was sorted previously, replace prefix
                mod_name = f'{f'{i}':0>3} {mod[4:]}'
            else:
                mod_name = f'{f'{i}':0>3} {mod}'
            mod_xml = ET.parse(f"{mods_path}/{mod_path}/metadata.xml")
            root = mod_xml.getroot()
            root.find("name").text = mod_name
            mod_xml.write(f"{mods_path}/{mod_path}/metadata.xml", encoding='utf-8', xml_declaration=True)
            i += 1
        self.getModList()


    def getModList(self):
        # Get list of Isaac mods
        if mods_path == '': return
        mod_list = os.listdir(mods_path)
        if loaded_mods != []:
            loaded_mods.clear()
        for mod in mod_list:
            mod_xml = ET.parse(f"{mods_path}/{mod}/metadata.xml")
            root = mod_xml.getroot()
            if [root.find("name").text, mod] not in loaded_mods:
                loaded_mods.append([root.find("name").text, mod])
        
        loaded_mods.sort()
        self.ddm.setStringList([mod[0] for mod in loaded_mods])


    def get_accent_color_hex(self):
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        palette = app.palette()
        accent_color = palette.color(QPalette.ColorRole.Highlight)
        return accent_color.name()


def set_icon(app):
    if sys.platform == 'win32':
        app.setWindowIcon(QIcon('assets/icon.ico'))
    elif sys.platform == 'darwin':
        app.setWindowIcon(QIcon('assets/icon.icns'))
    else:
        app.setWindowIcon(QIcon('assets/icon.png'))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('fusion')
    set_icon(app)
    window = DragApp()
    window.show()
    sys.exit(app.exec())
