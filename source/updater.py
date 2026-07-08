"""Self-update: GitHub release check, download, and AppImage replacement."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from typing import Callable, Optional
from urllib.request import Request, urlopen

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from . import config, paths

REPO = "PetricaT/IsaacMM"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases"


# ── helpers (thread-safe) ──────────────────────────────────────────────


def _fetch_json(url: str, timeout: int = 10) -> Optional[dict]:
    try:
        req = Request(
            url,
            headers={
                "User-Agent": "IsaacMM/1.0",
                "Accept": "application/json",
            },
        )
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _parse_version(tag: str) -> tuple[int, ...]:
    cleaned = tag.lstrip("vV")
    parts = cleaned.split(".")
    return tuple(int(p) if p.isdigit() else 0 for p in parts)


# ── public API (thread-safe, no Qt imports needed above here) ──────────


def get_latest_release() -> Optional[dict]:
    """Fetch latest release info from GitHub API. Call in a worker thread."""
    return _fetch_json(API_URL)


def is_newer_version(release_tag: str, current: str = paths.version) -> bool:
    return _parse_version(release_tag) > _parse_version(current)


def get_download_asset(release: dict) -> Optional[dict]:
    """Pick the right asset for the current platform from release data."""
    system = platform.system()
    machine = platform.machine()
    for asset in release.get("assets", []):
        name: str = asset.get("name", "")
        if system == "Linux":
            if "AppImage" in name and machine in name:
                return asset
        elif system == "Windows":
            if name.endswith(".exe") and "AppImage" not in name:
                return asset
        elif system == "Darwin":
            if name.endswith(".dmg"):
                return asset
    return None


def get_appimage_path() -> Optional[str]:
    return os.environ.get("APPIMAGE")


def is_appimage() -> bool:
    return "APPIMAGE" in os.environ


def download_asset(
    url: str,
    dest: str,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> bool:
    """Download an asset to *dest*.progress_cb receives 0.0–1.0."""
    tmp = dest + ".part"
    try:
        req = Request(url, headers={"User-Agent": "IsaacMM/1.0"})
        with urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", "0"))
            downloaded = 0
            chunk_size = 8192
            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        progress_cb(downloaded / total)
        os.replace(tmp, dest)
        return True
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


def install_appimage_update(downloaded_path: str) -> None:
    """Replace the running AppImage with *downloaded_path* and restart."""
    appimage = get_appimage_path()
    if not appimage:
        return

    pid = os.fork()
    if pid == 0:
        time.sleep(2)
        try:
            os.replace(downloaded_path, appimage)
            os.chmod(appimage, 0o755)
            os.execv(appimage, [appimage] + sys.argv[1:])
        except Exception:
            pass
        os._exit(1)


def install_windows_update(downloaded_path: str) -> None:
    """Replace the running .exe with *downloaded_path* and restart."""
    exe = sys.executable if getattr(sys, "frozen", False) else None
    if not exe:
        return

    import tempfile

    bat_path = os.path.join(tempfile.gettempdir(), "isaacmm_update.bat")
    content = (
        f"@echo off\r\n"
        f"timeout /t 2 /nobreak >nul\r\n"
        f'move /y "{downloaded_path}" "{exe}"\r\n'
        f'start "" "{exe}"\r\n'
    )
    try:
        with open(bat_path, "w") as f:
            f.write(content)
        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        )
    except Exception:
        return
    sys.exit(0)


# ── update UI dialog ───────────────────────────────────────────────────


class UpdateDialog(QDialog):
    def __init__(
        self,
        current_version: str,
        new_version: str,
        changelog: str,
        download_url: str,
        parent=None,
    ):
        super().__init__(parent)
        self._download_url = download_url
        self._download_path: Optional[str] = None

        self.setWindowTitle("Update Available")
        self.setMinimumSize(480, 360)

        layout = QVBoxLayout(self)

        header = QLabel(
            f"A new version is available: <b>{new_version}</b>"
            f"<br>(you have <b>{current_version}</b>)"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        self._changelog = QTextBrowser()
        self._changelog.setOpenExternalLinks(True)
        self._changelog.setPlainText(changelog or "(no release notes)")
        layout.addWidget(self._changelog)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel()
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        buttons = QDialogButtonBox()
        self._install_btn = buttons.addButton(
            "Download && Install", QDialogButtonBox.ActionRole
        )
        self._open_btn = buttons.addButton(
            "Open Release Page", QDialogButtonBox.ActionRole
        )
        buttons.addButton(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if not download_url:
            self._install_btn.setVisible(False)
            self._status_label.setText(
                "No download available for your platform. Open the release page instead."
            )
            self._status_label.setVisible(True)

        self._install_btn.clicked.connect(self._on_install)
        self._open_btn.clicked.connect(self._on_open)

    def _on_open(self) -> None:
        QDesktopServices.openUrl(RELEASES_URL)

    def _on_install(self) -> None:
        self._install_btn.setEnabled(False)
        self._open_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._status_label.setVisible(True)
        self._status_label.setText("Downloading...")

        import tempfile

        suffix = (
            "-x86_64.AppImage"
            if platform.system() == "Linux"
            else ".exe"
            if platform.system() == "Windows"
            else ".dmg"
        )
        tmp = tempfile.mktemp(suffix=suffix)

        def _progress(pct: float) -> None:
            QTimer.singleShot(0, lambda: self._progress.setValue(int(pct * 100)))

        def _do_download() -> bool:
            return download_asset(self._download_url, tmp, _progress)

        from .worker import ManagedWorker

        self._dl_worker = ManagedWorker(parent=self)
        self._dl_worker.finished.connect(lambda ok: self._on_downloaded(ok, tmp))
        self._dl_worker.error.connect(lambda _: None)
        self._dl_worker.start(_do_download, name="UpdateDownload")

    def _on_downloaded(self, ok: bool, path: str) -> None:
        if not ok:
            self._status_label.setText("Download failed. Check your connection.")
            self._install_btn.setEnabled(True)
            self._open_btn.setEnabled(True)
            return

        self._download_path = path
        self._status_label.setText("Download complete. Installing...")

        if is_appimage():
            self.accept()
            install_appimage_update(path)
        elif platform.system() == "Windows" and getattr(sys, "frozen", False):
            self.accept()
            install_windows_update(path)
        elif platform.system() == "Linux":
            self._status_label.setText(
                f"Downloaded to: {path}\n"
                "Not running as AppImage. Make it executable and run it."
            )
            self._install_btn.setVisible(False)
            QDesktopServices.openUrl(RELEASES_URL)
        else:
            self._status_label.setText(f"Downloaded to: {path}")
            self._install_btn.setVisible(False)
            QDesktopServices.openUrl(RELEASES_URL)

    def download_path(self) -> Optional[str]:
        return self._download_path
