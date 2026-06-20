import os
import sys

STEAM_APPID = 250900

if sys.platform == "win32":
    appdata = os.path.expanduser("~") + "/AppData/IsaacMM"
elif sys.platform == "darwin":
    appdata = os.path.expanduser("~") + "/Library/Application Support/IsaacMM"
else:
    appdata = os.path.expanduser("~") + "/.local/share/IsaacMM"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

version = "0.0.0"
try:
    import toml

    pp = os.path.join(BASE_DIR, "pyproject.toml")
    if os.path.exists(pp):
        version = toml.load(pp)["project"]["version"]
except Exception:
    pass


def find_isaac_mods_folder():
    match sys.platform:
        case "win32":
            return _resolve_windows_path()
        case "darwin":
            p = os.path.expanduser(
                "~/Library/Application Support/Binding of Isaac Afterbirth+ Mods"
            )
            return p if os.path.exists(p) else None
        case "linux":
            return _resolve_linux_path()
    return None


def _parse_vdf_path(steam_path):
    try:
        with open(f"{steam_path}/config/libraryfolders.vdf") as f:
            for line in f:
                if '"path"' in line:
                    game_root = line.split('"')[3]
                if f'"{STEAM_APPID}"' in line:
                    candidate = (
                        f"{game_root}/steamapps/common/"
                        "The Binding of Isaac Rebirth/mods/"
                    )
                    if os.path.exists(candidate):
                        return game_root
    except (FileNotFoundError, IndexError):
        pass
    return None


def _resolve_windows_path():
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"
        )
        steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
        winreg.CloseKey(key)
        root = _parse_vdf_path(steam_path)
        if root:
            return f"{root}/steamapps/common/The Binding of Isaac Rebirth/mods/"
    except Exception:
        pass
    return None


def _resolve_linux_path():
    home = os.path.expanduser("~")
    steam_paths = [
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
    for sp in steam_paths:
        if os.path.exists(sp):
            root = _parse_vdf_path(sp)
            if root:
                return (
                    f"{root}/steamapps/common/"
                    "The Binding of Isaac Rebirth/mods/"
                )
    return None
