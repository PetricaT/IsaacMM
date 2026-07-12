"""Self-update: GitHub release check, download, and AppImage replacement."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
import time
from typing import Callable, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from . import config, paths

REPO = "PetricaT/IsaacMM"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases"

_HEADERS = {"User-Agent": "IsaacMM/1.0"}


# ── helpers (thread-safe) ──────────────────────────────────────────────


def _parse_version(tag: str) -> tuple[int, ...]:
    cleaned = tag.lstrip("vV")
    parts = cleaned.split(".")
    return tuple(int(p) if p.isdigit() else 0 for p in parts)


# ── public API (thread-safe, no Qt imports needed above here) ──────────


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=10),
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True,
)
def _fetch_json(url: str) -> Optional[dict]:
    with httpx.Client(follow_redirects=True) as client:
        resp = client.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()


def get_latest_release() -> Optional[dict]:
    """Fetch latest release info from GitHub API. Call in a worker thread."""
    try:
        return _fetch_json(API_URL)
    except Exception:
        return None


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


def find_appimageupdatetool() -> Optional[str]:
    """Find the bundled appimageupdatetool inside the running AppImage."""
    appimage = get_appimage_path()
    if not appimage:
        return None
    appdir = os.path.dirname(appimage)
    tool = os.path.join(appdir, "usr", "bin", "appimageupdatetool")
    if os.path.isfile(tool) and os.access(tool, os.X_OK):
        return tool
    return None


def run_appimage_delta_update(
    progress_cb: Optional[Callable[[str], None]] = None,
) -> bool:
    """Run appimageupdatetool for a delta update. Returns True on success."""
    tool = find_appimageupdatetool()
    appimage = get_appimage_path()
    if not tool or not appimage:
        return False
    try:
        proc = subprocess.run(
            [tool, appimage],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return proc.returncode == 0
    except Exception:
        return False


def download_asset(
    url: str,
    dest: str,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> bool:
    """Download an asset to *dest*. progress_cb receives 0.0-1.0."""
    tmp = dest + ".part"
    try:
        with httpx.Client(follow_redirects=True) as client:
            with client.stream("GET", url, headers=_HEADERS, timeout=120) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", "0"))
                downloaded = 0
                with open(tmp, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=8192):
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

        # Try delta update first when running as AppImage with bundled tool
        if is_appimage() and find_appimageupdatetool():
            self._progress.setVisible(True)
            self._progress.setRange(0, 0)
            self._status_label.setVisible(True)
            self._status_label.setText("Applying delta update...")
            from .worker import ManagedWorker

            self._dl_worker = ManagedWorker(parent=self)
            self._dl_worker.finished.connect(self._on_delta_done)
            self._dl_worker.error.connect(self._on_delta_error)
            self._dl_worker.start(run_appimage_delta_update, name="DeltaUpdate")
            return

        # Fall back to full download
        self._progress.setVisible(True)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._status_label.setVisible(True)
        self._status_label.setText("Downloading...")
        self._start_full_download()

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

    def _on_delta_done(self, ok: bool) -> None:
        if ok:
            self._status_label.setText("Update applied. Restarting...")
            self._progress.setRange(0, 100)
            self._progress.setValue(100)
            self.accept()
            appimage = get_appimage_path()
            if appimage:
                QTimer.singleShot(1500, lambda: os.execv(appimage, [appimage] + sys.argv[1:]))
        else:
            self._status_label.setText("Delta update failed. Falling back to full download...")
            self._progress.setRange(0, 100)
            self._progress.setValue(0)
            self._start_full_download()

    def _on_delta_error(self, msg: str) -> None:
        self._status_label.setText("Delta update failed. Falling back to full download...")
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._start_full_download()

    def _start_full_download(self) -> None:
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
