import xml.etree.ElementTree as ET
from pathlib import Path
import platformdirs
import configparser
import logging
import sys
import os
import re

SORTED_PATTERN = re.compile(r'[0-9]{3}\s{1}.*')
logger = logging.Logger('libisaac')
class libisaac:
  def __init__(self, GENERATE_CONFIG = True):
    self.GENERATE_CONFIG = GENERATE_CONFIG
    self.cfgparser = configparser.ConfigParser
    self.CONFIG_PATH = platformdirs.user_config_path('libisaac')
    self.LOG_PATH = platformdirs.user_log_path('libisaac')
    self.CONFIG_FILE_PATH = Path(rf'{self.CONFIG_PATH}/config.ini')

    print(fr'{'CONFIG PATH':<18}: {self.CONFIG_PATH}')
    print(fr'{'CONFIG FILE PATH':<18}: {self.CONFIG_FILE_PATH}')
    print(fr'{'LOG PATH':<18}: {self.LOG_PATH}')
    try: 
      logging.basicConfig(filename=fr'{self.LOG_PATH}/libisaac.log')
    except:
      os.makedirs(self.LOG_PATH)
      logging.basicConfig(filename=fr'{self.LOG_PATH}/libisaac.log')
    self._get_config()

  def _get_config(self):
    print(self.CONFIG_PATH)
    if not os.path.exists(self.CONFIG_PATH) and self.GENERATE_CONFIG: os.makedirs(self.CONFIG_PATH)
    if os.path.exists(self.CONFIG_FILE_PATH):
      logger.info('Config file found, loading.')
      self.cfgparser.read(self.CONFIG_FILE_PATH)
    else:
      logger.warning('Config file not found')
      # If the dev wants to make their own config, respect that option.
      if self.GENERATE_CONFIG:      
        with open(Path(fr'{self.CONFIG_PATH}/config.ini'), 'w') as f:
          f.write('[GENERAL]')
          f.write('mods_folder=')
          f.close()


  def getmods() -> list[str]:
    '''Returns a list of all the currently installed mods (present in the mods folder)'''
    pass

libisaac()