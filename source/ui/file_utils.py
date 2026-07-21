"""File system utilities: opening paths and URLs."""

from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def _open_with_system(target: str, is_file: bool) -> bool:
    if sys.platform.startswith("linux"):
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("LD_LIBRARY_PATH", "APPDIR", "APPIMAGE")
        }
        proc = subprocess.Popen(
            ["xdg-open", target],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.communicate(timeout=5)
        return proc.returncode == 0
    elif sys.platform == "darwin":
        proc = subprocess.Popen(
            ["open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        proc.communicate(timeout=5)
        return proc.returncode == 0
    else:
        url = QUrl.fromLocalFile(target) if is_file else QUrl(target)
        return QDesktopServices.openUrl(url)


def open_path(path: str) -> bool:
    return _open_with_system(path, is_file=True)


def open_url(url: str) -> bool:
    return _open_with_system(url, is_file=False)
