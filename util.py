import xml.etree.ElementTree as ET
from pathlib import Path
import toml
import os
import re

sorted_pattern = re.compile(r'[0-9]{3}\s{1}.*')

class log:
  def debug(TEXT: str):
    level = 'DEBUG'
    color = '\033[94m'
    print(color + f'[{level:_^5}] {TEXT}' + '\033[0m')
    
  def info(TEXT: str):
    level = 'INFO'
    print(f'[{level:_^5}] {TEXT}' + '\033[0m')


  def warn(TEXT: str):
    level = 'WARN'
    color = '\033[93m'
    print(color + f'[{level:_^5}] {TEXT}' + '\033[0m')

  def error(TEXT: str):
    level = 'ERROR'
    color = '\033[91m'
    print(color + f'[{level:_^5}] {TEXT}' + '\033[0m')

class util:
  '''Utility class for TboI mod sorter'''
  def __init__(self):
    super().__init__()
    # Check if config exists, otherwise write it.
    if os.path.exists('config.toml'):
      global SETTINGS
      SETTINGS = toml.load('config.toml')
      try:
        global MODS_PATH
        MODS_PATH = Path(SETTINGS['paths']['mods'])
      except:
        print("Error reading MODS_PATH from TOML")
    else:
      with open('config.toml', 'w') as f:
        f.write('[paths]')
        f.write("mods='C:\Path\To\Your\Mod\Folder'")
        print('Please set the mod folder path in `config.toml`')
  
  def setMods(self, mods_folder_path: Path) -> None:
    SETTINGS['paths']['mods'] = str(mods_folder_path)
  
  def loadMods(self) -> list:
    mod_array = []
    #       0           1         2       3
    # +------------+----------+------+----------+
    # │ Sort Order │ Mod name │ Path │ XML Name │
    # +------------+----------+------+----------+
    log.debug(MODS_PATH)
    for item in os.listdir(MODS_PATH):
      sorted = False
      xml_config_path = Path(str(MODS_PATH) + '\\' + item + '\\' + 'metadata.xml')
      xml_config = ET.parse(xml_config_path)
      xml_name = xml_config.getroot()[0].text
      if re.match(sorted_pattern, xml_name):
        sorted = True

      RANK = xml_name[:3]
      NAME = xml_name
      FOLDER_NAME = item
      PATH = str(MODS_PATH) + '\\' + item
      if sorted:
        mod_array.append((RANK, NAME, FOLDER_NAME, PATH))
      else:
        mod_array.append(("_", NAME, FOLDER_NAME, PATH))
    return mod_array

  def genOrder(self, mod_list):    
    # Sort load order by number
    mod_list.sort(key=lambda mod: mod[0])
    max_mod_name: int = 0
    max_mod_steam_name: int = 0
    
    # Get longest game name for middle column
    for item in mod_list:
      if len(item[1]) > max_mod_name: max_mod_name = len(item[1])
      if len(item[2]) > max_mod_steam_name: max_mod_steam_name = len(item[2])
    
    # Write mods.txt with current mod order, leaving unsorted at the bottom
    with open('mods.txt', 'w') as f:
      for item in mlist:
        f.write(f'{item[1]:<{max_mod_name}}|{item[2]:<{max_mod_steam_name}}|{item[3]}\n')

  def printList(self, list):
    for i in list:
      print(i)
  
  def useOrder(self, modlist):
    if not os.path.exists('mods.txt'):
      log.warn('MODS.TXT does not exit, generating now...')
      mods.genOrder(mod_list=modlist)
      log.warn('MODS.TXT has been generated, go and sort the mods')
      return
    else:
      log.info('Applying sorted list')
      rank = 1
      sorted_list = []
      with open('mods.txt', 'r') as f:
        lines = f.readlines()
        for line in lines:
          line = line.split('|')
          rank_str = f'{rank:0>3}'
          NAME = line[0].strip()
          FOLDER_NAME = line[1].strip()
          PATH = line[2].replace('\n', '')
          sorted_list.append((rank_str, NAME, FOLDER_NAME, PATH))
          rank += 1
    self.applyList(sorted_list)
    
  def applyList(self, sorted_list):
    for mod in sorted_list:
      XML_PATH = mod[3] + '\\' + 'metadata.xml'
      tree = ET.parse(XML_PATH)
      root = tree.getroot()
      current_name = root[0].text
      if re.match(sorted_pattern, current_name):
        new_name = current_name
        old_tag = current_name[:3]
        new_name = new_name.replace(old_tag, '')
        new_name = mod[0] + new_name
      else:
        new_name = mod[0] + ' ' + current_name
      
      name_element = root.find('name')
      if name_element is not None:
        name_element.text = new_name
      tree.write(mod[3] + '\\' + 'metadata.xml')
        
mods = util()
mlist = mods.loadMods()
mods.useOrder(modlist=mlist)


