"""Filesystem-based theme loader.

Themes live in ``{config_dir}/themes/``.  Each immediate subdirectory is one
theme and may contain any combination of:

* ``colors.toml``       – palette overrides (used for both light & dark)
* ``colors-light.toml`` – light-mode overrides (takes precedence in light)
* ``colors-dark.toml``  – dark-mode overrides  (takes precedence in dark)
* ``style.qss``         – Qt stylesheet additions

Missing files are silently skipped.  The built-in **System** theme performs
no overrides and is always available.

This module is a **pure data loader** — it never calls ``setStyleSheet`` or
``setPalette`` directly.  The caller (``window.py``) applies the loaded
palette and stylesheet through its own safe repaint mechanism.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from ..core import paths

THEMES_DIR: Path = Path(paths.config_dir) / "themes"

_SYSTEM_THEME_NAME = "System"

# TOML key  →  QPalette.ColorRole
_PALETTE_MAP: dict[str, QPalette.ColorRole] = {
    "Window":          QPalette.ColorRole.Window,
    "WindowText":      QPalette.ColorRole.WindowText,
    "Base":            QPalette.ColorRole.Base,
    "AlternateBase":   QPalette.ColorRole.AlternateBase,
    "Button":          QPalette.ColorRole.Button,
    "ButtonText":      QPalette.ColorRole.ButtonText,
    "Text":            QPalette.ColorRole.Text,
    "BrightText":      QPalette.ColorRole.BrightText,
    "Link":            QPalette.ColorRole.Link,
    "LinkVisited":     QPalette.ColorRole.LinkVisited,
    "Highlight":       QPalette.ColorRole.Highlight,
    "HighlightedText": QPalette.ColorRole.HighlightedText,
    "Mid":             QPalette.ColorRole.Mid,
    "Dark":            QPalette.ColorRole.Dark,
    "Shadow":          QPalette.ColorRole.Shadow,
    "PlaceholderText": QPalette.ColorRole.PlaceholderText,
}

# Qt 6.6+ added the Accent role; skip gracefully on older versions.
try:
    _PALETTE_MAP["Accent"] = QPalette.ColorRole.Accent  # type: ignore[attr-defined]
except AttributeError:
    pass


# -- color-scheme detection ---------------------------------------------

def detect_color_scheme() -> str:
    """Return ``"light"`` or ``"dark"`` based on the current system hint."""
    app = QApplication.instance()
    if app is None:
        return "dark"

    hints = app.styleHints()
    scheme = hints.colorScheme()
    if scheme == Qt.ColorScheme.Light:
        return "light"
    if scheme == Qt.ColorScheme.Dark:
        return "dark"

    # fallback: luminance of Window role
    win = app.palette().color(QPalette.ColorRole.Window)
    luma = 0.299 * win.redF() + 0.587 * win.greenF() + 0.114 * win.blueF()
    return "light" if luma > 0.5 else "dark"


# -- theme data ---------------------------------------------------------

@dataclass
class Theme:
    """A discovered theme on disk."""

    name: str
    directory: Path
    has_colors: bool = field(init=False)
    has_qss: bool = field(init=False)
    has_light: bool = field(init=False)
    has_dark: bool = field(init=False)

    def __post_init__(self) -> None:
        self.has_colors = (self.directory / "colors.toml").is_file()
        self.has_qss = (self.directory / "style.qss").is_file()
        self.has_light = (self.directory / "colors-light.toml").is_file()
        self.has_dark = (self.directory / "colors-dark.toml").is_file()


def _ensure_dir() -> None:
    THEMES_DIR.mkdir(parents=True, exist_ok=True)


def discover_themes() -> list[Theme]:
    """Return all available themes, including the built-in System theme."""
    _ensure_dir()
    themes: list[Theme] = [Theme(_SYSTEM_THEME_NAME, Path())]
    for entry in sorted(THEMES_DIR.iterdir()):
        if entry.is_dir() and not entry.name.startswith("."):
            themes.append(Theme(entry.name, entry))
    return themes


def get_theme(name: str) -> Optional[Theme]:
    """Look up a single theme by *name* (case-sensitive)."""
    for t in discover_themes():
        if t.name == name:
            return t
    return None


def _read_toml(path: Path) -> dict:
    """Safely read a TOML file, returning ``{}`` on any error."""
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_colors(theme: Theme, scheme: Optional[str] = None) -> dict:
    """Read colour overrides for *theme*.

    Resolution order (per ``scheme``):
      1. ``colors-{scheme}.toml``  (e.g. ``colors-dark.toml``)
      2. ``colors.toml``          (fallback for both modes)

    If *scheme* is ``None`` the current system hint is used.
    Returns an empty dict when no file is found.
    """
    if not theme.has_colors and not theme.has_light and not theme.has_dark:
        return {}

    if scheme is None:
        scheme = detect_color_scheme()

    variant = theme.directory / f"colors-{scheme}.toml"
    if variant.is_file():
        return _read_toml(variant)

    return _read_toml(theme.directory / "colors.toml")


def load_qss(theme: Theme) -> str:
    """Read ``style.qss`` and return its contents.

    Returns an empty string when the file is missing.
    """
    if not theme.has_qss:
        return ""
    try:
        return (theme.directory / "style.qss").read_text(encoding="utf-8")
    except OSError:
        return ""


# -- palette building (pure data, no Qt side-effects) ------------------

def build_palette(
    theme: Theme,
    scheme: Optional[str] = None,
) -> Optional[QPalette]:
    """Build a QPalette from *theme*'s colour file.

    Returns ``None`` when the theme has no palette section.
    The caller must call ``app.setPalette()`` at the appropriate time.
    """
    data = load_colors(theme, scheme=scheme)
    palette_section = data.get("palette", {})
    if not isinstance(palette_section, dict) or not palette_section:
        return None

    app = QApplication.instance()
    if app is None:
        return None

    pal = app.palette()  # start from native
    for key, role in _PALETTE_MAP.items():
        raw = palette_section.get(key)
        if isinstance(raw, dict):
            continue
        if raw is None:
            continue
        try:
            c = QColor(str(raw))
        except Exception:
            continue
        if c.isValid():
            pal.setColor(role, c)
    return pal


def load_theme_colors(theme: Theme, scheme: Optional[str] = None) -> dict:
    """Return the ``[colors]`` section (app config overrides) from *theme*."""
    data = load_colors(theme, scheme=scheme)
    colors = data.get("colors", {})
    return colors if isinstance(colors, dict) else {}
