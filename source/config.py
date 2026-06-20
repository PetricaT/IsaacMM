import os
import toml

from . import paths, sorter

mods_path = ""
loaded_mods = []


def load():
    global mods_path
    try:
        cfg = toml.load(f"{paths.appdata}/config.toml")
        mods_path = cfg["paths"]["mods"]
        if mods_path == "":
            print("Mods path malformed, check if path is correct")
    except FileNotFoundError:
        _create_default()


def _create_default():
    global mods_path
    os.makedirs(paths.appdata, exist_ok=True)
    detected = paths.find_isaac_mods_folder()
    mods_path = detected or ""
    sorter.fetch_initial()
    cfg = {
        "paths": {"mods": mods_path},
        "settings": {"remove_marks": False},
    }
    with open(f"{paths.appdata}/config.toml", "w") as f:
        toml.dump(cfg, f)


def save():
    cfg = {
        "paths": {"mods": mods_path},
        "settings": {},
    }
    os.makedirs(paths.appdata, exist_ok=True)
    with open(f"{paths.appdata}/config.toml", "w") as f:
        toml.dump(cfg, f)
