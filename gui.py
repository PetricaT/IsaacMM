from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QStringListModel, QModelIndex, QMimeData, QByteArray, QDataStream, QIODevice
from PySide6.QtWidgets import QApplication, QMainWindow, QListView, QAbstractItemView, QPushButton, QWidget, QVBoxLayout, QGridLayout, QLabel
from PySide6.QtGui import QIcon
import xml.etree.ElementTree as ET
import sys
from matplotlib.image import thumbnail
import toml
import os
import re 


sorted_pattern = re.compile(r'[0-9]{3}\s{1}.*')

cfg_file = toml.load("config.toml")
mods_path = cfg_file["paths"]["mods"]

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
            print("case 1: ROW IS NOT -1, meaning inserting in between, above or below an existing node")
            beginRow = row
        elif parent.isValid():
            print("case 2: place item above parent")
            beginRow = parent.row()
        else:
            print("case 3: PARENT IS INVALID, inserting to root, "
                  "can change to 0 if you want it to appear at the top")
            beginRow = self.rowCount(QModelIndex())
        print(f"row={row}, beginRow={beginRow}")

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
    def __init__(self, parent=None):
        super(DragApp, self).__init__(parent)

        self.setWindowTitle('Tboi Mod Sorter')
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
        self.baseLayout.addWidget(self.refreshOrder, 1, 1)
        self.applyOrder.clicked.connect(self.printModel)
        self.refreshOrder.clicked.connect(self.getModList)

    def modListWidget(self):
        self.listView = QListView(self)
        self.listView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.listView.setDragEnabled(True)
        self.listView.setAcceptDrops(True)
        self.listView.setDropIndicatorShown(True)
        self.ddm = DragDropListModel()
        self.listView.setModel(self.ddm)

        self.getModList()

        self.applyOrder = QPushButton("Apply Sort Order")
        self.refreshOrder = QPushButton("Refresh")


    def printModel(self):
        # print(self.ddm.data(self.listView.currentIndex()))
        print(self.ddm.stringList())

    def getModList(self):
        # Get list of Isaac mods
        mod_list = os.listdir(mods_path)
        real_mod_name = []
        for mod in mod_list:
            mod_xml = ET.parse(f"{mods_path}/{mod}/metadata.xml")
            root = mod_xml.getroot()
            real_mod_name.append(root.find("name").text)
        
        real_mod_name.sort()

        self.ddm.setStringList([mod for mod in real_mod_name])


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('fusion')
    app.setWindowIcon(QIcon('assets/icon.png'))
    window = DragApp()
    window.show()
    sys.exit(app.exec())