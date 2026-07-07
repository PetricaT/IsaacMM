"""Filesystem path resolution and symlink setup."""
from __future__ import annotations

import os
import re
import sys
from typing import Optional

from platformdirs import PlatformDirs

STEAM_APPID: int = 250900
WORKSHOP_ID_RE: re.Pattern = re.compile(r"_(\d+)$")

_dirs = PlatformDirs("IsaacMM", "PetricaT")
appdata: str = _dirs.user_data_dir
config_dir: str = _dirs.user_config_dir
cache_dir: str = _dirs.user_cache_dir


def _ensure_symlink(target: str, link: str) -> None:
    if os.path.islink(link):
        if os.readlink(link) != target:
            os.unlink(link)
            os.symlink(target, link)
    elif not os.path.exists(link):
        os.symlink(target, link)


def _migrate_old_linux_config() -> None:
    """Migrate config from old ~/.local/share/IsaacMM to ~/.config/IsaacMM on Linux."""
    old_appdata = os.path.expanduser("~") + "/.local/share/IsaacMM"
    if config_dir == old_appdata:
        return
    old_config = os.path.join(old_appdata, "config.toml")
    if not os.path.isfile(old_config):
        return
    new_config = os.path.join(config_dir, "config.toml")
    if os.path.isfile(new_config):
        return
    os.makedirs(config_dir, exist_ok=True)
    os.replace(old_config, new_config)


def setup_symlinks() -> None:
    os.makedirs(appdata, exist_ok=True)
    _migrate_old_linux_config()
    if config_dir != appdata and os.path.isdir(config_dir):
        old_link = os.path.join(appdata, "config")
        if os.path.islink(old_link):
            os.unlink(old_link)
        for entry in os.listdir(config_dir):
            src = os.path.join(config_dir, entry)
            dst = os.path.join(appdata, entry)
            if not os.path.exists(dst) and not os.path.islink(dst):
                os.symlink(src, dst)
    cache_link = os.path.join(appdata, "cache")
    if cache_dir != appdata and cache_dir != cache_link:
        _ensure_symlink(cache_dir, cache_link)


if getattr(sys, "frozen", False):
    BASE_DIR: str = sys._MEIPASS
elif os.environ.get("FLATPAK_ID"):
    BASE_DIR = "/app/share/IsaacMM"
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def initialize() -> None:
    global version
    try:
        import toml

        pyproject_path = os.path.join(BASE_DIR, "pyproject.toml")
        if os.path.exists(pyproject_path):
            version = toml.load(pyproject_path)["project"]["version"]
    except Exception:
        pass


version: str = "0.0.0"
initialize()


def _extract_workshop_id(folder_name: str) -> Optional[str]:
    match = WORKSHOP_ID_RE.search(folder_name)
    return match.group(1) if match else None


def find_isaac_mods_folder() -> Optional[str]:
    match sys.platform:
        case "win32":
            return _resolve_windows_path()
        case "darwin":
            mods_path = os.path.expanduser(
                "~/Library/Application Support/Binding of Isaac Afterbirth+ Mods"
            )
            return mods_path if os.path.exists(mods_path) else None
        case "linux":
            return _resolve_linux_path()
    return None


def _parse_vdf_path(steam_path: str) -> Optional[str]:
    try:
        with open(f"{steam_path}/config/libraryfolders.vdf") as vdf_file:
            for line in vdf_file:
                if '"path"' in line:
                    game_root_path = line.split('"')[3]
                if f'"{STEAM_APPID}"' in line:
                    candidate_path = (
                        f"{game_root_path}/steamapps/common/"
                        "The Binding of Isaac Rebirth/mods/"
                    )
                    if os.path.exists(candidate_path):
                        return game_root_path
    except (FileNotFoundError, IndexError):
        pass
    return None


def _resolve_windows_path() -> Optional[str]:
    try:
        import winreg

        registry_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"
        )  # pyright: ignore[reportAttributeAccessIssue]
        steam_path, _ = winreg.QueryValueEx(
            registry_key, "SteamPath"
        )  # pyright: ignore[reportAttributeAccessIssue]
        winreg.CloseKey(registry_key)  # pyright: ignore[reportAttributeAccessIssue]
        steam_root = _parse_vdf_path(steam_path)
        if steam_root:
            return f"{steam_root}/steamapps/common/The Binding of Isaac Rebirth/mods/"
    except Exception:
        pass
    return None


def _resolve_linux_path() -> Optional[str]:
    home: str = os.path.expanduser("~")
    steam_paths: list[str] = [
        f"{home}/.steam/steam",
        f"{home}/.local/share/Steam",
        f"{home}/snap/steam/common/.local/share/Steam",
        f"{home}/steam/root",
        f"{home}/steam",
        f"{home}/.var/app/com.valvesoftware.Steam/.steam/steam",
        f"{home}/.var/app/com.valvesoftware.Steam/.local/share/Steam",
        f"{home}/.var/app/com.valvesoftware.Steam/.steam/root",
        f"{home}/.var/app/com.valvesoftware.Steam/.steam",
    ]
    for steam_path in steam_paths:
        if os.path.exists(steam_path):
            steam_root = _parse_vdf_path(steam_path)
            if steam_root:
                return (
                    f"{steam_root}/steamapps/common/The Binding of Isaac Rebirth/mods/"
                )
    return None
