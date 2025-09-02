# ---------------------------------------
# Folder manager
#
# Any logic that relates to interacting with folders and files
# lives here.

import xml.etree.ElementTree as ET
import logging
import os, sys

from source.config import config_manager
from pathlib import Path

class folder_manager:
    def __init__(self):
        self.config = config_manager()
        self.modlist = {}
        # self._get_mod_list()
        print(self.config.get("paths", "mods"))
    
    def _get_mod_list(self):
        mod_folder_list = {}
        mods = os.listdir(self.config.get_variable("paths", "mods"))
        print(mods)
        pass