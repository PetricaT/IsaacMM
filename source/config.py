import os
import toml

from . import paths

mods_path = ""
remove_marks = False
loaded_mods = []


def load():
    global mods_path, remove_marks
    try:
        cfg = toml.load(f"{paths.appdata}/config.toml")
        mods_path = cfg["paths"]["mods"]
        if mods_path == "":
            print("Mods path malformed, check if path is correct")
        remove_marks = cfg["settings"].get("remove_marks", "false") == "true"
    except FileNotFoundError:
        _create_default()


def _create_default():
    global mods_path
    os.makedirs(paths.appdata, exist_ok=True)
    detected = paths.find_isaac_mods_folder()
    mods_path = detected or ""
    cfg = {
        "paths": {"mods": mods_path},
        "settings": {"remove_marks": False},
    }
    with open(f"{paths.appdata}/config.toml", "w") as f:
        toml.dump(cfg, f)


def save():
    cfg = {
        "paths": {"mods": mods_path},
        "settings": {"remove_marks": remove_marks},
    }
    os.makedirs(paths.appdata, exist_ok=True)
    with open(f"{paths.appdata}/config.toml", "w") as f:
        toml.dump(cfg, f)
