import os
from typing import Optional

import toml
from PySide6.QtCore import QSettings

from . import paths, sorter

mods_path: str = ""
backup_enabled: bool = False
backup_path: Optional[str] = None
theme: str = "fusion"
accent_color: str = "#3daee9"
disabled_mod_color: str = "#777777"
overwritten_mod_color: str = "#555555"
download_icons: bool = False
animate_icons: bool = True
preview_images: bool = True
loaded_mods: list = []
workshop_timestamps: list[float] = []
dead_workshop_ids: list[str] = []
log_level: str = "info"

IGNORED_FILES: set[str] = {".DS_Store", "Thumbs.db", "metadata.xml", "disable.it"}
IGNORED_DIRS: set[str] = {".git", "__pycache__"}


def get_settings() -> QSettings:
    return QSettings("PetricaT", "IsaacMM")


def load() -> None:
    global mods_path, backup_enabled, backup_path, theme, accent_color, animate_icons, preview_images
    global download_icons, workshop_timestamps, dead_workshop_ids, log_level
    global disabled_mod_color, overwritten_mod_color
    try:
        config_data = toml.load(f"{paths.config_dir}/config.toml")
        mods_path = config_data["paths"]["mods"]
        if mods_path == "":
            from . import logger
            logger.log("warning", "Mods path malformed, check if path is correct")
        settings_section = config_data.get("settings", {})
        backup_enabled = settings_section.get("backup_enabled", False)
        backup_path = settings_section.get("backup_path") or None
        theme = settings_section.get("theme", "fusion")
        animate_icons = settings_section.get("animate_icons", True)
        preview_images = settings_section.get("preview_images", True)
        download_icons = settings_section.get("download_icons", False)
        log_level = settings_section.get("log_level", "info")
        theme_section = config_data.get("theme", {})
        accent_color = theme_section.get("accent", "#3daee9")
        workshop_section = config_data.get("workshop", {})
        workshop_timestamps = workshop_section.get("timestamps", [])
        dead_workshop_ids = settings_section.get("dead_workshop_ids", [])
        colors_section = config_data.get("colors", {})
        disabled_mod_color = colors_section.get("disabled_mod", "#777777")
        overwritten_mod_color = colors_section.get("overwritten_mod", "#7E7E7E")
    except FileNotFoundError:
        _create_default()


def _create_default() -> None:
    global mods_path
    os.makedirs(paths.config_dir, exist_ok=True)
    detected_path = paths.find_isaac_mods_folder()
    mods_path = detected_path or ""
    sorter.fetch_initial()
    config_data = {
        "paths": {"mods": mods_path},
        "settings": {"remove_marks": False, "backup_enabled": False},
    }
    with open(f"{paths.config_dir}/config.toml", "w") as config_file:
        toml.dump(config_data, config_file)


def save() -> None:
    config_data = {
        "paths": {"mods": mods_path},
        "settings": {
            "backup_enabled": backup_enabled,
            "backup_path": backup_path,
            "theme": theme,
            "animate_icons": animate_icons,
            "preview_images": preview_images,
            "download_icons": download_icons,
            "log_level": log_level,
            "dead_workshop_ids": dead_workshop_ids,
        },
        "theme": {
            "accent": accent_color,
        },
        "workshop": {
            "timestamps": workshop_timestamps,
        },
        "colors": {
            "disabled_mod": disabled_mod_color,
            "overwritten_mod": overwritten_mod_color,
        },
    }
    os.makedirs(paths.config_dir, exist_ok=True)
    with open(f"{paths.config_dir}/config.toml", "w") as config_file:
        toml.dump(config_data, config_file)
