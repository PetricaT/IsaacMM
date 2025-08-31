import xml.etree.ElementTree as ET
from pathlib import Path
import tomllib
import logging
import sys
import os
import re

from source.config import config_manager

sorted_pattern = re.compile(r'[0-9]{3}\s{1}.*')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler('exec.log', mode='w')
fh.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)


formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)

class mod_manager:
    def __init__(self):
        logger.info(f"Running on platform {sys.platform}")
        match sys.platform:
            case "win32":
                self.config_directory = Path.home() / 'AppData' / 'Local' / 'IsaacMM'
            case "darwin":
                self.config_directory = Path.home() / 'Library' / 'Application Support' / 'IsaacMM'
            case "linux":
                self.config_directory = Path.home() / '.config' / 'IsaacMM'
            case _:
                print("OS Not Supported")
                sys.exit(1)
    
        config_manager(self.config_directory)

if __name__ == '__main__':
    mod_manager()