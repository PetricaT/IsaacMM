"""Configuration management: load, save, and provide defaults."""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import toml
from PySide6.QtCore import QSettings

from . import paths, sorter

_save_lock = threading.Lock()
_last_save: float = 0.0
SAVE_DEBOUNCE: float = 2.0


@dataclass
class _Config:
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
    loaded_mods: list = field(default_factory=list)
    workshop_timestamps: list = field(default_factory=list)
    dead_workshop_ids: list = field(default_factory=list)
    log_level: str = "info"
    date_format: str = ""
    ignored_items: list = field(default_factory=lambda: [
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
    ])
    controller_enabled: bool = True
    controller_deadzone: int = 8000
    controller_simple_icons: bool = False
    _native_style: str = ""


_cfg = _Config()


def __getattr__(name: str):
    return getattr(_cfg, name)


def __setattr__(name: str, value) -> None:
    setattr(_cfg, name, value)


def get_settings() -> QSettings:
    return QSettings("PetricaT", "IsaacMM")


def load() -> None:
    try:
        config_data = toml.load(f"{paths.config_dir}/config.toml")
        _cfg.mods_path = config_data["paths"]["mods"]
        if _cfg.mods_path == "":
            from . import logger

            logger.log("warning", "Mods path malformed, check if path is correct")
        settings_section = config_data.get("settings", {})
        _cfg.backup_enabled = settings_section.get("backup_enabled", False)
        _cfg.backup_path = settings_section.get("backup_path") or None
        _cfg.theme = settings_section.get("theme", "fusion")
        _cfg.animate_icons = settings_section.get("animate_icons", True)
        _cfg.animate_anm2_preview = settings_section.get("animate_anm2_preview", True)
        _cfg.preview_images = settings_section.get("preview_images", True)
        _cfg.download_icons = settings_section.get("download_icons", False)
        _cfg.log_level = settings_section.get("log_level", "info")
        _cfg.date_format = settings_section.get("date_format", "")
        _cfg.ignored_items = settings_section.get(
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
        _cfg.controller_enabled = settings_section.get("controller_enabled", True)
        _cfg.controller_deadzone = settings_section.get("controller_deadzone", 8000)
        _cfg.controller_simple_icons = settings_section.get("controller_simple_icons", False)
        theme_section = config_data.get("theme", {})
        _cfg.accent_color = theme_section.get("accent", "#3daee9")
        _cfg.disabled_mod_color = theme_section.get("disabled_mod", "#808080")
        workshop_section = config_data.get("workshop", {})
        _cfg.workshop_timestamps = workshop_section.get("timestamps", [])
        _cfg.dead_workshop_ids = settings_section.get("dead_workshop_ids", [])
    except FileNotFoundError:
        os.makedirs(paths.config_dir, exist_ok=True)
        detected_path = paths.find_isaac_mods_folder()
        _cfg.mods_path = detected_path or ""
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
            "paths": {"mods": _cfg.mods_path},
            "settings": {
                "backup_enabled": _cfg.backup_enabled,
                "backup_path": _cfg.backup_path,
                "theme": _cfg.theme,
                "animate_icons": _cfg.animate_icons,
                "animate_anm2_preview": _cfg.animate_anm2_preview,
                "preview_images": _cfg.preview_images,
                "download_icons": _cfg.download_icons,
                "log_level": _cfg.log_level,
                "date_format": _cfg.date_format,
                "dead_workshop_ids": _cfg.dead_workshop_ids,
                "ignored_items": _cfg.ignored_items,
                "controller_enabled": _cfg.controller_enabled,
                "controller_deadzone": _cfg.controller_deadzone,
                "controller_simple_icons": _cfg.controller_simple_icons,
            },
            "theme": {
                "accent": _cfg.accent_color,
                "disabled_mod": _cfg.disabled_mod_color,
            },
            "workshop": {
                "timestamps": _cfg.workshop_timestamps,
            },
        }
        os.makedirs(paths.config_dir, exist_ok=True)
        with open(f"{paths.config_dir}/config.toml", "w") as config_file:
            toml.dump(config_data, config_file)
