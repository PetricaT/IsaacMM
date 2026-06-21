import hashlib
import os
import shutil
from typing import Optional

HASH_FILE: str = ".backup_hash"
_SKIP_DIRS: set[str] = {'.git', '__pycache__'}
_SKIP_FILES: set[str] = {'.DS_Store', 'Thumbs.db'}


def _folder_hash(mod_path: str) -> str:
    hasher = hashlib.sha256()
    for root, walk_dirs, file_names in os.walk(mod_path):
        walk_dirs[:] = [directory for directory in walk_dirs if directory not in _SKIP_DIRS]
        for file_name in sorted(file_names):
            if file_name in _SKIP_FILES:
                continue
            file_path = os.path.join(root, file_name)
            relative_path = os.path.relpath(file_path, mod_path)
            try:
                stat_result = os.stat(file_path)
            except OSError:
                continue
            hasher.update(relative_path.encode())
            hasher.update(str(stat_result.st_size).encode())
            hasher.update(str(stat_result.st_mtime_ns).encode())
    return hasher.hexdigest()


def _read_stored_hash(backup_mod_path: str) -> Optional[str]:
    hash_file_path = os.path.join(backup_mod_path, HASH_FILE)
    try:
        with open(hash_file_path) as hash_file:
            return hash_file.read().strip()
    except OSError:
        return None


def _write_hash(backup_mod_path: str, hash_digest: str) -> None:
    os.makedirs(backup_mod_path, exist_ok=True)
    with open(os.path.join(backup_mod_path, HASH_FILE), "w") as hash_file:
        hash_file.write(hash_digest)


def backup_needed(mod_folder: str, mods_path: str, backup_root: str) -> bool:
    full_mod_path = os.path.join(mods_path, mod_folder)
    if not os.path.isdir(full_mod_path):
        return False
    backup_mod_path = os.path.join(backup_root, mod_folder)
    current_hash = _folder_hash(full_mod_path)
    stored_hash = _read_stored_hash(backup_mod_path)
    return current_hash != stored_hash


def backup_mod(mod_folder: str, mods_path: str, backup_root: str) -> None:
    full_mod_path = os.path.join(mods_path, mod_folder)
    backup_mod_path = os.path.join(backup_root, mod_folder)
    if not os.path.isdir(full_mod_path):
        return
    shutil.copytree(
        full_mod_path,
        backup_mod_path,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns('.git', '__pycache__', '.DS_Store', 'Thumbs.db'),
    )
    hash_digest = _folder_hash(full_mod_path)
    _write_hash(backup_mod_path, hash_digest)


def backup_all(mods_path: str, backup_root: str, mod_list: list) -> None:
    os.makedirs(backup_root, exist_ok=True)
    for mod_name, mod_folder in mod_list:
        if backup_needed(mod_folder, mods_path, backup_root):
            backup_mod(mod_folder, mods_path, backup_root)


def get_backup_root(mods_path: str) -> str:
    parent_directory = os.path.dirname(os.path.normpath(mods_path))
    return os.path.join(parent_directory, "backup")
