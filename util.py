import xml.etree.ElementTree as ET
from pathlib import Path
import toml
import os
import re

sorted_pattern = re.compile(r'[0-9]{3}\s{1}.*')


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
  
  def setmods(mods_folder_path: Path) -> None:
    SETTINGS['paths']['mods'] = str(mods_folder_path)
  
  def loadmods(self):
    # +------------+----------+------+----------+
    # │ Sort Order │ Mod name │ Path │ XML Name │
    # +------------+----------+------+----------+
    print(MODS_PATH)
    for item in os.listdir(MODS_PATH):
      xml_config_path = Path(str(MODS_PATH) + '\\' + item + '\\' + 'metadata.xml')
      xml_config = ET.parse(xml_config_path)
      root = xml_config.getroot()[0].text
      print(root)

mods = util()
mods.loadmods()

# XML
# {metadata} -> {name}
# for index, item in enumerate(MODS):
#   sorted = '_'
#   xml_config_path = Path(str(MODS_PATH) + '\\' + item + '\\' + 'metadata.xml')
#   xml_config = ET.parse(xml_config_path)
#   root = xml_config.getroot()[0].text
#   item = root.strip('!').strip()
#   if re.findall(sorted_pattern, item):
#     sorted = 'X'

#   print(f'[{sorted}] {index+1}.\t{root}')