import hashlib
import os
import shutil

HASH_FILE = ".backup_hash"
_SKIP_DIRS = {'.git', '__pycache__'}
_SKIP_FILES = {'.DS_Store', 'Thumbs.db'}


def _folder_hash(mod_path):
    hasher = hashlib.sha256()
    for root, dirs, files in os.walk(mod_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for f in sorted(files):
            if f in _SKIP_FILES:
                continue
            path = os.path.join(root, f)
            rel = os.path.relpath(path, mod_path)
            try:
                st = os.stat(path)
            except OSError:
                continue
            hasher.update(rel.encode())
            hasher.update(str(st.st_size).encode())
            hasher.update(str(st.st_mtime_ns).encode())
    return hasher.hexdigest()


def _read_stored_hash(backup_mod_path):
    path = os.path.join(backup_mod_path, HASH_FILE)
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _write_hash(backup_mod_path, h):
    os.makedirs(backup_mod_path, exist_ok=True)
    with open(os.path.join(backup_mod_path, HASH_FILE), "w") as f:
        f.write(h)


def backup_needed(mod_folder, mods_path, backup_root):
    mod_path = os.path.join(mods_path, mod_folder)
    if not os.path.isdir(mod_path):
        return False
    backup_mod_path = os.path.join(backup_root, mod_folder)
    current = _folder_hash(mod_path)
    stored = _read_stored_hash(backup_mod_path)
    return current != stored


def backup_mod(mod_folder, mods_path, backup_root):
    mod_path = os.path.join(mods_path, mod_folder)
    backup_mod_path = os.path.join(backup_root, mod_folder)
    if not os.path.isdir(mod_path):
        return
    shutil.copytree(
        mod_path,
        backup_mod_path,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns('.git', '__pycache__', '.DS_Store', 'Thumbs.db'),
    )
    h = _folder_hash(mod_path)
    _write_hash(backup_mod_path, h)


def backup_all(mods_path, backup_root, loaded_mods):
    os.makedirs(backup_root, exist_ok=True)
    for name, folder in loaded_mods:
        if backup_needed(folder, mods_path, backup_root):
            backup_mod(folder, mods_path, backup_root)


def get_backup_root(mods_path):
    parent = os.path.dirname(os.path.normpath(mods_path))
    return os.path.join(parent, "backup")
