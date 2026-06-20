# ---------------------------------------
# Mod name management and automatic sorting

import logging
import os
import re
import xml.etree.ElementTree as ET

from source.config import config_manager
from source.folder import folder_manager

sorted_pattern = re.compile(r"^[0-9]{3}\s{1}.*")

logger = logging.getLogger(__name__)

class sort_manager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._initialized = False
            cls._instance = inst
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.config = config_manager()
        self.active_sort_order = []
        # Sort fetched mods ascending (for when we display the list)
        mlist = folder_manager().get_mod_list()
        mods = mlist.keys()
        for mod in mods:
            self.active_sort_order.append([mlist.get(mod)["rank"], mlist.get(mod)["name"]])
        self.active_sort_order.sort()
