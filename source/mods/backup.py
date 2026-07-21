"""Mod backup and restore functionality."""

from __future__ import annotations

import os
import shutil
import sys
import xml.etree.ElementTree as ET

from packaging.version import InvalidVersion, Version

from ..core import config, paths


def _read_version(mod_folder: str, mods_path: str) -> str:
    xml_path = os.path.join(mods_path, mod_folder, "metadata.xml")
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        version_el = root.find("version")
        return (
            version_el.text.strip()
            if version_el is not None and version_el.text
            else "?"
        )
    except ET.ParseError, FileNotFoundError, AttributeError:
        return "?"


def _versions_differ(a: str, b: str) -> bool:
    try:
        return Version(a) != Version(b)
    except InvalidVersion:
        return a != b


def _classify_magnitude(old: str, new: str) -> str:
    try:
        vo = Version(old)
        vn = Version(new)
        if vo.major != vn.major:
            return "major"
        if vo.minor != vn.minor:
            return "minor"
        return "patch"
    except InvalidVersion:
        return "?"


def backup_needed(mod_folder: str, mods_path: str, backup_root: str) -> bool:
    full_mod_path = os.path.join(mods_path, mod_folder)
    if not os.path.isdir(full_mod_path):
        return False
    current_version = _read_version(mod_folder, mods_path)
    backup_mod_path = os.path.join(backup_root, mod_folder)
    if not os.path.isdir(backup_mod_path):
        return True
    backup_version = _read_version(mod_folder, backup_root)
    return _versions_differ(current_version, backup_version)


def backup_mod(mod_folder: str, mods_path: str, backup_root: str) -> None:
    full_mod_path = os.path.join(mods_path, mod_folder)
    backup_mod_path = os.path.join(backup_root, mod_folder)
    if not os.path.isdir(full_mod_path):
        return
    shutil.copytree(
        full_mod_path,
        backup_mod_path,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            ".git", "__pycache__", ".DS_Store", "Thumbs.db", "MERGED"
        ),
    )


def backup_all(
    mods_path: str,
    backup_root: str,
    mod_list: list,
) -> list[tuple[str, str, str, str]]:
    os.makedirs(backup_root, exist_ok=True)
    results: list[tuple[str, str, str, str]] = []
    for mod_name, mod_folder in mod_list:
        if backup_needed(mod_folder, mods_path, backup_root):
            old_version = _read_version(mod_folder, backup_root)
            backup_mod(mod_folder, mods_path, backup_root)
            new_version = _read_version(mod_folder, mods_path)
            magnitude = _classify_magnitude(old_version, new_version)
            results.append((mod_name, old_version, new_version, magnitude))
    return results


def get_backup_root(mods_path: str) -> str:
    if config.backup_path:
        return config.backup_path
    if sys.platform == "darwin":
        return os.path.join(paths.config_dir, "backup")
    parent_directory = os.path.dirname(os.path.normpath(mods_path))
    return os.path.join(parent_directory, "backup")
