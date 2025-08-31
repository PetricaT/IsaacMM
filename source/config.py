from pathlib import Path
import logging
import toml
import sys
import re

logger = logging.getLogger(__name__)

class config_manager:
    def __init__(self, config_directory):
        self.cfg_file = config_directory


    def load_config(self) -> dict:
        if self.cfg_file.exists():
            return toml.load(self.cfg_file)
        return self.create_default_config()
    

    def create_default_config(self) -> dict:
        cfg = {"paths": {"mods": ""}, "settings": {"remove_marks": False}}
        # Try to guess the Isaac folder
        isaac_folder = re.compile(r".*Binding of Isaac.*")
        match sys.platform:
            case "win32":
                #TODO: Try default C: for possible path
                pass
            case "darwin":
                cfg["paths"]["mods"] = str(
                Path.home() / "Library/Application Support/Binding of Isaac Afterbirth+ Mods"
            )
            case "linux":
                steam_path = Path.home() / ".steam/steam/steamapps/common"
                #TODO: READ ACF FILES FOR GAME PATH
        self.save_config(cfg)
        return cfg
    

    def save_config(self, cfg: dict):
        with open(self.cfg_file, 'w') as f:
            toml.dump(cfg, f)