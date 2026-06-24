import os
import re
import sys
from typing import Optional

STEAM_APPID: int = 250900
WORKSHOP_ID_RE: re.Pattern = re.compile(r"_(\d+)$")

appdata: str = ""
if sys.platform == "win32":
    appdata = os.path.expanduser("~") + "/AppData/Local/IsaacMM"
elif sys.platform == "darwin":
    appdata = os.path.expanduser("~") + "/Library/Application Support/IsaacMM"
else:
    xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    appdata = os.path.join(xdg_data, "IsaacMM")

if getattr(sys, "frozen", False):
    BASE_DIR: str = sys._MEIPASS
elif os.environ.get("FLATPAK_ID"):
    BASE_DIR = "/app/share/IsaacMM"
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

version: str = "0.0.0"
try:
    import toml

    pyproject_path = os.path.join(BASE_DIR, "pyproject.toml")
    if os.path.exists(pyproject_path):
        version = toml.load(pyproject_path)["project"]["version"]
except Exception:
    pass


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

        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(registry_key, "SteamPath")
        winreg.CloseKey(registry_key)
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
