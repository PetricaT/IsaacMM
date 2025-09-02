# ---------------------------------------
# Config file/folder manager
#
# The only purpose this serves is to manage, write and read
# the configuration file that is used to represent the state
# of the program.

import logging
import os, sys
import toml

from pathlib import Path

logger = logging.getLogger(__name__)

STEAM_APPID = 250900


class config_manager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance == None:
            inst = super().__new__(cls)
            inst._initialized = False
            inst._config = {}
            inst.config_file = None
            cls._instance = inst
        return cls._instance

    def __init__(self, config_directory: Path | None = None):
        """
        Helper class to generate and manage the configuration file
        """
        # Initialize only once
        if self._initialized or config_directory is None: return
        
        logger.debug(f"Config directory: {config_directory}")
        self.config_file = config_directory / "config.toml"
        self.config: dict = self._load_config()
        logger.debug(f"Mods dir: {self.get('paths', 'mods')}")
        self._initialized = True
        
    # --------------
    # Public API
    # --------------
    def get(self, header, variable):
        return self.config.get(header).get(variable)

    # --------------
    # Private functions
    # --------------
    def _load_config(self) -> dict:
        if self.config_file.exists():
            return toml.load(self.config_file)
        return self._create_default_config()

    def _create_default_config(self) -> dict:
        cfg = {"paths": {"mods": ""}, "settings": {"remove_marks": False}}
        # Get game path from Steam vdf file
        match sys.platform:
            case "win32":
                _mods_path = self._resolve_windows_path()
                pass
            case "darwin":
                _mods_path = str(
                    Path.home()
                    / "Library/Application Support/Binding of Isaac Afterbirth+ Mods"
                )
                if not os.path.exists(_mods_path): 
                    _mods_path = None
            case "linux":
                _mods_path = self._resolve_linux_path()

        logger.debug(f"Set mods path to: {_mods_path}")
        cfg["paths"]["mods"] = str(_mods_path) if _mods_path is not None else ""
        self._save_config(cfg)
        return cfg

    def _save_config(self, cfg: dict):
        with open(self.config_file, "w") as f:
            toml.dump(cfg, f)

    def _parse_vdf_path(self, steam_path: str) -> str | None:
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

    def _resolve_windows_path(self) -> Path | None:
        """
        Steam can be installed in any folder on Windows, but we can
        query the Steam registry to find the correct path.

        Returns: `%%STEAM_PATH%%\\steamapps\\common\\The Binding of Isaac Rebirth\\mods`
        """
        import winreg

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")  # type: ignore
        steam_path, _ = winreg.QueryValueEx(key, "SteamPath")  # type: ignore
        winreg.CloseKey(key)  # type: ignore

        return Path(rf"{self._parse_vdf_path(steam_path)}/steamapps/common/The Binding of Isaac Rebirth/mods")

    def _resolve_linux_path(self) -> Path | None:
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
                return Path(f"{self._parse_vdf_path(spath)}/steamapps/common/The Binding of Isaac Rebirth/mods/")
        return None
