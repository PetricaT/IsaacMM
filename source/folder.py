# ---------------------------------------
# Folder manager
#
# Any logic that relates to interacting with folders and files
# lives here.

import logging
import os
import re
import xml.etree.ElementTree as ET

from source.config import config_manager

sorted_pattern = re.compile(r"^[0-9]{3}\s{1}.*")

logger = logging.getLogger(__name__)

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
        self.mod_folder_data = {}
        # self.get_mod_list()

        self._initialized = True

    def get_mod_list(self) -> dict:
        blacklisted_folders = [".DS_Store"]  # Apple is the bane of my existance
        mods: list[str] = os.listdir(self.mods_dir)
        # Purge unwanted folders before getting metadata
        for _ in mods:
            if _ in blacklisted_folders:
                mods.pop(mods.index(_))
        # Generate metadata
        for mod in mods:
            self.mod_folder_data.update(self._generate_metadata(mod))
        return self.mod_folder_data

    def disable(self, raw_folder_name: str | None = None) -> None:
        if raw_folder_name is None: return
        disable_file = f"{self.mods_dir}/{raw_folder_name}/disable.it"
        if os.path.exists(disable_file): 
            logger.debug(f"Mod '{raw_folder_name}' alredy disabled")
            return
        else: 
            logger.debug(f"Disabling '{raw_folder_name}'")
            with open(disable_file, 'w') as f:
                f.close()

    def enable(self, raw_folder_name: str | None = None) -> None:
        if raw_folder_name is None: return
        disable_file = f"{self.mods_dir}/{raw_folder_name}/disable.it"
        if os.path.exists(disable_file):
            logger.debug(f"Enabling '{raw_folder_name}'")
            os.remove(disable_file)
            return
        logger.debug(f"Mod '{raw_folder_name}' alredy enabled")

    def _regen_metadata(self):
        self._generate_metadata

    def _generate_metadata(self, raw_folder_name: str) -> dict:
        rawFolderName: str = raw_folder_name
        absolutePath: str = f"{self.mods_dir}/{raw_folder_name}"
        steamID: int = self._resolve_steamid(rawFolderName)
        disableStatus = False
        if os.path.exists(f"{absolutePath}/disable.it"):
            disableStatus = True
        [modName, rank, directory, version, tags] = self._parse_xml(rawFolderName)

        return {
            rawFolderName: {
                "steamID": steamID, 
                "name": modName, 
                "rank": rank,
                "directory_name": directory,
                "path": absolutePath,
                "version": version,
                "disabled": disableStatus,
                "tags": tags
                }
        }

    def _resolve_steamid(self, raw_folder_name: str) -> int:
        # Resolves local (probably in dev) mods to -1
        try:
            return int(raw_folder_name.split("_")[-1])
        except ValueError:
            return -1

    def _parse_xml(self, raw_folder_name: str) -> list[str]:
        # Provide useful info from mod's xml
        try:
            mod_xml = ET.parse(f"{self.mods_dir}/{raw_folder_name}/metadata.xml")
            root = mod_xml.getroot()
            name: str = self._handle_none_xml_tag(
                root, "name", raw_folder=raw_folder_name
            )
            rank = -1
            directory: str = self._handle_none_xml_tag(
                root, "directory", raw_folder=raw_folder_name
            )
            version: str = self._handle_none_xml_tag(
                root, "version", raw_folder=raw_folder_name
            )
            
            tags = [tag.get("id") for tag in root.findall("tag")]
            if re.match(sorted_pattern, name):
                rank = int(name[:3])
                name = name[4:]
            return [name, rank, directory, version, tags]

        except FileNotFoundError:
            return [raw_folder_name, -1, raw_folder_name, "0", []]

    def _handle_none_xml_tag(
        self, xml_root: ET.Element, tag: str, raw_folder: str | None = None
    ) -> str:
        var = xml_root.find(tag)
        if var is None or var.text is None:
            logging.debug(f"Couldn't find parameter {tag} for {raw_folder}")
            return ""
        else:
            return var.text
