import base64
import os
from typing import Optional

import toml

from . import paths, sorter

mods_path: str = ""
backup_enabled: bool = False
backup_path: Optional[str] = None
splitter_state: Optional[str] = None
column_state: Optional[str] = None
window_geometry: Optional[str] = None
loaded_mods: list = []


def load() -> None:
    global mods_path, backup_enabled, backup_path, splitter_state, column_state, window_geometry
    try:
        config_data = toml.load(f"{paths.appdata}/config.toml")
        mods_path = config_data["paths"]["mods"]
        if mods_path == "":
            print("Mods path malformed, check if path is correct")
        settings_section = config_data.get("settings", {})
        backup_enabled = settings_section.get("backup_enabled", False)
        backup_path = settings_section.get("backup_path") or None
        layout_section = config_data.get("layout", {})
        splitter_state = layout_section.get("splitter_state")
        column_state = layout_section.get("column_state")
        window_geometry = layout_section.get("window_geometry")
    except FileNotFoundError:
        _create_default()


def _create_default() -> None:
    global mods_path
    os.makedirs(paths.appdata, exist_ok=True)
    detected_path = paths.find_isaac_mods_folder()
    mods_path = detected_path or ""
    sorter.fetch_initial()
    config_data = {
        "paths": {"mods": mods_path},
        "settings": {"remove_marks": False, "backup_enabled": False},
    }
    with open(f"{paths.appdata}/config.toml", "w") as config_file:
        toml.dump(config_data, config_file)


def encode_state(state_data: bytes) -> Optional[str]:
    return base64.b85encode(state_data).decode("ascii") if state_data else None


def decode_state(state_string: str) -> Optional[bytes]:
    return base64.b85decode(state_string.encode("ascii")) if state_string else None


def save() -> None:
    config_data = {
        "paths": {"mods": mods_path},
        "settings": {
            "backup_enabled": backup_enabled,
            "backup_path": backup_path,
        },
        "layout": {
            "splitter_state": splitter_state,
            "column_state": column_state,
            "window_geometry": window_geometry,
        },
    }
    os.makedirs(paths.appdata, exist_ok=True)
    with open(f"{paths.appdata}/config.toml", "w") as config_file:
        toml.dump(config_data, config_file)
