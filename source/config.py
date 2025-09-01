# ---------------------------------------
# Config file/folder manager
#
# The only purpose this serves is to manage, write and read
# the configuration file that is used to represent the state
# of the program.

import logging
import os
import sys
from pathlib import Path
import toml

logger = logging.getLogger(__name__)

STEAM_APPID = 250900


class config_manager:
    def __init__(self, config_directory: Path):
        """
        Helper class to generate and manage the configuration file
        """
        logger.debug(f"Config directory: {config_directory}")
        self.config_file = config_directory / "config.toml"
        self.config = self.load_config()

    def get_config(self) -> dict:
        return self.config

    def load_config(self) -> dict:
        if self.config_file.exists():
            return toml.load(self.config_file)
        return self.create_default_config()

    def create_default_config(self) -> dict:
        cfg = {"paths": {"mods": ""}, "settings": {"remove_marks": False}}
        # Get game path from Steam vdf file
        match sys.platform:
            case "win32":
                _mods_path = self.resolve_windows_path()
                pass
            case "darwin":
                _mods_path = str(
                    Path.home()
                    / "Library/Application Support/Binding of Isaac Afterbirth+ Mods"
                )
                if not os.path.exists(_mods_path): 
                    _mods_path = None
            case "linux":
                _mods_path = self.resolve_linux_path()

        logger.debug(f"Set mods path to: {_mods_path}")
        cfg["paths"]["mods"] = str(_mods_path) if _mods_path is not None else ""
        self.save_config(cfg)
        return cfg

    def save_config(self, cfg: dict):
        with open(self.config_file, "w") as f:
            toml.dump(cfg, f)

    def parse_vdf_path(self, steam_path: str) -> str | None:
        """
        Simple Valve Data File (.vdf) reader to figure out where a game is located on
        the computer.

        Reads the VDF line by line and early returns when the game is found
        """
        try:
            with open(f"{steam_path}/config/libraryfolders.vdf", "r") as file:
                for line in file:
                    if '"path"' in line:
                        game_root_folder = line.split('"')[3]
                    if f'"{STEAM_APPID}"' in line:
                        if os.path.exists(
                            f"{game_root_folder}/steamapps/common/The Binding of Isaac Rebirth/mods/"
                        ):
                            logger.info("VDF Found folder")
                            return game_root_folder
                file.close()
        except FileNotFoundError:
            pass
        return None

    def resolve_windows_path(self) -> Path | None:
        """
        Steam can be installed in any folder on Windows, but we can
        query the Steam registry to find the correct path.

        Returns: `%%STEAM_PATH%%\\steamapps\\common\\The Binding of Isaac Rebirth\\mods`
        """
        import winreg

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")  # type: ignore
        steam_path, _ = winreg.QueryValueEx(key, "SteamPath")  # type: ignore
        winreg.CloseKey(key)  # type: ignore

        return Path(rf"{self.parse_vdf_path(steam_path)}/steamapps/common/The Binding of Isaac Rebirth/mods")

    def resolve_linux_path(self) -> Path | None:
        """
        Linux can have multiple locations for the steam install, therefore
        we check some of the known file locations depending on the install
        method: native, snap, flatpak

        Returns: `$STEAM_PATH/steamapps/common/The Binding of Isaac Rebirth/mods`
        """
        # Target: ~/.local/share/Steam/config/libraryfolders.vdf
        USER_HOME = Path.home()
        STEAM_PATHS = [
            f"{USER_HOME}/.steam/steam",
            f"{USER_HOME}/.local/share/Steam",
            f"{USER_HOME}/snap/steam/common/.local/share/Steam",
            f"{USER_HOME}/steam/root",
            f"{USER_HOME}/steam",
            f"{USER_HOME}/.var/app/com.valvesoftware.Steam/.steam/steam",
            f"{USER_HOME}/.var/app/com.valvesoftware.Steam/.local/share/Steam",
            f"{USER_HOME}/.var/app/com.valvesoftware.Steam/.steam/root",
            f"{USER_HOME}/.var/app/com.valvesoftware.Steam/.steam",
        ]
        # Attrocious implementation but the safest
        for spath in STEAM_PATHS:
            if os.path.exists(spath):
                return Path(f"{self.parse_vdf_path(spath)}/steamapps/common/The Binding of Isaac Rebirth/mods/")
        return None
