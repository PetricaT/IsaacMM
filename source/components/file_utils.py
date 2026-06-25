"""File system utilities: opening paths and URLs."""
import os
import subprocess
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_path(path: str) -> bool:
    if sys.platform.startswith("linux"):
        env = os.environ.copy()
        env.pop("LD_LIBRARY_PATH", None)
        env.pop("APPDIR", None)
        env.pop("APPIMAGE", None)
        proc = subprocess.Popen(
            ["xdg-open", path],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.communicate(timeout=5)
        if proc.returncode != 0:
            return False
        return True
    elif sys.platform == "darwin":
        proc = subprocess.Popen(
            ["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        proc.communicate(timeout=5)
        return proc.returncode == 0
    else:
        return QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def open_url(url: str) -> bool:
    if sys.platform.startswith("linux"):
        env = os.environ.copy()
        env.pop("LD_LIBRARY_PATH", None)
        env.pop("APPDIR", None)
        env.pop("APPIMAGE", None)
        proc = subprocess.Popen(
            ["xdg-open", url],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.communicate(timeout=5)
        if proc.returncode != 0:
            return False
        return True
    elif sys.platform == "darwin":
        proc = subprocess.Popen(
            ["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        proc.communicate(timeout=5)
        return proc.returncode == 0
    else:
        return QDesktopServices.openUrl(QUrl(url))
