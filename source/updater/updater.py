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

from ..core import config, paths

REPO = "PetricaT/IsaacMM"
LATEST_API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_API_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=1"
RELEASES_URL = f"https://github.com/{REPO}/releases"

_HEADERS = {"User-Agent": "IsaacMM/1.0"}


# -- helpers (thread-safe) ----------------------------------------------


def _parse_version(tag: str) -> tuple[int, ...]:
    cleaned = tag.lstrip("vV")
    parts = cleaned.split(".")
    nums = []
    for p in parts:
        digits = ""
        for ch in p:
            if ch.isdigit():
                digits += ch
            else:
                break
        nums.append(int(digits) if digits else 0)
    return tuple(nums)


# -- public API (thread-safe, no Qt imports needed above here) ----------


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


def get_latest_release(include_prereleases: bool = False) -> Optional[dict]:
    """Fetch latest release info from GitHub API. Call in a worker thread."""
    try:
        if include_prereleases:
            data = _fetch_json(RELEASES_API_URL)
            if isinstance(data, list) and data:
                return data[0]
            return None
        return _fetch_json(LATEST_API_URL)
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



