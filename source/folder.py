# ---------------------------------------
# Folder manager
#
# Any logic that relates to interacting with folders and files
# lives here.

import logging
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from source.config import config_manager

sorted_pattern = re.compile(r"^[0-9]{3}\s{1}.*")


class folder_manager:
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
        self.modlist = {}
        self.mods_dir = self.config.get("paths", "mods")
        self._get_mod_list()

        self._initialized = True

    def _get_mod_list(self):
        mod_folder_data = {}
        blacklisted_folders = [".DS_Store"]  # Apple is the bane of my existance
        mods: list[str] = os.listdir(self.mods_dir)
        # Purge unwanted folders before getting metadata
        for _ in mods:
            if _ in blacklisted_folders:
                mods.pop(mods.index(_))
        # Generate metadata
        for mod in mods:
            mod_folder_data.update(self._generate_metadata(mod))

        print(mod_folder_data)

    def _generate_metadata(self, raw_folder_name: str) -> dict:
        rawFolderName: str = raw_folder_name
        steamID: int = self._resolve_steamid(rawFolderName)
        [modName, version] = self._parse_xml(rawFolderName)

        return {
            rawFolderName: {"steamID": steamID, "name": modName, "version": version}
        }

    def _resolve_steamid(self, raw_folder_name: str) -> int:
        # Resolves local (probably in dev) mods to -1
        try:
            return int(raw_folder_name.split("_")[-1])
        except ValueError:
            return -1

    def _parse_xml(self, raw_folder_name: str) -> list[str]:
        """Returns list[Mod Name: str, Version: str]"""
        # Provide useful info from mod's xml
        try:
            mod_xml = ET.parse(f"{self.mods_dir}/{raw_folder_name}/metadata.xml")
            root = mod_xml.getroot()
            name: str = self._handle_none_xml_tag(
                root, "name", raw_folder=raw_folder_name
            )
            version: str = self._handle_none_xml_tag(
                root, "version", raw_folder=raw_folder_name
            )

            if re.match(sorted_pattern, name):
                name = name[4:]
            return [name, version]

        except FileNotFoundError:
            return [raw_folder_name, "0"]

    def _handle_none_xml_tag(
        self, xml_root: ET.Element, tag: str, raw_folder: str | None = None
    ) -> str:
        var = xml_root.find(tag)
        if var is None or var.text is None:
            logging.debug(f"Couldn't find parameter {tag} for {raw_folder}")
            return ""
        else:
            return var.text
