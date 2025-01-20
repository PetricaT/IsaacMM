#!/opt/homebrew/bin/python3
import xml.etree.ElementTree as ET
from pathlib import Path
import platformdirs
import configparser
import subprocess
import logging
import sys
import os
import re

import platformdirs.macos

SORTED_PATTERN = re.compile(r'[0-9]{3}\s{1}.*')
logger = logging.getLogger('libisaac')

if sys.platform == "win32":
    OS = 'Windows'
elif sys.platform == "darwin":
    OS = 'MacOS'
else:
    OS = 'Linux'

# Windows   : C:\Program Files (x86)\Steam\steamapps\common\The Binding of Isaac Rebirth\mods\
# Linux     : /Steam/steamapps/compatdata/250900/pfx/drive_c/users/steamuser/Documents/My Games/Binding of Isaac Afterbirth+ Mods
# MacOS     : /Users/USERNAME/Library/Application Support/Binding of Isaac Afterbirth+ Mods

class libisaac:
  def __init__(self, GENERATE_CONFIG = True):
    self.GENERATE_CONFIG = GENERATE_CONFIG
    self.cfgparser = configparser.ConfigParser
    self.CONFIG_PATH = platformdirs.user_config_path('libisaac')
    self.LOG_PATH = platformdirs.user_log_path('libisaac')
    self.CONFIG_FILE_PATH = Path(rf'{self.CONFIG_PATH}/config.ini')
    self.MODS_PATH = ''
    logging.basicConfig(filename=fr'{self.LOG_PATH}/libisaac.log', level=logging.DEBUG, filemode='w')

    print(fr'CONFIG PATH:      {self.CONFIG_PATH}')
    print(fr'CONFIG FILE PATH: {self.CONFIG_FILE_PATH}')
    print(fr'LOG PATH:         {self.LOG_PATH}')

    try: os.makedirs(self.LOG_PATH)
    except: pass

    self._get_config()

  def _get_config(self):
    print(self.CONFIG_PATH)
    if not os.path.exists(self.CONFIG_PATH) and self.GENERATE_CONFIG: os.makedirs(self.CONFIG_PATH)
    if os.path.exists(self.CONFIG_FILE_PATH):
      logger.info('Config file found, loading.')
      #self.cfgparser.read(self.CONFIG_FILE_PATH)
    else:
      logger.warning('Config file not found')
      # If the dev wants to make their own config, respect that option.
      if self.GENERATE_CONFIG:      
        logger.info('Generating config file')
        with open(Path(fr'{self.CONFIG_PATH}/config.ini'), 'w') as f:
          f.write('[GENERAL]\n')
          # Make best effort to autofill
          # TODO: Implement Windows & Linux
          if OS == 'MacOS':
            USERNAME = subprocess.run(["whoami"], capture_output=True)
            USERNAME = str(USERNAME.stdout).replace("b'", '').replace(r"\n'", '')
            logger.debug(f'MacOS detected, writing config with username: {USERNAME}')
            f.write(f'mods_folder=/Users/{USERNAME}/Library/Application Support/Binding of Isaac Afterbirth+ Mods')
          else:
            f.write(f'mods_folder=')
          f.close()

  def getmods(self) -> list[str]:
    '''Returns a list of all the currently installed mods (present in the mods folder)'''
    # SORT_ID, Folder name, Mod Name
    folder_list = os.listdir(self.MODS_PATH)
    print(folder_list)

  def setmods(self, mods_folder_path: Path):
    self.MODS_PATH = mods_folder_path


libisaac()
