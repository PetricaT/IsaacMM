import os
import re
import xml.etree.ElementTree as ET

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPalette, QPixmap, QStandardItem
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QStyledItemDelegate,
    QWidget,
)

CONFLICT_ROLE = Qt.UserRole + 1
SEPARATOR_ROLE = Qt.UserRole + 2
SEPARATOR_SUFFIX = "_separator"


class ConflictDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        p = QPixmap(os.path.join(paths.BASE_DIR, "assets", "warning.png"))
        self._warning = (
            p.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if not p.isNull() else None
        )

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if self._warning is None:
            return
        if not index.data(CONFLICT_ROLE):
            return
        rect = option.rect
        x = rect.right() - self._warning.width() - 4
        y = rect.top() + (rect.height() - self._warning.height()) // 2
        painter.drawPixmap(x, y, self._warning)


class SeparatorDialog(QDialog):
    def __init__(self, title, name="", color="#888888", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._color = color
        layout = QFormLayout(self)

        self.name_edit = QLineEdit(name)

        self.color_btn = QPushButton()
        self.color_btn.setStyleSheet(
            f"background-color: {color}; min-height: 24px; min-width: 60px;"
        )
        self.color_btn.clicked.connect(self._pick_color)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addRow("Name:", self.name_edit)
        layout.addRow("Color:", self.color_btn)
        layout.addRow(buttons)

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self)
        if c.isValid():
            self._color = c.name()
            self.color_btn.setStyleSheet(
                f"background-color: {self._color}; min-height: 24px; min-width: 60px;"
            )

    @property
    def result_name(self):
        return self.name_edit.text().strip()

    @property
    def result_color(self):
        return self._color


from . import config, paths, sorter
from .models import FlatDropModel
from .widgets import ModInfoPanel

sorted_pattern = re.compile(r"[0-9]{3}\s.*")


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)

        self.backup_check = QCheckBox("Back up mods on apply / auto-sort")
        self.backup_check.setChecked(config.backup_enabled)

        if config.mods_path:
            from .backup import get_backup_root
            br = get_backup_root(config.mods_path)
            loc_label = QLabel(f"Backup location: {br}")
        else:
            loc_label = QLabel("(set mods path first)")
        loc_label.setStyleSheet("color: gray;")

        run_btn = QPushButton("Run backup now")
        run_btn.clicked.connect(self._run_backup)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addRow(self.backup_check)
        layout.addRow(loc_label)
        layout.addRow(run_btn)
        layout.addRow(buttons)

    def _run_backup(self):
        if not config.mods_path:
            return
        from .backup import backup_all, get_backup_root
        backup_all(config.mods_path, get_backup_root(config.mods_path), config.loaded_mods)

    @property
    def result_backup_enabled(self):
        return self.backup_check.isChecked()


class DragApp(QWidget):
    loaded_mods = config.loaded_mods

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"Tboi Mod Manager [{paths.version}]")
        self.resize(1161, 550)
        self.pending_toggles = {}
        self._mod_files_cache = {}
        self._populating = False

        self.initUi()

    def initUi(self):
        self.baseLayout = QGridLayout(self)
        self.modListWidget()
        self.modInfoPanel = ModInfoPanel()
        self.modInfoPanel.setMaximumWidth(580)

        self.baseLayout.addWidget(self.listView, 0, 0, 5, 1)
        self.baseLayout.addWidget(self.modInfoPanel, 0, 1, 6, 1)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.applyOrder)
        btn_row.addWidget(self.autoSort)
        btn_row.addWidget(self.restoreOrder)
        btn_row.addStretch()
        btn_row.addWidget(self.addSeparatorBtn)
        btn_row.addWidget(self.settingsBtn)
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
        self.listView.setItemDelegate(ConflictDelegate(self.listView))
        self.model.itemChanged.connect(self.on_item_changed)
        self.model.rowsInserted.connect(self._on_rows_inserted)

        self.applyOrder = QPushButton("Apply Sort Order")
        self.autoSort = QPushButton("Auto Sort")
        self.restoreOrder = QPushButton("Restore Last Order")
        self.restoreOrder.setEnabled(sorter.load_last_order() is not None)
        self.pickModsPath = QPushButton("Select Mods Folder")
        self.currentPath = QLineEdit(f"{config.mods_path}")
        self.currentPath.setReadOnly(True)
        self.addSeparatorBtn = QPushButton("Add Separator")
        self.addSeparatorBtn.clicked.connect(self._create_separator)
        self.settingsBtn = QPushButton("Settings")
        self.settingsBtn.clicked.connect(self._open_settings)
        self.listView.doubleClicked.connect(self._on_item_double_clicked)

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
            mod_folder = item.data(Qt.UserRole)
            folder_order.append(mod_folder)
            if item.data(SEPARATOR_ROLE):
                continue
            mod_name = item.text()
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
            if folder.endswith(SEPARATOR_SUFFIX):
                continue
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
        self._mod_files_cache.clear()
        config.loaded_mods.clear()

        all_items = []
        sep_map = {}

        for entry in os.listdir(config.mods_path):
            if entry in (".DS_Store", "Thumbs.db"):
                continue
            full = os.path.join(config.mods_path, entry)
            if not os.path.isdir(full):
                continue

            if entry.endswith(SEPARATOR_SUFFIX):
                sep_path = os.path.join(full, "separator.xml")
                try:
                    tree = ET.parse(sep_path)
                    root = tree.getroot()
                    name = root.find("name").text
                    color_el = root.find("color")
                    color = color_el.text if color_el is not None else "#888888"
                except Exception:
                    name = entry[: -len(SEPARATOR_SUFFIX)]
                    color = "#888888"
                all_items.append((name, entry))
                sep_map[entry] = color
                continue

            try:
                mod_xml = ET.parse(os.path.join(full, "metadata.xml"))
                root = mod_xml.getroot()
                name = root.find("name").text
                config.loaded_mods.append([name, entry])
                all_items.append((name, entry))
            except FileNotFoundError:
                continue

        saved_order = sorter.load_last_order()
        if saved_order:
            by_folder = {f: (n, f) for n, f in all_items}
            ordered = []
            for folder in saved_order:
                if folder in by_folder:
                    ordered.append(by_folder.pop(folder))
            ordered.extend(by_folder.values())
            all_items = ordered
        else:
            all_items.sort(key=lambda x: x[0].lower())

        for name, folder in all_items:
            item = QStandardItem(name)
            item.setData(folder, Qt.UserRole)
            if folder in sep_map:
                color = sep_map[folder]
                item.setData({"name": name, "color": color}, SEPARATOR_ROLE)
                item.setBackground(QColor(color))
                item.setTextAlignment(Qt.AlignCenter)
            else:
                item.setCheckable(True)
                disable_path = os.path.join(config.mods_path, folder, "disable.it")
                item.setCheckState(
                    Qt.Unchecked if os.path.exists(disable_path) else Qt.Checked
                )
            self.model.appendRow(item)

        self._populating = False
        self._maybe_backup()
        self._update_conflict_indicators()
        self._update_path_button_style()

    def _on_rows_inserted(self, parent, first, last):
        if self._populating:
            return
        QTimer.singleShot(0, self._update_conflict_indicators)

    def _update_conflict_indicators(self):
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            if item is None:
                continue
            item.setData(None, CONFLICT_ROLE)
            sep_data = item.data(SEPARATOR_ROLE)
            if sep_data:
                item.setBackground(QColor(sep_data["color"]))
                item.setTextAlignment(Qt.AlignCenter)
        for i in range(self.model.rowCount()):
            item_i = self.model.item(i)
            if item_i is None or item_i.data(SEPARATOR_ROLE):
                continue
            for j in range(i + 1, self.model.rowCount()):
                item_j = self.model.item(j)
                if item_j is None or item_j.data(SEPARATOR_ROLE):
                    continue
                common = (
                    self._scan_mod_files(item_i.data(Qt.UserRole))
                    & self._scan_mod_files(item_j.data(Qt.UserRole))
                )
                if not common:
                    continue
                item_i.setData(True, CONFLICT_ROLE)
                item_j.setData(True, CONFLICT_ROLE)

    def on_mod_selected(self, selected, deselected):
        if self._populating:
            return

        indexes = self.listView.selectedIndexes()

        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            if item.data(SEPARATOR_ROLE):
                sep = item.data(SEPARATOR_ROLE)
                item.setBackground(QColor(sep["color"]))
            else:
                item.setBackground(QBrush())

        if not indexes:
            self.modInfoPanel.clear()
            return

        item = self.model.itemFromIndex(indexes[0])

        sep_data = item.data(SEPARATOR_ROLE)
        if sep_data:
            self.modInfoPanel.clear()
            folder = item.data(Qt.UserRole)
            self.modInfoPanel._mod_path = os.path.join(config.mods_path, folder)
            self.modInfoPanel.folder_button.setEnabled(True)
            self.modInfoPanel.state_label.setText(sep_data["name"])
            self.modInfoPanel.state_label.setStyleSheet(
                f"color: {sep_data['color']}; font-weight: bold; font-size: 14px;"
            )
            self.modInfoPanel.folder_label.setText(
                f"Separator folder: {folder}"
            )
            return

        self.modInfoPanel.show_mod_info(
            item.text(), item.data(Qt.UserRole), item.checkState()
        )

        mod_folder = item.data(Qt.UserRole)
        current_files = self._scan_mod_files(mod_folder)
        current_idx = next(
            (i for i in range(self.model.rowCount())
             if self.model.item(i).data(Qt.UserRole) == mod_folder),
            -1,
        )

        for row in range(self.model.rowCount()):
            other = self.model.item(row)
            other_folder = other.data(Qt.UserRole)
            if other_folder == mod_folder:
                continue
            common = current_files & self._scan_mod_files(other_folder)
            if not common:
                continue
            if row < current_idx:
                other.setBackground(QColor("#9E4D4D"))
            else:
                other.setBackground(QColor("#65A665"))

    def _scan_mod_files(self, folder):
        cached = self._mod_files_cache.get(folder)
        if cached is not None:
            return cached
        files = set()
        mod_path = os.path.join(config.mods_path, folder)
        try:
            for root, dirs, fnames in os.walk(mod_path):
                dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
                for f in fnames:
                    if f in ('metadata.xml', 'disable.it', '.DS_Store', 'Thumbs.db'):
                        continue
                    rel = os.path.relpath(os.path.join(root, f), mod_path)
                    if '/' in rel or '\\' in rel:
                        files.add(rel)
        except OSError:
            pass
        self._mod_files_cache[folder] = files
        return files

    def on_item_changed(self, item):
        if self._populating:
            return
        folder = item.data(Qt.UserRole)
        if folder:
            self.pending_toggles[folder] = item.checkState()

    def autoSortMods(self):
        mods_data = []
        separators = []
        for r in range(self.model.rowCount()):
            item = self.model.item(r)
            sep_data = item.data(SEPARATOR_ROLE)
            if sep_data:
                separators.append({
                    "name": item.text(),
                    "folder": item.data(Qt.UserRole),
                    "color": sep_data["color"],
                    "index": len(mods_data),
                })
            else:
                mods_data.append({
                    "name": item.text(),
                    "folder": item.data(Qt.UserRole),
                    "checked": item.checkState(),
                })

        sorted_mods = sorter.auto_sort(
            [[d["name"], d["folder"]] for d in mods_data],
            config.mods_path,
        )

        self._populating = True
        self.model.clear()
        self._mod_files_cache.clear()

        sorted_list = list(sorted_mods)
        for sep in separators:
            pos = min(sep["index"], len(sorted_list))
            sorted_list.insert(pos, (sep["name"], sep["folder"]))

        mod_lookup = {d["folder"]: d for d in mods_data}
        sep_lookup = {s["folder"]: s for s in separators}
        for name, folder in sorted_list:
            if folder in sep_lookup:
                s = sep_lookup[folder]
                item = QStandardItem(name)
                item.setData(folder, Qt.UserRole)
                item.setData({"name": name, "color": s["color"]}, SEPARATOR_ROLE)
                item.setBackground(QColor(s["color"]))
                item.setTextAlignment(Qt.AlignCenter)
            else:
                d = mod_lookup.get(folder, {})
                item = QStandardItem(name)
                item.setCheckable(True)
                item.setCheckState(d.get("checked", Qt.Checked))
                item.setData(folder, Qt.UserRole)
            self.model.appendRow(item)

        config.loaded_mods = [
            [name, folder] for name, folder in sorted_list
            if folder not in sep_lookup
        ]
        self._populating = False
        self._maybe_backup()
        self._update_conflict_indicators()

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        config.backup_enabled = dlg.result_backup_enabled
        config.save()

    def _maybe_backup(self):
        if not config.backup_enabled or not config.mods_path:
            return
        from .backup import backup_all, get_backup_root
        backup_all(config.mods_path, get_backup_root(config.mods_path), config.loaded_mods)

    def _create_separator(self):
        dlg = SeparatorDialog("Create Separator", parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        name = dlg.result_name
        color = dlg.result_color
        if not name:
            return
        folder = f"{name}{SEPARATOR_SUFFIX}"
        folder_path = os.path.join(config.mods_path, folder)
        try:
            os.makedirs(folder_path, exist_ok=True)
            root = ET.Element("separator")
            ET.SubElement(root, "name").text = name
            ET.SubElement(root, "color").text = color
            tree = ET.ElementTree(root)
            tree.write(
                os.path.join(folder_path, "separator.xml"),
                encoding="utf-8",
                xml_declaration=True,
            )
            self.getModList()
        except OSError:
            pass

    def _on_item_double_clicked(self, index):
        item = self.model.itemFromIndex(index)
        if not item.data(SEPARATOR_ROLE):
            return
        self._edit_separator(item)

    def _edit_separator(self, item):
        sep = item.data(SEPARATOR_ROLE)
        old_folder = item.data(Qt.UserRole)
        dlg = SeparatorDialog(
            "Edit Separator", name=sep["name"], color=sep["color"], parent=self
        )
        if dlg.exec() != QDialog.Accepted:
            return
        new_name = dlg.result_name
        new_color = dlg.result_color
        if not new_name:
            return
        new_folder = f"{new_name}{SEPARATOR_SUFFIX}"
        if old_folder != new_folder:
            try:
                os.rename(
                    os.path.join(config.mods_path, old_folder),
                    os.path.join(config.mods_path, new_folder),
                )
            except OSError:
                return
        sep_path = os.path.join(config.mods_path, new_folder, "separator.xml")
        root = ET.Element("separator")
        ET.SubElement(root, "name").text = new_name
        ET.SubElement(root, "color").text = new_color
        tree = ET.ElementTree(root)
        tree.write(sep_path, encoding="utf-8", xml_declaration=True)
        self.getModList()

    def _get_accent_color_hex(self):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if not app:
            app = QApplication([])
        palette = app.palette()
        accent_color = palette.color(QPalette.ColorRole.Highlight)
        return accent_color.name()
