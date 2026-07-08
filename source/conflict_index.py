"""Persistent mod folder fingerprinting for conflict-detection cache invalidation.

On each launch the fingerprint of every enabled mod is compared against the
value stored in the database.  If it hasn't changed the cached file list is
re-used, avoiding a full filesystem walk of that mod.
"""

from __future__ import annotations

import json
import os
import time
from hashlib import blake2b

from . import config, database

# Must match modlist.py _CONFLICT_EXTS
_CONFLICT_EXTS = {".png", ".anm2", ".wav", ".lua"}


def _fingerprint_folder(mod_path: str,
                        ignored_items: list) -> tuple[str, set[str]]:
    """Walk *mod_path* and return (blake2b_hexdigest, set_of_relative_paths)."""
    h = blake2b()
    files: set[str] = set()
    try:
        for root, dirs, fnames in os.walk(mod_path):
            dirs[:] = [d for d in dirs if d not in ignored_items]
            for fname in fnames:
                if fname in ignored_items:
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if ext not in _CONFLICT_EXTS:
                    continue
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, mod_path)
                if "/" not in rel and "\\" not in rel:
                    continue
                files.add(rel)
                try:
                    mtime = os.path.getmtime(full)
                except OSError:
                    mtime = 0.0
                h.update(f"{rel}\0{mtime}\0".encode())
    except OSError:
        pass
    return h.hexdigest(), files


def get_cached_files(folder: str) -> set[str]:
    """Return the set of conflict-relevant relative paths for *folder*.

    Uses the database fingerprint cache to avoid re-walking mods that
    haven't changed since the last time they were indexed.
    """
    full_path = os.path.join(config.mods_path, folder)

    # -- quick token: directory mtime + top-level entry list ---------------
    try:
        cur_token = _quick_token(full_path, config.ignored_items)
    except OSError:
        database.delete_mod_fingerprint(folder)
        return set()

    row = database.get_mod_fingerprint(folder)
    if row is not None and row.get("token") == cur_token:
        return set(json.loads(row["files_json"]))

    # -- full walk ---------------------------------------------------------
    fp, files = _fingerprint_folder(full_path, config.ignored_items)
    database.set_mod_fingerprint(folder, fp, sorted(files), cur_token)
    return files


def invalidate(folder: str) -> None:
    """Remove the cached fingerprint for *folder* (e.g. after rename/delete)."""
    database.delete_mod_fingerprint(folder)


def _quick_token(mod_path: str, ignored_items: list) -> str:
    """Lightweight directory-state token that changes when contents change.

    Combines directory mtime with a sorted list of top-level entry names
    and their individual mtimes so that adding, removing or modifying
    files (even in subdirectories) is detected without a full recursive walk.
    """
    h = blake2b()
    try:
        h.update(f"{os.path.getmtime(mod_path)}\0".encode())
    except OSError:
        h.update(b"0\0")
    try:
        entries = sorted(os.listdir(mod_path))
    except OSError:
        entries = []
    for entry in entries:
        if entry in ignored_items:
            continue
        h.update(entry.encode() + b"\0")
        try:
            h.update(f"{os.path.getmtime(os.path.join(mod_path, entry))}\0".encode())
        except OSError:
            h.update(b"0\0")
    return h.hexdigest()
