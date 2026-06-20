import os
import re
import xml.etree.ElementTree as ET

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QStandardItem
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QListView,
    QPushButton,
    QWidget,
)

from . import config, paths, sorter
from .models import FlatDropModel
from .widgets import ModInfoPanel

sorted_pattern = re.compile(r"[0-9]{3}\s{1}.*")


class DragApp(QWidget):
    loaded_mods = config.loaded_mods

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"Tboi Mod Manager [{paths.version}]")
        self.resize(800, 400)
        self.pending_toggles = {}
        self._populating = False

        self.initUi()

    def initUi(self):
        self.baseLayout = QGridLayout(self)
        self.modListWidget()
        self.modInfoPanel = ModInfoPanel()

        self.baseLayout.addWidget(self.listView, 0, 0, 5, 1)
        self.baseLayout.addWidget(self.modInfoPanel, 0, 1, 6, 1)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.applyOrder)
        btn_row.addWidget(self.autoSort)
        btn_row.addWidget(self.restoreOrder)
        self.baseLayout.addLayout(btn_row, 5, 0)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self.pickModsPath)
        bottom_row.addWidget(self.currentPath, 1)
        self.baseLayout.addLayout(bottom_row, 6, 0, 1, 2)

        self.baseLayout.setColumnStretch(0, 1)
        self.baseLayout.setColumnStretch(1, 1)

        self.applyOrder.clicked.connect(self.applyModOrder)
        self.autoSort.clicked.connect(self.autoSortMods)
        self.restoreOrder.clicked.connect(self.restoreLastOrder)
        self.pickModsPath.clicked.connect(self.setModsPath)
        self.listView.selectionModel().selectionChanged.connect(
            self.on_mod_selected
        )

    def modListWidget(self):
        self.accent_color = self._get_accent_color_hex()
        self.listView = QListView(self)
        self.listView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.listView.setDragEnabled(True)
        self.listView.setAcceptDrops(True)
        self.listView.setDropIndicatorShown(True)
        self.listView.setDragDropMode(QAbstractItemView.InternalMove)
        self.listView.setDefaultDropAction(Qt.MoveAction)
        self.listView.setAlternatingRowColors(True)
        pal = self.listView.palette()
        base = pal.color(QPalette.Base)
        alt = base.lighter(120) if base.lightness() < 128 else base.darker(108)
        pal.setColor(QPalette.AlternateBase, alt)
        self.listView.setPalette(pal)

        self.model = FlatDropModel()
        self.listView.setModel(self.model)
        self.model.itemChanged.connect(self.on_item_changed)

        self.applyOrder = QPushButton("Apply Sort Order")
        self.autoSort = QPushButton("Auto Sort")
        self.restoreOrder = QPushButton("Restore Last Order")
        self.restoreOrder.setEnabled(sorter.load_last_order() is not None)
        self.pickModsPath = QPushButton("Select Mods Folder")
        self.currentPath = QLineEdit(f"{config.mods_path}")
        self.currentPath.setReadOnly(True)

        self.getModList()
        self.applyOrder.setStyleSheet(f"background-color : {self.accent_color}")
        self._update_path_button_style()

    def setModsPath(self):
        start_dir = ""
        if config.mods_path and os.path.isdir(config.mods_path):
            start_dir = config.mods_path
        else:
            detected = paths.find_isaac_mods_folder()
            if detected and os.path.isdir(detected):
                start_dir = detected
        new_path = QFileDialog.getExistingDirectory(
            self, "Select Mods Folder", start_dir
        )
        if new_path:
            config.mods_path = new_path
            config.save()
            self.currentPath.setText(new_path)
            self.getModList()

    def applyModOrder(self):
        i = 1
        folder_order = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            mod_name = item.text()
            mod_folder = item.data(Qt.UserRole)
            folder_order.append(mod_folder)
            if sorted_pattern.match(mod_name):
                new_name = f"{i:03} {mod_name[4:]}"
            else:
                new_name = f"{i:03} {mod_name}"
            mod_xml = ET.parse(f"{config.mods_path}/{mod_folder}/metadata.xml")
            root = mod_xml.getroot()
            root.find("name").text = new_name
            mod_xml.write(
                f"{config.mods_path}/{mod_folder}/metadata.xml",
                encoding="utf-8",
                xml_declaration=True,
            )
            i += 1
        for folder, state in self.pending_toggles.items():
            disable_path = os.path.join(config.mods_path, folder, "disable.it")
            if state == Qt.Unchecked:
                open(disable_path, "a").close()
            else:
                try:
                    os.remove(disable_path)
                except FileNotFoundError:
                    pass
        self.pending_toggles.clear()
        sorter.save_last_order(folder_order)
        self.getModList()

    def restoreLastOrder(self):
        folder_order = sorter.load_last_order()
        if not folder_order:
            return
        i = 1
        for folder in folder_order:
            xml_path = os.path.join(config.mods_path, folder, "metadata.xml")
            if not os.path.exists(xml_path):
                continue
            mod_xml = ET.parse(xml_path)
            root = mod_xml.getroot()
            name = root.find("name").text
            if sorted_pattern.match(name):
                name = name[4:]
            root.find("name").text = f"{i:03} {name}"
            mod_xml.write(xml_path, encoding="utf-8", xml_declaration=True)
            i += 1
        self.getModList()

    def _update_path_button_style(self):
        if config.mods_path == "" or config.loaded_mods == []:
            self.pickModsPath.setStyleSheet("background-color : red")
        else:
            self.pickModsPath.setStyleSheet("")

    def getModList(self):
        if config.mods_path == "":
            self._update_path_button_style()
            return

        self._populating = True
        self.model.clear()
        self.pending_toggles.clear()
        config.loaded_mods.clear()

        mod_list = os.listdir(config.mods_path)
        try:
            ds_index = mod_list.index(".DS_Store")
            mod_list.pop(ds_index)
        except ValueError:
            pass

        for mod_folder in mod_list:
            try:
                mod_xml = ET.parse(
                    f"{config.mods_path}/{mod_folder}/metadata.xml"
                )
                root = mod_xml.getroot()
                name = root.find("name").text
                config.loaded_mods.append([name, mod_folder])
            except FileNotFoundError:
                continue

        config.loaded_mods.sort(key=lambda x: x[0])

        for name, mod_folder in config.loaded_mods:
            item = QStandardItem(name)
            item.setCheckable(True)
            disable_path = os.path.join(
                config.mods_path, mod_folder, "disable.it"
            )
            item.setCheckState(
                Qt.Unchecked if os.path.exists(disable_path) else Qt.Checked
            )
            item.setData(mod_folder, Qt.UserRole)
            self.model.appendRow(item)

        self._populating = False
        self._update_path_button_style()

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

    def autoSortMods(self):
        items_data = []
        for r in range(self.model.rowCount()):
            item = self.model.item(r)
            items_data.append({
                "name": item.text(),
                "folder": item.data(Qt.UserRole),
                "checked": item.checkState(),
            })

        sorted_items = sorter.auto_sort(
            [[d["name"], d["folder"]] for d in items_data],
            config.mods_path,
        )

        self._populating = True
        self.model.clear()

        folder_data = {d["folder"]: d for d in items_data}
        for name, folder in sorted_items:
            d = folder_data.get(folder, {})
            item = QStandardItem(name)
            item.setCheckable(True)
            item.setCheckState(d.get("checked", Qt.Checked))
            item.setData(folder, Qt.UserRole)
            self.model.appendRow(item)

        config.loaded_mods = [[name, folder] for name, folder in sorted_items]
        self._populating = False

    def _get_accent_color_hex(self):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if not app:
            app = QApplication([])
        palette = app.palette()
        accent_color = palette.color(QPalette.ColorRole.Highlight)
        return accent_color.name()
