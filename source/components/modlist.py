import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListView,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import config, logger, paths, sorter
from ..models import FlatDropModel
from ..modlist_io import export_modlist_csv, import_modlist_csv
from .dialogs import (
    CONFLICT_ROLE,
    OVERWRITTEN_ROLE,
    PREV_CHECK_ROLE,
    SEPARATOR_ROLE,
    ConflictDelegate,
    SeparatorDialog,
)
from .file_utils import open_path

SEPARATOR_SUFFIX = "_separator"
sorted_pattern = re.compile(r"[0-9]{3}\s.*")


class ModListPanel(QWidget):
    mod_selected = Signal(str, str, object)
    log_message = Signal(str, str)
    open_settings = Signal()
    mods_loaded = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.pending_toggles: dict = {}
        self._mod_files_cache: dict = {}
        self._populating: bool = False
        self._updating_conflicts: bool = False
        self._first_load: bool = True
        self._accent_color = config.accent_color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        modlist_header_layout = QHBoxLayout()
        modlist_label = QLabel("<b>Mod List</b>")
        modlist_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        menu_button = QPushButton("\u2630")
        menu_button.setFixedWidth(30)
        overflow_menu = QMenu(menu_button)
        overflow_menu.addAction("Add Separator", self._create_separator)
        overflow_menu.addAction("Export modlist (.csv)", self._export_modlist)
        overflow_menu.addAction("Import modlist (.csv)", self._import_modlist)
        menu_button.setMenu(overflow_menu)
        modlist_header_layout.addWidget(modlist_label, 1)
        modlist_header_layout.addWidget(menu_button)
        layout.addLayout(modlist_header_layout)

        self.listView = QListView(self)
        self.listView.setStyleSheet(
            f"QListView::item:selected {{ background-color: {self._accent_color}; }}"
        )
        self.listView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.listView.setDragEnabled(True)
        self.listView.setAcceptDrops(True)
        self.listView.setDropIndicatorShown(True)
        self.listView.setDragDropMode(QAbstractItemView.InternalMove)
        self.listView.setDefaultDropAction(Qt.MoveAction)
        self.listView.setAlternatingRowColors(True)
        current_palette = self.listView.palette()
        base_color = current_palette.color(QPalette.Base)
        alternate_color = (
            base_color.lighter(120)
            if base_color.lightness() < 128
            else base_color.darker(108)
        )
        current_palette.setColor(QPalette.AlternateBase, alternate_color)
        self.listView.setPalette(current_palette)

        self.model = FlatDropModel()
        self.listView.setModel(self.model)
        self.listView.setItemDelegate(ConflictDelegate(self.listView))
        self.model.itemChanged.connect(self._on_item_changed)
        self.model.rowsInserted.connect(self._on_rows_inserted)

        self.applyOrder = QPushButton("Apply Sort Order")
        self.autoSort = QPushButton("Auto Sort")
        self.restoreOrder = QPushButton("Restore Last Order")
        self.restoreOrder.setEnabled(sorter.load_last_order() is not None)
        self.settingsBtn = QPushButton("Settings")
        self.settingsBtn.clicked.connect(self.open_settings.emit)
        self.listView.doubleClicked.connect(self._on_item_double_clicked)
        self.listView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listView.customContextMenuRequested.connect(self._on_context_menu)

        layout.addWidget(self.listView, 1)

        button_row = QHBoxLayout()
        button_row.addWidget(self.applyOrder)
        button_row.addWidget(self.autoSort)
        button_row.addWidget(self.restoreOrder)
        button_row.addStretch()
        button_row.addWidget(self.settingsBtn)
        layout.addLayout(button_row)

        self.applyOrder.clicked.connect(self.apply_mod_order)
        self.autoSort.clicked.connect(self.auto_sort_mods)
        self.restoreOrder.clicked.connect(self.restore_last_order)
        self.listView.selectionModel().selectionChanged.connect(self._on_mod_selected)

        self.applyOrder.setStyleSheet(f"background-color : {self._accent_color}")
        self.load_mod_list()

    def load_mod_list(self) -> None:
        if config.mods_path == "":
            self.log_message.emit(
                "No mods folder set \u2014 open Settings to configure one", "warning"
            )
            return

        self._populating = True
        self.model.clear()
        self.pending_toggles.clear()
        self._mod_files_cache.clear()
        config.loaded_mods.clear()

        all_entries = []
        separator_map = {}

        try:
            directory_entries = os.listdir(config.mods_path)
        except OSError as exc:
            self.log_message.emit(f"Failed to list mods folder: {exc}", "error")
            self._populating = False
            return

        for directory_entry in directory_entries:
            if directory_entry in (".DS_Store", "Thumbs.db"):
                continue
            full_path = os.path.join(config.mods_path, directory_entry)
            if not os.path.isdir(full_path):
                continue

            if directory_entry.endswith(SEPARATOR_SUFFIX):
                separator_xml_path = os.path.join(full_path, "separator.xml")
                try:
                    metadata_tree = ET.parse(separator_xml_path)
                    xml_root = metadata_tree.getroot()
                    separator_name = xml_root.find("name").text
                    color_element = xml_root.find("color")
                    separator_color = (
                        color_element.text if color_element is not None else "#888888"
                    )
                except Exception:
                    separator_name = directory_entry[: -len(SEPARATOR_SUFFIX)]
                    separator_color = "#888888"
                all_entries.append((separator_name, directory_entry))
                separator_map[directory_entry] = separator_color
                continue

            try:
                metadata_tree = ET.parse(os.path.join(full_path, "metadata.xml"))
                xml_root = metadata_tree.getroot()
                mod_name = xml_root.find("name").text
                config.loaded_mods.append([mod_name, directory_entry])
                all_entries.append((mod_name, directory_entry))
            except FileNotFoundError:
                continue

        saved_folder_order = sorter.load_last_order()
        if saved_folder_order:
            entries_by_folder = {folder: (name, folder) for name, folder in all_entries}
            ordered_entries = []
            for folder_name in saved_folder_order:
                if folder_name in entries_by_folder:
                    ordered_entries.append(entries_by_folder.pop(folder_name))
            ordered_entries.extend(entries_by_folder.values())
            all_entries = ordered_entries
        else:
            all_entries.sort(key=lambda entry: entry[0].lower())

        for entry_name, entry_folder in all_entries:
            list_item = self._make_list_item()
            list_item.setText(entry_name)
            list_item.setData(entry_folder, Qt.UserRole)
            if entry_folder in separator_map:
                separator_color = separator_map[entry_folder]
                list_item.setData(
                    {"name": entry_name, "color": separator_color}, SEPARATOR_ROLE
                )
                list_item.setBackground(QColor(separator_color))
                list_item.setTextAlignment(Qt.AlignCenter)
            else:
                list_item.setCheckable(True)
                disable_file_path = os.path.join(
                    config.mods_path, entry_folder, "disable.it"
                )
                initial_state = (
                    Qt.CheckState.Unchecked
                    if os.path.exists(disable_file_path)
                    else Qt.CheckState.Checked
                )
                list_item.setCheckState(initial_state)
                list_item.setData(initial_state, PREV_CHECK_ROLE)
            self.model.appendRow(list_item)

        self._populating = False
        if self._first_load:
            self._first_load = False
            self.log_message.emit(
                f"Loaded {len(config.loaded_mods)} mods, {len(separator_map)} separators",
                "info",
            )
        self._update_conflict_indicators()
        self.mods_loaded.emit()

    def _make_list_item(self):
        from PySide6.QtGui import QStandardItem

        return QStandardItem()

    def _on_rows_inserted(self, parent, first_row: int, last_row: int) -> None:
        if self._populating:
            return
        self._update_conflict_indicators()

    def _update_conflict_indicators(self) -> None:
        if self._updating_conflicts:
            return
        self._updating_conflicts = True
        t0 = time.perf_counter()

        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            if list_item is None:
                continue
            list_item.setData(None, CONFLICT_ROLE)
            list_item.setData(None, OVERWRITTEN_ROLE)
            separator_data = list_item.data(SEPARATOR_ROLE)
            if separator_data:
                list_item.setBackground(QColor(separator_data["color"]))
                list_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        file_to_mods: dict[str, set[int]] = {}
        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            if list_item is None or list_item.data(SEPARATOR_ROLE) or list_item.checkState() != Qt.CheckState.Checked:
                continue
            for f in self._scan_mod_files(list_item.data(Qt.UserRole)):
                file_to_mods.setdefault(f, set()).add(row_index)

        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            if list_item is None or list_item.data(SEPARATOR_ROLE) or list_item.checkState() != Qt.CheckState.Checked:
                continue
            for f in self._scan_mod_files(list_item.data(Qt.UserRole)):
                if len(file_to_mods.get(f, ())) > 1:
                    list_item.setData(True, CONFLICT_ROLE)
                    break

        running_files: set[str] = set()
        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            if list_item is None or list_item.data(SEPARATOR_ROLE) or list_item.checkState() != Qt.CheckState.Checked:
                continue
            mod_files = self._scan_mod_files(list_item.data(Qt.UserRole))
            if mod_files and mod_files.issubset(running_files):
                list_item.setData(True, OVERWRITTEN_ROLE)
            running_files |= mod_files

        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            if list_item is None or list_item.data(SEPARATOR_ROLE):
                continue
            if list_item.checkState() != Qt.CheckState.Checked:
                list_item.setForeground(QColor(config.disabled_mod_color))
            elif list_item.data(OVERWRITTEN_ROLE):
                list_item.setForeground(QColor(config.disabled_mod_color))
                font = list_item.font()
                font.setItalic(True)
                list_item.setFont(font)
            else:
                list_item.setData(None, Qt.ItemDataRole.ForegroundRole)

        total_ms = (time.perf_counter() - t0) * 1000
        if total_ms > 5 and config.log_level == "debug":
            self.log_message.emit(
                f"Conflict scan: {total_ms:.0f}ms ({self.model.rowCount()} mods)", "debug"
            )
        self._updating_conflicts = False

    def _on_mod_selected(self, selected, deselected) -> None:
        if self._populating:
            return

        selected_indexes = self.listView.selectedIndexes()

        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            if list_item.data(SEPARATOR_ROLE):
                separator_data = list_item.data(SEPARATOR_ROLE)
                list_item.setBackground(QColor(separator_data["color"]))
            else:
                list_item.setBackground(QBrush())
                if list_item.checkState() != Qt.CheckState.Checked:
                    list_item.setForeground(QColor(config.disabled_mod_color))
                elif list_item.data(OVERWRITTEN_ROLE):
                    list_item.setForeground(QColor(config.disabled_mod_color))
                    font = list_item.font()
                    font.setItalic(True)
                    list_item.setFont(font)
                else:
                    list_item.setData(None, Qt.ItemDataRole.ForegroundRole)

        if not selected_indexes:
            self.mod_selected.emit("", None, None)
            return

        selected_item = self.model.itemFromIndex(selected_indexes[0])

        separator_data = selected_item.data(SEPARATOR_ROLE)
        if separator_data:
            self.mod_selected.emit(
                separator_data["name"],
                selected_item.data(Qt.UserRole),
                None,
            )
            return

        self._refresh_selection_conflicts(selected_item)

    def _refresh_selection_conflicts(self, selected_item) -> None:
        mod_folder = selected_item.data(Qt.UserRole)

        if selected_item.checkState() != Qt.CheckState.Checked:
            self.mod_selected.emit(selected_item.text(), mod_folder, {})
            return

        current_mod_files = self._scan_mod_files(mod_folder)
        current_mod_index = next(
            index
            for index in range(self.model.rowCount())
            if self.model.item(index).data(Qt.UserRole) == mod_folder
        )

        conflict_mods = {}
        for row_index in range(self.model.rowCount()):
            other_item = self.model.item(row_index)
            other_mod_folder = other_item.data(Qt.UserRole)
            if other_mod_folder == mod_folder:
                continue
            if other_item.checkState() != Qt.CheckState.Checked:
                continue
            common_files = current_mod_files & self._scan_mod_files(other_mod_folder)
            if not common_files:
                continue
            conflict_mods[other_item.text()] = {
                "folder": other_mod_folder,
                "files": sorted(common_files),
                "overwrites": row_index > current_mod_index,
            }
            if row_index < current_mod_index:
                other_item.setBackground(QColor("#9E4D4D"))
            else:
                other_item.setBackground(QColor("#65A665"))

        self.mod_selected.emit(
            selected_item.text(),
            mod_folder,
            conflict_mods,
        )

    _CONFLICT_EXTS = {".png", ".anm2", ".wav", ".lua"}

    def _scan_mod_files(self, mod_folder_name: str) -> set:
        cached_files = self._mod_files_cache.get(mod_folder_name)
        if cached_files is not None:
            return cached_files
        conflict_files = set()
        full_mod_path = os.path.join(config.mods_path, mod_folder_name)
        try:
            for walk_root, walk_dirs, file_names in os.walk(full_mod_path):
                walk_dirs[:] = [
                    directory
                    for directory in walk_dirs
                    if directory not in config.ignored_items
                ]
                for file_name in file_names:
                    if file_name in config.ignored_items:
                        continue
                    file_extension = os.path.splitext(file_name)[1].lower()
                    if file_extension not in self._CONFLICT_EXTS:
                        continue
                    relative_path = os.path.relpath(
                        os.path.join(walk_root, file_name), full_mod_path
                    )
                    if "/" in relative_path or "\\" in relative_path:
                        conflict_files.add(relative_path)
        except OSError as exc:
            self.log_message.emit(
                f"Failed to scan mod files for {mod_folder_name}: {exc}", "warning"
            )
        self._mod_files_cache[mod_folder_name] = conflict_files
        return conflict_files

    def _on_item_changed(self, list_item) -> None:
        if self._populating or self._updating_conflicts:
            return
        mod_folder = list_item.data(Qt.UserRole)
        if not mod_folder or list_item.data(SEPARATOR_ROLE):
            return

        current_state = list_item.checkState()
        if current_state == list_item.data(PREV_CHECK_ROLE):
            return

        list_item.setData(current_state, PREV_CHECK_ROLE)
        self.pending_toggles[mod_folder] = current_state
        if current_state != Qt.CheckState.Checked:
            list_item.setForeground(QColor(config.disabled_mod_color))
        else:
            list_item.setData(None, Qt.ItemDataRole.ForegroundRole)
        self._update_conflict_indicators()

        selected_indexes = self.listView.selectedIndexes()
        if selected_indexes:
            selected_item = self.model.itemFromIndex(selected_indexes[0])
            if not selected_item.data(SEPARATOR_ROLE):
                for row_index in range(self.model.rowCount()):
                    item = self.model.item(row_index)
                    if item.data(SEPARATOR_ROLE):
                        item.setBackground(QColor(item.data(SEPARATOR_ROLE)["color"]))
                    else:
                        item.setBackground(QBrush())
                        if item.checkState() != Qt.CheckState.Checked:
                            item.setForeground(QColor(config.disabled_mod_color))
                        elif item.data(OVERWRITTEN_ROLE):
                            item.setForeground(QColor(config.disabled_mod_color))
                            font = item.font()
                            font.setItalic(True)
                            item.setFont(font)
                        else:
                            item.setData(None, Qt.ItemDataRole.ForegroundRole)

                self._refresh_selection_conflicts(selected_item)

    def apply_mod_order(self) -> None:
        self.log_message.emit("Applying sort order...", "info")
        sort_index = 1
        ordered_folders = []
        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            mod_folder = list_item.data(Qt.UserRole)
            ordered_folders.append(mod_folder)
            if list_item.data(SEPARATOR_ROLE):
                continue
            mod_name = list_item.text()
            if sorted_pattern.match(mod_name):
                new_name = f"{sort_index:03} {mod_name[4:]}"
            else:
                new_name = f"{sort_index:03} {mod_name}"
            try:
                metadata_tree = ET.parse(
                    f"{config.mods_path}/{mod_folder}/metadata.xml"
                )
                xml_root = metadata_tree.getroot()
                xml_root.find("name").text = new_name
                metadata_tree.write(
                    f"{config.mods_path}/{mod_folder}/metadata.xml",
                    encoding="utf-8",
                    xml_declaration=True,
                )
                sort_index += 1
            except Exception as exception:
                self.log_message.emit(f"Writing {mod_folder}: {exception}", "error")
        for folder_name, toggle_state in self.pending_toggles.items():
            disable_file_path = os.path.join(
                config.mods_path, folder_name, "disable.it"
            )
            if toggle_state == Qt.CheckState.Unchecked:
                try:
                    open(disable_file_path, "a").close()
                except OSError as exception:
                    self.log_message.emit(
                        f"Disabling {folder_name}: {exception}", "error"
                    )
            else:
                try:
                    os.remove(disable_file_path)
                except FileNotFoundError:
                    pass
                except OSError as exception:
                    self.log_message.emit(
                        f"Enabling {folder_name}: {exception}", "error"
                    )
        self.pending_toggles.clear()
        sorter.save_last_order(ordered_folders)
        self.log_message.emit(f"Applied order for {sort_index - 1} mods", "info")
        self.load_mod_list()

    def restore_last_order(self) -> None:
        folder_order = sorter.load_last_order()
        if not folder_order:
            self.log_message.emit("No saved order to restore", "info")
            return
        self.log_message.emit("Restoring last saved order...", "info")
        sort_index = 1
        for mod_folder in folder_order:
            if mod_folder.endswith(SEPARATOR_SUFFIX):
                continue
            xml_path = os.path.join(config.mods_path, mod_folder, "metadata.xml")
            if not os.path.exists(xml_path):
                self.log_message.emit(
                    f"{mod_folder} no longer exists, skipping", "warning"
                )
                continue
            metadata_tree = ET.parse(xml_path)
            xml_root = metadata_tree.getroot()
            mod_name = xml_root.find("name").text
            if sorted_pattern.match(mod_name):
                mod_name = mod_name[4:]
            xml_root.find("name").text = f"{sort_index:03} {mod_name}"
            metadata_tree.write(xml_path, encoding="utf-8", xml_declaration=True)
            sort_index += 1
        self.log_message.emit(f"Restored order for {sort_index - 1} mods", "info")
        self.load_mod_list()

    def auto_sort_mods(self) -> None:
        self.log_message.emit("Running auto-sort...", "info")
        mod_data_list = []
        separators = []
        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            separator_data = list_item.data(SEPARATOR_ROLE)
            if separator_data:
                separators.append(
                    {
                        "name": list_item.text(),
                        "folder": list_item.data(Qt.UserRole),
                        "color": separator_data["color"],
                        "index": len(mod_data_list),
                    }
                )
            else:
                mod_data_list.append(
                    {
                        "name": list_item.text(),
                        "folder": list_item.data(Qt.UserRole),
                        "checked": list_item.checkState(),
                    }
                )

        auto_sorted_mods = sorter.auto_sort(
            [[mod["name"], mod["folder"]] for mod in mod_data_list],
            config.mods_path,
        )

        self._populating = True
        self.model.clear()
        self._mod_files_cache.clear()

        ordered_list = list(auto_sorted_mods)
        for separator_entry in separators:
            insert_position = min(separator_entry["index"], len(ordered_list))
            ordered_list.insert(
                insert_position, (separator_entry["name"], separator_entry["folder"])
            )

        mod_data_lookup = {mod["folder"]: mod for mod in mod_data_list}
        separator_lookup = {sep["folder"]: sep for sep in separators}
        for entry_name, entry_folder in ordered_list:
            list_item = self._make_list_item()
            list_item.setText(entry_name)
            list_item.setData(entry_folder, Qt.UserRole)
            if entry_folder in separator_lookup:
                separator_entry = separator_lookup[entry_folder]
                list_item.setData(
                    {"name": entry_name, "color": separator_entry["color"]},
                    SEPARATOR_ROLE,
                )
                list_item.setBackground(QColor(separator_entry["color"]))
                list_item.setTextAlignment(Qt.AlignCenter)
            else:
                mod_info = mod_data_lookup.get(entry_folder, {})
                list_item.setCheckable(True)
                list_item.setCheckState(mod_info.get("checked", Qt.Checked))
            self.model.appendRow(list_item)

        config.loaded_mods = [
            [entry_name, entry_folder]
            for entry_name, entry_folder in ordered_list
            if entry_folder not in separator_lookup
        ]
        self._populating = False
        self.log_message.emit(
            f"Auto-sort complete ({len(config.loaded_mods)} mods)", "info"
        )
        self._update_conflict_indicators()
        self.mods_loaded.emit()

    def _on_item_double_clicked(self, index) -> None:
        list_item = self.model.itemFromIndex(index)
        if list_item.data(SEPARATOR_ROLE):
            self._edit_separator(list_item)
            return
        ctrl_held = QApplication.keyboardModifiers() & Qt.ControlModifier
        if ctrl_held:
            mod_folder = list_item.data(Qt.UserRole)
            if not mod_folder:
                return
            folder_path = os.path.join(config.mods_path, mod_folder)
            if not os.path.isdir(folder_path):
                self.log_message.emit(
                    f"Folder does not exist: {folder_path}", "warning"
                )
                return
            if not open_path(folder_path):
                self.log_message.emit(f"Failed to open folder: {folder_path}", "error")

    def _edit_separator(self, list_item) -> None:
        separator_data = list_item.data(SEPARATOR_ROLE)
        old_separator_folder = list_item.data(Qt.UserRole)
        dialog = SeparatorDialog(
            "Edit Separator",
            name=separator_data["name"],
            color=separator_data["color"],
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        new_separator_name = dialog.result_name
        new_separator_color = dialog.result_color
        if not new_separator_name:
            return
        new_separator_folder = f"{new_separator_name}{SEPARATOR_SUFFIX}"
        if old_separator_folder != new_separator_folder:
            try:
                os.rename(
                    os.path.join(config.mods_path, old_separator_folder),
                    os.path.join(config.mods_path, new_separator_folder),
                )
            except OSError as exc:
                self.log_message.emit(
                    f"Failed to rename separator folder: {exc}", "error"
                )
                return
        separator_xml_path = os.path.join(
            config.mods_path, new_separator_folder, "separator.xml"
        )
        xml_root = ET.Element("separator")
        ET.SubElement(xml_root, "name").text = new_separator_name
        ET.SubElement(xml_root, "color").text = new_separator_color
        xml_tree = ET.ElementTree(xml_root)
        xml_tree.write(separator_xml_path, encoding="utf-8", xml_declaration=True)
        self.log_message.emit(f"Updated separator '{new_separator_name}'", "info")
        self._save_current_order()
        self.load_mod_list()

    def _on_context_menu(self, position) -> None:
        from PySide6.QtWidgets import QDialog

        index = self.listView.indexAt(position)
        if not index or not index.isValid():
            return
        list_item = self.model.itemFromIndex(index)
        if not list_item.data(SEPARATOR_ROLE):
            return
        context_menu = QMenu(self)
        context_menu.setStyleSheet("QMenu { border: 1px solid palette(mid); }")
        context_menu.addAction("Edit", lambda: self._edit_separator(list_item))
        context_menu.addAction("Delete", lambda: self._delete_separator(list_item))
        context_menu.exec(self.listView.viewport().mapToGlobal(position))

    def _delete_separator(self, list_item) -> None:
        import shutil

        separator_folder = list_item.data(Qt.UserRole)
        folder_path = os.path.join(config.mods_path, separator_folder)
        try:
            shutil.rmtree(folder_path)
            self.log_message.emit(f"Deleted separator '{list_item.text()}'", "info")
            self._save_current_order()
            self.load_mod_list()
        except OSError as exception:
            self.log_message.emit(f"Deleting separator: {exception}", "error")

    def _create_separator(self) -> None:
        from PySide6.QtWidgets import QDialog

        dialog = SeparatorDialog("Create Separator", parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        separator_name = dialog.result_name
        separator_color = dialog.result_color
        if not separator_name:
            return
        separator_folder = f"{separator_name}{SEPARATOR_SUFFIX}"
        try:
            os.makedirs(os.path.join(config.mods_path, separator_folder), exist_ok=True)
            separator_xml_path = os.path.join(
                config.mods_path, separator_folder, "separator.xml"
            )
            xml_root = ET.Element("separator")
            ET.SubElement(xml_root, "name").text = separator_name
            ET.SubElement(xml_root, "color").text = separator_color
            xml_tree = ET.ElementTree(xml_root)
            xml_tree.write(separator_xml_path, encoding="utf-8", xml_declaration=True)
            self.log_message.emit(f"Created separator '{separator_name}'", "info")
        except OSError as exception:
            self.log_message.emit(f"Creating separator: {exception}", "error")
        self._save_current_order()
        self.load_mod_list()

    def _export_modlist(self) -> None:
        from PySide6.QtWidgets import QDialog, QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Modlist", "", "CSV files (*.csv);;All files (*)"
        )
        if not file_path:
            return
        items = []
        for row_index in range(self.model.rowCount()):
            list_item = self.model.item(row_index)
            if list_item.data(SEPARATOR_ROLE):
                continue
            items.append((list_item.data(Qt.UserRole), list_item.text()))
        try:
            count = export_modlist_csv(file_path, items)
            self.log_message.emit(f"Exported {count} mods to {file_path}", "info")
        except OSError as exception:
            self.log_message.emit(f"Exporting modlist: {exception}", "error")

    def _import_modlist(self) -> None:
        from PySide6.QtWidgets import QDialog, QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Modlist", "", "CSV files (*.csv);;All files (*)"
        )
        if not file_path:
            return
        try:
            known_mods = {}
            for row_index in range(self.model.rowCount()):
                list_item = self.model.item(row_index)
                if list_item.data(SEPARATOR_ROLE):
                    continue
                folder = list_item.data(Qt.UserRole)
                known_mods[folder] = (list_item.text(), folder)

            ordered_folders = import_modlist_csv(file_path, known_mods)
            if ordered_folders:
                sorter.save_last_order(ordered_folders)
                self.log_message.emit(f"Imported modlist from {file_path}", "info")
                self.load_mod_list()
        except Exception as exception:
            self.log_message.emit(f"Importing modlist: {exception}", "error")

    def _save_current_order(self) -> None:
        ordered_folders = []
        for row_index in range(self.model.rowCount()):
            ordered_folders.append(self.model.item(row_index).data(Qt.UserRole))
        sorter.save_last_order(ordered_folders)

    def update_accent_color(self, color: str) -> None:
        self._accent_color = color
        self.listView.setStyleSheet(
            f"QListView::item:selected {{ background-color: {color}; }}"
        )
        self.applyOrder.setStyleSheet(f"background-color : {color}")
