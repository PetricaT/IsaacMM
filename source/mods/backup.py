"""Mod backup and restore functionality."""

from __future__ import annotations

import os
import shutil
import sys
import tarfile
import zipfile
from datetime import datetime
from typing import Optional

import xml.etree.ElementTree as ET

from packaging.version import InvalidVersion, Version

from ..core import config, paths


_IGNORE_PATTERNS = {".git", "__pycache__", ".DS_Store", "Thumbs.db", "MERGED"}

_ARCHIVE_SUFFIXES = {
    "zip": ".zip",
    "tar.gz": ".tar.gz",
    "tar.xz": ".tar.xz",
    "7z": ".7z",
}


# ---- helpers ----------------------------------------------------------------


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
    except (ET.ParseError, FileNotFoundError, AttributeError):
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


# ---- archive helpers ---------------------------------------------------------


def get_available_formats() -> list[str]:
    formats = ["zip", "tar.gz", "tar.xz"]
    try:
        import py7zr  # noqa
        formats.append("7z")
    except ImportError:
        pass
    return formats


def _detect_best_format() -> str:
    try:
        import py7zr  # noqa
        return "7z"
    except ImportError:
        pass
    return "tar.xz"


def _resolve_format(fmt: str) -> str:
    if fmt == "auto":
        return _detect_best_format()
    if fmt not in _ARCHIVE_SUFFIXES:
        return "zip"
    return fmt


def _archive_suffix(fmt: str) -> str:
    return _ARCHIVE_SUFFIXES.get(fmt, ".zip")


def _should_ignore(name: str) -> bool:
    return name in _IGNORE_PATTERNS


def _listdir(path: str) -> list[str]:
    try:
        return os.listdir(path)
    except FileNotFoundError:
        return []


def _create_archive(source_dir: str, dest_path: str, fmt: str) -> None:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    items = [n for n in _listdir(source_dir) if not _should_ignore(n)]

    if fmt == "zip":
        with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in items:
                full = os.path.join(source_dir, item)
                if os.path.isdir(full):
                    for root, dirs, files in os.walk(full):
                        dirs[:] = [d for d in dirs if not _should_ignore(d)]
                        for f in files:
                            if _should_ignore(f):
                                continue
                            fp = os.path.join(root, f)
                            zf.write(fp, os.path.relpath(fp, source_dir))
                else:
                    zf.write(full, item)
        return

    mode = {"tar.gz": "w:gz", "tar.xz": "w:xz"}.get(fmt)
    if mode:
        with tarfile.open(dest_path, mode) as tar:
            for item in items:
                full = os.path.join(source_dir, item)
                tar.add(full, arcname=item, filter=_tar_filter)
        return

    if fmt == "7z":
        import py7zr

        with py7zr.SevenZipFile(dest_path, "w") as sz:
            for item in items:
                full = os.path.join(source_dir, item)
                if os.path.isdir(full):
                    sz.writeall(full, arcname=item)
                else:
                    sz.write(full, arcname=item)


def _tar_filter(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
    if _should_ignore(os.path.basename(tarinfo.name)):
        return None
    return tarinfo


# ---- reading version from archives -------------------------------------------


def _read_archived_version(mod_folder: str, backup_root: str, fmt: str) -> str:
    mod_backup_dir = os.path.join(backup_root, mod_folder)
    suffix = _archive_suffix(fmt)
    prefix = f"{mod_folder}_"

    archives = sorted(
        f for f in _listdir(mod_backup_dir)
        if f.startswith(prefix) and f.endswith(suffix)
    )
    if not archives:
        return "?"

    latest = os.path.join(mod_backup_dir, archives[-1])

    try:
        if fmt == "zip":
            with zipfile.ZipFile(latest, "r") as zf:
                try:
                    data = zf.read("metadata.xml")
                except KeyError:
                    return "?"
                return _parse_xml_version(data)

        if fmt in ("tar.gz", "tar.xz"):
            with tarfile.open(latest, "r") as tar:
                try:
                    member = tar.getmember("metadata.xml")
                    f = tar.extractfile(member)
                    if f is None:
                        return "?"
                    data = f.read()
                except KeyError:
                    return "?"
                return _parse_xml_version(data)

        if fmt == "7z":
            import py7zr

            with py7zr.SevenZipFile(latest, "r") as sz:
                data = sz.read("metadata.xml")
                buf = data.get("metadata.xml")
                if buf is None:
                    return "?"
                return _parse_xml_version(buf.read())
    except Exception:
        return "?"
    return "?"


def _parse_xml_version(data: bytes) -> str:
    try:
        root = ET.fromstring(data)
        version_el = root.find("version")
        return version_el.text.strip() if version_el is not None and version_el.text else "?"
    except (ET.ParseError, AttributeError):
        return "?"


# ---- backup size -------------------------------------------------------------


def get_backup_size(backup_root: str) -> int:
    total = 0
    try:
        for root, _dirs, files in os.walk(backup_root):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    except FileNotFoundError:
        pass
    return total


def format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ---- backup needed -----------------------------------------------------------


def backup_needed(mod_folder: str, mods_path: str, backup_root: str) -> bool:
    full_mod_path = os.path.join(mods_path, mod_folder)
    if not os.path.isdir(full_mod_path):
        return False
    current_version = _read_version(mod_folder, mods_path)
    if config.backup_archive_enabled:
        fmt = _resolve_format(config.backup_archive_format)
        backup_version = _read_archived_version(mod_folder, backup_root, fmt)
    else:
        backup_mod_path = os.path.join(backup_root, mod_folder)
        if not os.path.isdir(backup_mod_path):
            return True
        backup_version = _read_version(mod_folder, backup_root)
    return _versions_differ(current_version, backup_version)


# ---- archived backup with retention -----------------------------------------


def _backup_mod_archived(
    mod_folder: str, mods_path: str, backup_root: str, fmt: str, max_keep: int
) -> None:
    full_mod_path = os.path.join(mods_path, mod_folder)
    if not os.path.isdir(full_mod_path):
        return

    mod_backup_dir = os.path.join(backup_root, mod_folder)
    os.makedirs(mod_backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = _archive_suffix(fmt)
    archive_name = f"{mod_folder}_{timestamp}{suffix}"
    archive_path = os.path.join(mod_backup_dir, archive_name)

    _create_archive(full_mod_path, archive_path, fmt)

    _prune_backups(mod_backup_dir, mod_folder, suffix, max_keep)


def _prune_backups(mod_backup_dir: str, mod_folder: str, suffix: str, max_keep: int) -> None:
    prefix = f"{mod_folder}_"
    archives = sorted(
        f for f in _listdir(mod_backup_dir)
        if f.startswith(prefix) and f.endswith(suffix)
    )
    while len(archives) > max_keep:
        oldest = archives.pop(0)
        try:
            os.remove(os.path.join(mod_backup_dir, oldest))
        except OSError:
            pass


# ---- plain backup (directory copy) ------------------------------------------


def backup_mod(mod_folder: str, mods_path: str, backup_root: str) -> None:
    full_mod_path = os.path.join(mods_path, mod_folder)
    backup_mod_path = os.path.join(backup_root, mod_folder)
    if not os.path.isdir(full_mod_path):
        return
    shutil.copytree(
        full_mod_path,
        backup_mod_path,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*_IGNORE_PATTERNS),
    )


# ---- backup_all dispatches to archived or plain -----------------------------


def backup_all(
    mods_path: str,
    backup_root: str,
    mod_list: list,
    progress_cb=None,
) -> list[tuple[str, str, str, str]]:
    os.makedirs(backup_root, exist_ok=True)
    results: list[tuple[str, str, str, str]] = []
    total = len(mod_list)
    for i, (mod_name, mod_folder) in enumerate(mod_list):
        if progress_cb is not None:
            progress_cb(i, total, f"Archiving mods ({i}/{total})...")
        if backup_needed(mod_folder, mods_path, backup_root):
            if config.backup_archive_enabled:
                old_version = _read_archived_version(
                    mod_folder, backup_root, _resolve_format(config.backup_archive_format)
                )
            else:
                old_version = _read_version(mod_folder, backup_root)

            if config.backup_archive_enabled:
                fmt = _resolve_format(config.backup_archive_format)
                _backup_mod_archived(
                    mod_folder, mods_path, backup_root, fmt, config.backup_max_keep
                )
            else:
                backup_mod(mod_folder, mods_path, backup_root)

            new_version = _read_version(mod_folder, mods_path)
            magnitude = _classify_magnitude(old_version, new_version)
            results.append((mod_name, old_version, new_version, magnitude))
    if progress_cb is not None:
        progress_cb(total, total, "Archiving mods...")
    return results


# ---- get_backup_root (unchanged) ---------------------------------------------


def get_backup_root(mods_path: str) -> str:
    if config.backup_path:
        return config.backup_path
    if sys.platform == "darwin":
        return os.path.join(paths.config_dir, "backup")
    parent_directory = os.path.dirname(os.path.normpath(mods_path))
    return os.path.join(parent_directory, "backup")
