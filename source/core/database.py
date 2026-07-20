"""Single DB access layer for persistent state.

Schema versioning: MIGRATIONS dict maps version → migration function.
On every launch, run any pending migrations in order.
Each migration must be idempotent and wrapped in a transaction.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Callable, Optional

from . import logger, paths

_DB: Optional[sqlite3.Connection] = None
_DB_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


def _path() -> str:
    return os.path.join(paths.appdata, "isaacmm.db")


def _conn() -> sqlite3.Connection:
    global _DB
    if _DB is None:
        _DB = sqlite3.connect(_path(), check_same_thread=False)
        _DB.row_factory = sqlite3.Row
        _DB.execute("PRAGMA journal_mode=WAL")
        _DB.execute("PRAGMA foreign_keys=ON")
    return _DB


# ---------------------------------------------------------------------------
# Migration framework
# ---------------------------------------------------------------------------

MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {}


def _migrate_v1(conn: sqlite3.Connection) -> None:
    """Import old data from last_order.yaml and workshop_details.json."""
    migrated = False

    last_order_yaml = os.path.join(paths.appdata, "last_order.yaml")
    if os.path.isfile(last_order_yaml):
        try:
            import yaml
            with open(last_order_yaml) as f:
                data = yaml.safe_load(f)
            folders = (data or {}).get("ordered_folders", [])
            if folders:
                now = time.time()
                conn.execute(
                    "INSERT INTO load_order_history (timestamp, order_json, label) VALUES (?, ?, ?)",
                    (now, json.dumps(folders), "migrated"),
                )
                migrated = True
        except Exception as exc:
            logger.log("warning", f"DB migration v1: failed to read {last_order_yaml}: {exc}")

    details_json = os.path.join(paths.cache_dir, "workshop_details.json")
    if os.path.isfile(details_json):
        try:
            with open(details_json) as f:
                details = json.load(f)
            for ws_id_str, data in details.items():
                try:
                    ws_id = int(ws_id_str)
                except (ValueError, TypeError):
                    continue
                conn.execute(
                    """INSERT OR IGNORE INTO workshop_items
                       (id, created_at, updated_at) VALUES (?, ?, ?)""",
                    (ws_id, data.get("time_created"), data.get("time_updated")),
                )
            migrated = True
        except Exception as exc:
            logger.log("warning", f"DB migration v1: failed to read {details_json}: {exc}")

    if not migrated:
        conn.execute("INSERT INTO load_order_history (timestamp, order_json, label) VALUES (?, ?, ?)",
                      (time.time(), "[]", "init"))


MIGRATIONS[1] = _migrate_v1


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """Add mod_fingerprints table for CONFLICT-INDEX cache invalidation."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mod_fingerprints (
            folder TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            files_json TEXT NOT NULL DEFAULT '[]',
            token TEXT NOT NULL DEFAULT '',
            updated_at REAL NOT NULL
        )
    """)


MIGRATIONS[2] = _migrate_v2


def init() -> None:
    """Create tables if needed and run any pending schema migrations."""
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS workshop_items (
            id INTEGER PRIMARY KEY,
            title TEXT DEFAULT '',
            preview_url TEXT DEFAULT '',
            description TEXT DEFAULT '',
            created_at REAL,
            updated_at REAL,
            status TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS load_order_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            order_json TEXT NOT NULL,
            label TEXT DEFAULT ''
        );
    """)
    conn.commit()

    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for ver, fn in sorted(MIGRATIONS.items()):
        if ver > current:
            try:
                conn.execute("BEGIN")
                fn(conn)
                conn.execute(f"PRAGMA user_version = {ver}")
                conn.commit()
                logger.log("info", f"DB migrated to schema v{ver}")
            except Exception:
                conn.rollback()
                logger.log("error", f"DB migration to v{ver} failed, rolling back")
                raise


# ---------------------------------------------------------------------------
# Workshop items
# ---------------------------------------------------------------------------


def get_workshop_item(ws_id: int) -> Optional[dict]:
    row = _conn().execute(
        "SELECT * FROM workshop_items WHERE id = ?", (ws_id,)
    ).fetchone()
    return dict(row) if row else None


def upsert_workshop_item(ws_id: int, **fields) -> None:
    cols = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    updates = ", ".join(f"{k} = excluded.{k}" for k in fields)
    values = tuple(fields.values())
    with _DB_LOCK:
        _conn().execute(
            f"INSERT INTO workshop_items (id, {cols}) VALUES (?, {placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            (ws_id, *values),
        )
        _conn().commit()


def all_workshop_items() -> list[dict]:
    return [dict(r) for r in _conn().execute("SELECT * FROM workshop_items").fetchall()]


# ---------------------------------------------------------------------------
# Workshop item status helpers
# ---------------------------------------------------------------------------


def get_dead_workshop_ids() -> set[int]:
    rows = _conn().execute(
        "SELECT id FROM workshop_items WHERE status = 'dead'"
    ).fetchall()
    return {r["id"] for r in rows}


def mark_workshop_dead(ws_id: int) -> None:
    with _DB_LOCK:
        _conn().execute(
            "INSERT INTO workshop_items (id, status) VALUES (?, 'dead') "
            "ON CONFLICT(id) DO UPDATE SET status = 'dead'",
            (ws_id,),
        )
        _conn().commit()


# ---------------------------------------------------------------------------
# Load order history
# ---------------------------------------------------------------------------


def save_load_order(folder_order: list) -> None:
    with _DB_LOCK:
        now = time.time()
        _conn().execute(
            "INSERT INTO load_order_history (timestamp, order_json) VALUES (?, ?)",
            (now, json.dumps(folder_order)),
        )
        _conn().execute(
            "DELETE FROM load_order_history WHERE id NOT IN (SELECT id FROM load_order_history ORDER BY id DESC LIMIT 50)"
        )
        _conn().commit()


def load_latest_order() -> Optional[list]:
    row = _conn().execute(
        "SELECT order_json FROM load_order_history ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row["order_json"])
    except (json.JSONDecodeError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Mod fingerprints (CONFLICT-INDEX cache)
# ---------------------------------------------------------------------------


def get_mod_fingerprint(folder: str) -> Optional[dict]:
    row = _conn().execute(
        "SELECT fingerprint, files_json, token FROM mod_fingerprints WHERE folder = ?",
        (folder,),
    ).fetchone()
    return dict(row) if row else None


def set_mod_fingerprint(folder: str, fingerprint: str, files: list, token: str) -> None:
    with _DB_LOCK:
        _conn().execute(
            """INSERT INTO mod_fingerprints (folder, fingerprint, files_json, token, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(folder) DO UPDATE SET
                   fingerprint = excluded.fingerprint,
                   files_json = excluded.files_json,
                   token = excluded.token,
                   updated_at = excluded.updated_at""",
            (folder, fingerprint, json.dumps(files), token, time.time()),
        )
        _conn().commit()


def delete_mod_fingerprint(folder: str) -> None:
    with _DB_LOCK:
        _conn().execute("DELETE FROM mod_fingerprints WHERE folder = ?", (folder,))
        _conn().commit()
