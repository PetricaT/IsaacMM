"""Configuration management: load, save, and provide defaults."""

from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import toml
from PySide6.QtCore import QSettings

from . import database, paths
from ..mods import sorter

_save_lock = threading.Lock()
_last_save: float = 0.0
SAVE_DEBOUNCE: float = 2.0


@dataclass
class _Config:
    mods_path: str = ""
    backup_enabled: bool = False
    backup_path: Optional[str] = None
    theme: str = "native"
    active_theme: str = "System"
    accent_color: str = ""
    disabled_mod_color: str = ""
    win_color: str = "#65A665"
    lose_color: str = "#9E4D4D"
    download_icons: bool = False
    animate_icons: bool = True
    preview_images: bool = True
    animate_anm2_preview: bool = True
    loaded_mods: list = field(default_factory=list)
    log_level: str = "info"
    date_format: str = ""
    ignored_items: list = field(
        default_factory=lambda: [
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
    )
    controller_enabled: bool = True
    controller_deadzone: int = 8000
    controller_simple_icons: bool = False
    slim_db: bool = False
    notifications_enabled: bool = False
    use_system_icons: bool = True
    theme_preset: str = ""
    # Widget colors
    dpad_color: str = ""
    tag_bg: str = ""
    tag_fg: str = ""
    folder_label_color: str = ""
    icon_border_color: str = ""
    workshop_missing_color: str = "#FF4444"
    workshop_badge_current: str = "#55C755"
    workshop_badge_possible: str = "#FFA500"
    workshop_badge_outdated: str = "#FF4444"
    workshop_badge_default: str = ""

    check_updates_on_startup: bool = False
    include_prereleases: bool = False

    console_bg: str = ""
    console_fg: str = ""
    console_border: str = ""
    rate_bar_bg: str = ""
    log_info_color: str = ""
    log_warn_color: str = "#ffa500"
    log_error_color: str = "#ff4444"
    # Modlist colors
    separator_color: str = ""
    # Preview colors
    preview_border: str = ""
    preview_bg: str = ""
    _native_style: str = ""


_cfg = _Config()


def __getattr__(name: str):
    return getattr(_cfg, name)


def __setattr__(name: str, value) -> None:
    setattr(_cfg, name, value)


THEME_PRESETS: dict[str, dict[str, str]] = {
    "light": {
        "accent_color": "#3daee9",
        "disabled_mod_color": "#a0a0a0",
        "win_color": "#2d7d2d",
        "lose_color": "#b33b3b",
        "dpad_color": "#555555",
        "tag_bg": "#c9dde8",
        "tag_fg": "#111111",
        "folder_label_color": "#666666",
        "icon_border_color": "#a0a0a0",
        "workshop_missing_color": "#cc3333",
        "workshop_badge_current": "#3d9e3d",
        "workshop_badge_possible": "#cc8400",
        "workshop_badge_outdated": "#cc3333",
        "workshop_badge_default": "#333333",
        "console_bg": "#f5f5f5",
        "console_fg": "#1e1e1e",
        "console_border": "#cccccc",
        "rate_bar_bg": "#e8e8e8",
        "log_info_color": "#1e1e1e",
        "log_warn_color": "#cc8400",
        "log_error_color": "#cc3333",
        "separator_color": "#cccccc",
        "preview_border": "#cccccc",
        "preview_bg": "#ffffff",
    },
    "default": {
        "accent_color": "#3daee9",
        "disabled_mod_color": "#808080",
        "win_color": "#65A665",
        "lose_color": "#9E4D4D",
        "dpad_color": "#888888",
        "tag_bg": "#9BB7D4",
        "tag_fg": "#111111",
        "folder_label_color": "#808080",
        "icon_border_color": "#808080",
        "workshop_missing_color": "#FF4444",
        "workshop_badge_current": "#55C755",
        "workshop_badge_possible": "#FFA500",
        "workshop_badge_outdated": "#FF4444",
        "workshop_badge_default": "#ffffff",
        "console_bg": "#1e1e1e",
        "console_fg": "#d4d4d4",
        "console_border": "#333333",
        "rate_bar_bg": "#252526",
        "log_info_color": "#d4d4d4",
        "log_warn_color": "#ffa500",
        "log_error_color": "#ff4444",
        "separator_color": "#888888",
        "preview_border": "#888888",
        "preview_bg": "#ffffff",
    },
    "high_contrast": {
        "accent_color": "#000080",
        "disabled_mod_color": "#808080",
        "dpad_color": "#000000",
        "tag_bg": "#000080",
        "tag_fg": "#ffffff",
        "folder_label_color": "#000000",
        "icon_border_color": "#000000",
        "workshop_missing_color": "#CC0000",
        "workshop_badge_current": "#006600",
        "workshop_badge_possible": "#996600",
        "workshop_badge_outdated": "#CC0000",
        "workshop_badge_default": "#000000",
        "console_bg": "#ffffff",
        "console_fg": "#000000",
        "console_border": "#000000",
        "rate_bar_bg": "#f0f0f0",
        "log_info_color": "#000000",
        "log_warn_color": "#996600",
        "log_error_color": "#CC0000",
        "separator_color": "#000000",
        "preview_border": "#000000",
        "preview_bg": "#ffffff",
        "win_color": "#006600",
        "lose_color": "#CC0000",
    },
}


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
        _cfg.theme = settings_section.get("theme", "native")
        _cfg.active_theme = settings_section.get("active_theme", "System")
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
        _cfg.controller_simple_icons = settings_section.get(
            "controller_simple_icons", False
        )
        _cfg.notifications_enabled = settings_section.get(
            "notifications_enabled", False
        )
        _cfg.check_updates_on_startup = settings_section.get(
            "check_updates_on_startup", False
        )
        _cfg.include_prereleases = settings_section.get(
            "include_prereleases", False
        )
        theme_section = config_data.get("theme", {})
        _cfg.use_system_icons = theme_section.get("use_system_icons", True)
        _cfg.theme_preset = theme_section.get("theme_preset", "")
        _cfg.accent_color = theme_section.get("accent", "")
        _cfg.disabled_mod_color = theme_section.get("disabled_mod", "")
        _cfg.win_color = theme_section.get("win", "#65A665")
        _cfg.lose_color = theme_section.get("lose", "#9E4D4D")
        _cfg.dpad_color = theme_section.get("dpad", "")
        _cfg.tag_bg = theme_section.get("tag_bg", "")
        _cfg.tag_fg = theme_section.get("tag_fg", "")
        _cfg.folder_label_color = theme_section.get("folder_label", "")
        _cfg.icon_border_color = theme_section.get("icon_border", "")
        _cfg.workshop_missing_color = theme_section.get("workshop_missing", "#FF4444")
        _cfg.workshop_badge_current = theme_section.get("workshop_current", "#55C755")
        _cfg.workshop_badge_possible = theme_section.get("workshop_possible", "#FFA500")
        _cfg.workshop_badge_outdated = theme_section.get("workshop_outdated", "#FF4444")
        _cfg.workshop_badge_default = theme_section.get("workshop_default", "")
        _cfg.console_bg = theme_section.get("console_bg", "")
        _cfg.console_fg = theme_section.get("console_fg", "")
        _cfg.console_border = theme_section.get("console_border", "")
        _cfg.rate_bar_bg = theme_section.get("rate_bar_bg", "")
        _cfg.log_info_color = theme_section.get("log_info", "")
        _cfg.log_warn_color = theme_section.get("log_warn", "#ffa500")
        _cfg.log_error_color = theme_section.get("log_error", "#ff4444")
        _cfg.separator_color = theme_section.get("separator", "")
        _cfg.preview_border = theme_section.get("preview_border", "")
        _cfg.preview_bg = theme_section.get("preview_bg", "")
        database.init()
    except FileNotFoundError:
        os.makedirs(paths.config_dir, exist_ok=True)
        detected_path = paths.find_isaac_mods_folder()
        _cfg.mods_path = detected_path or ""
        sorter.fetch_initial()
        database.init()
        save()


def apply_preset(preset_name: str) -> None:
    _cfg.theme_preset = preset_name
    overrides = THEME_PRESETS.get(preset_name, {})
    for key, value in overrides.items():
        setattr(_cfg, key, value)


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


def _get_cfg(name: str):
    """Read a config value via the module-level accessor.
    This resolves both values set directly on _cfg (by load())
    and those set via config.xxx = value (which creates a module __dict__ entry)."""
    mod = sys.modules[__name__]
    return getattr(mod, name)


def _do_save() -> None:
    _v = _get_cfg
    with _save_lock:
        config_data = {
            "paths": {"mods": _v("mods_path")},
            "settings": {
                "backup_enabled": _v("backup_enabled"),
                "backup_path": _v("backup_path"),
                "theme": _v("theme"),
                "active_theme": _v("active_theme"),
                "animate_icons": _v("animate_icons"),
                "animate_anm2_preview": _v("animate_anm2_preview"),
                "preview_images": _v("preview_images"),
                "download_icons": _v("download_icons"),
                "log_level": _v("log_level"),
                "date_format": _v("date_format"),
                "ignored_items": _v("ignored_items"),
                "controller_enabled": _v("controller_enabled"),
                "controller_deadzone": _v("controller_deadzone"),
                "controller_simple_icons": _v("controller_simple_icons"),
                "notifications_enabled": _v("notifications_enabled"),
                "check_updates_on_startup": _v("check_updates_on_startup"),
                "include_prereleases": _v("include_prereleases"),
            },
            "theme": {
                "accent": _v("accent_color"),
                "disabled_mod": _v("disabled_mod_color"),
                "use_system_icons": _v("use_system_icons"),
                "theme_preset": _v("theme_preset"),
                "win": _v("win_color"),
                "lose": _v("lose_color"),
                "dpad": _v("dpad_color"),
                "tag_bg": _v("tag_bg"),
                "tag_fg": _v("tag_fg"),
                "folder_label": _v("folder_label_color"),
                "icon_border": _v("icon_border_color"),
                "workshop_missing": _v("workshop_missing_color"),
                "workshop_current": _v("workshop_badge_current"),
                "workshop_possible": _v("workshop_badge_possible"),
                "workshop_outdated": _v("workshop_badge_outdated"),
                "workshop_default": _v("workshop_badge_default"),
                "console_bg": _v("console_bg"),
                "console_fg": _v("console_fg"),
                "console_border": _v("console_border"),
                "rate_bar_bg": _v("rate_bar_bg"),
                "log_info": _v("log_info_color"),
                "log_warn": _v("log_warn_color"),
                "log_error": _v("log_error_color"),
                "separator": _v("separator_color"),
                "preview_border": _v("preview_border"),
                "preview_bg": _v("preview_bg"),
            },
        }
        os.makedirs(paths.config_dir, exist_ok=True)
        with open(f"{paths.config_dir}/config.toml", "w") as config_file:
            toml.dump(config_data, config_file)
