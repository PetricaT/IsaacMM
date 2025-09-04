import logging
import os
import re
import sys
from pathlib import Path

from source.config import config_manager
from source.folder import folder_manager
from source.sort import sort_manager

sorted_pattern = re.compile(r"[0-9]{3}\s{1}.*")

class mod_manager:
    def __init__(self):
        # Determine where the application state should be stored
        match sys.platform:
            case "win32":
                self.config_directory = Path.home() / "AppData" / "Local" / "IsaacMM"
            case "darwin":
                self.config_directory = (
                    Path.home() / "Library" / "Application Support" / "IsaacMM"
                )
            case "linux":
                self.config_directory = Path.home() / ".config" / "IsaacMM"
            case _:
                print("OS Not Supported")
                sys.exit(1)

        # Initiate config directory
        if not os.path.exists(self.config_directory):
            os.makedirs(self.config_directory)
        
        self._setup_logger()
        # cfg = config_manager(self.config_directory)
        config_manager(self.config_directory)
        sort_manager()

    def _setup_logger(self):
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        file_formatter = logging.Formatter("%(name)s [%(levelname)s] - %(message)s")
        fh = logging.FileHandler(f"{self.config_directory}/exec.log", mode="w")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(file_formatter)

        console_formatter = ColoredFormatter("%(levelname)s\t- %(message)s")
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(console_formatter)

        if not logger.handlers:
            logger.addHandler(fh)
            logger.addHandler(ch)

        logger.info(f"Running on platform {sys.platform}")

    def sometin(self):
        pass

class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[34m",   # Blue
        "INFO": "\033[36m",    # Cyan
        "WARNING": "\033[33m", # Yellow
        "ERROR": "\033[31m",   # Red
        "CRITICAL": "\033[41m" # Red background
    }
    RESET = "\033[0m"

    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        return super().format(record)


if __name__ == "__main__":
    mod_manager()
