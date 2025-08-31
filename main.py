import logging
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import tomllib

from source.config import config_manager

sorted_pattern = re.compile(r"[0-9]{3}\s{1}.*")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class mod_manager:
    def __init__(self):
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
        self._setup_logger()

        config_manager(self.config_directory)

    def _setup_logger(self):
        # Disable log writing if it is unset
        if logger.level <= 0:
            return
        # Create log file at config dir.
        if not os.path.exists(f"{self.config_directory}/exec.log"):
            os.makedirs(self.config_directory)

        fh = logging.FileHandler(f"{self.config_directory}/exec.log", mode="w")
        fh.setLevel(logging.DEBUG)

        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        file_formatter = logging.Formatter("%(name)s %(levelname)s - %(message)s")
        fh.setFormatter(file_formatter)

        console_formatter = logging.Formatter("%(levelname)s - %(message)s")
        ch.setFormatter(console_formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

        logger.info(f"Running on platform {sys.platform}")

    def sometin(self):
        pass


if __name__ == "__main__":
    mod_manager()
