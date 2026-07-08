"""Theme loading and saving."""

from __future__ import annotations

import os
from typing import Dict, List

import toml

from . import paths

THEMES_DIR: str = os.path.join(paths.config_dir, "themes")


def discover_themes() -> List[Dict[str, str]]:
    os.makedirs(THEMES_DIR, exist_ok=True)
    themes: List[Dict[str, str]] = []
    for entry in sorted(os.listdir(THEMES_DIR)):
        if not entry.endswith(".toml"):
            continue
        file_path = os.path.join(THEMES_DIR, entry)
        try:
            data = toml.load(file_path)
            info = data.get("info", {})
            theme = data.get("theme", {})
            name = info.get("name", entry[:-5])
            accent = theme.get("accent", "")
            if accent:
                themes.append(
                    {
                        "name": name,
                        "accent": accent,
                        "file": entry,
                    }
                )
        except Exception:
            pass
    return themes
