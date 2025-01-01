import xml.etree.ElementTree as ET
from pathlib import Path
import toml
import os
import re

settings = toml.load('config.toml')
MODS_PATH = Path(settings['paths']['mods']) 
MODS = os.listdir(MODS_PATH)
sorted_pattern = re.compile(r'[A-Z]{2}\s{1}.*')


class util:
  def setmods(mods_folder_path: Path):
    
    pass
  
  def loadmods(mods_folder_path: Path):
    # +------------+----------+------+----------+
    # │ Sort Order │ Mod name │ Path │ XML Name │
    # +------------+----------+------+----------+
    
    for item in os.listdir(mods_folder_path):
      xml_config_path = Path(str(MODS_PATH) + '\\' + item + '\\' + 'metadata.xml')
      xml_config = ET.parse(xml_config_path)
      root = xml_config.getroot()[0].text
      print(root)

util.loadmods(MODS_PATH)

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