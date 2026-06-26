"""Configuration management: load, save, and provide defaults."""
import os
import threading
import time
from typing import Optional

import toml
from PySide6.QtCore import QSettings

from . import paths, sorter

_save_lock = threading.Lock()
_last_save: float = 0.0
SAVE_DEBOUNCE: float = 2.0

mods_path: str = ""
backup_enabled: bool = False
backup_path: Optional[str] = None
theme: str = "fusion"
accent_color: str = "#3daee9"
disabled_mod_color: str = "#808080"
download_icons: bool = False
animate_icons: bool = True
preview_images: bool = True
animate_anm2_preview: bool = True
loaded_mods: list = []
workshop_timestamps: list[float] = []
dead_workshop_ids: list[str] = []
log_level: str = "info"
date_format: str = ""
ignored_items: list[str] = [
    ".git",
    "__pycache__",
    "metadata.xml",
    "disable.it",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    ".Trashes",
    ".Spotlight-V100",
    "$RECYCLE.BIN",
    ".directory",
    "~",
]


def get_settings() -> QSettings:
    return QSettings("PetricaT", "IsaacMM")


def load() -> None:
    global mods_path, backup_enabled, backup_path, theme, accent_color, disabled_mod_color, animate_icons, preview_images
    global download_icons, workshop_timestamps, dead_workshop_ids, log_level, date_format, ignored_items, animate_anm2_preview
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
        animate_anm2_preview = settings_section.get("animate_anm2_preview", True)
        preview_images = settings_section.get("preview_images", True)
        download_icons = settings_section.get("download_icons", False)
        log_level = settings_section.get("log_level", "info")
        date_format = settings_section.get("date_format", "")
        ignored_items = settings_section.get(
            "ignored_items",
            [
                ".git",
                "__pycache__",
                "metadata.xml",
                "disable.it",
                ".DS_Store",
                "Thumbs.db",
                "desktop.ini",
                ".Trashes",
                ".Spotlight-V100",
                "$RECYCLE.BIN",
                ".directory",
                "~",
            ],
        )
        theme_section = config_data.get("theme", {})
        accent_color = theme_section.get("accent", "#3daee9")
        disabled_mod_color = theme_section.get("disabled_mod", "#808080")
        workshop_section = config_data.get("workshop", {})
        workshop_timestamps = workshop_section.get("timestamps", [])
        dead_workshop_ids = settings_section.get("dead_workshop_ids", [])
    except FileNotFoundError:
        os.makedirs(paths.config_dir, exist_ok=True)
        detected_path = paths.find_isaac_mods_folder()
        mods_path = detected_path or ""
        sorter.fetch_initial()
        save()


def flush() -> None:
    global _last_save
    _last_save = 0.0
    _do_save()


def save() -> None:
    global _last_save
    now = time.time()
    if now - _last_save < SAVE_DEBOUNCE:
        return
    _last_save = now
    _do_save()


def _do_save() -> None:
    with _save_lock:
        config_data = {
            "paths": {"mods": mods_path},
            "settings": {
                "backup_enabled": backup_enabled,
                "backup_path": backup_path,
                "theme": theme,
                "animate_icons": animate_icons,
                "animate_anm2_preview": animate_anm2_preview,
                "preview_images": preview_images,
                "download_icons": download_icons,
                "log_level": log_level,
                "date_format": date_format,
                "dead_workshop_ids": dead_workshop_ids,
                "ignored_items": ignored_items,
            },
            "theme": {
                "accent": accent_color,
                "disabled_mod": disabled_mod_color,
            },
            "workshop": {
                "timestamps": workshop_timestamps,
            },
        }
        os.makedirs(paths.config_dir, exist_ok=True)
        with open(f"{paths.config_dir}/config.toml", "w") as config_file:
            toml.dump(config_data, config_file)
