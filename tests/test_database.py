"""Tests for source/database.py."""

from __future__ import annotations

import json
import os
import sqlite3

import pytest

from source import database


@pytest.fixture(autouse=True)
def _in_memory_db(monkeypatch: pytest.MonkeyPatch, tmp_path: str) -> sqlite3.Connection:
    """Use a temp-file DB so the real DB file is never touched."""
    db_path = os.path.join(tmp_path, "test.db")
    monkeypatch.setattr(database, "_path", lambda: db_path)
    database._DB = None
    database.init()
    conn = database._conn()
    conn.executescript("DELETE FROM workshop_items; DELETE FROM load_order_history; DELETE FROM mod_fingerprints;")
    return conn


class TestInit:
    def test_tables_created(self, _in_memory_db: sqlite3.Connection) -> None:
        cursor = _in_memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert "workshop_items" in tables
        assert "load_order_history" in tables
        assert "mod_fingerprints" in tables


class TestWorkshopItems:
    def test_upsert_and_get(self, _in_memory_db: sqlite3.Connection) -> None:
        database.upsert_workshop_item(12345, title="Test Mod", description="A test")
        item = database.get_workshop_item(12345)
        assert item is not None
        assert item["title"] == "Test Mod"

    def test_get_missing_returns_none(self, _in_memory_db: sqlite3.Connection) -> None:
        assert database.get_workshop_item(99999) is None

    def test_all_workshop_items(self, _in_memory_db: sqlite3.Connection) -> None:
        database.upsert_workshop_item(1, title="A")
        database.upsert_workshop_item(2, title="B")
        items = database.all_workshop_items()
        assert len(items) == 2

    def test_upsert_updates_existing(self, _in_memory_db: sqlite3.Connection) -> None:
        database.upsert_workshop_item(1, title="Original")
        database.upsert_workshop_item(1, title="Updated")
        item = database.get_workshop_item(1)
        assert item["title"] == "Updated"


class TestDeadWorkshop:
    def test_mark_and_get_dead(self, _in_memory_db: sqlite3.Connection) -> None:
        database.upsert_workshop_item(1, title="Dead Mod")
        database.mark_workshop_dead(1)
        dead = database.get_dead_workshop_ids()
        assert 1 in dead

    def test_get_dead_returns_empty_set_initially(self, _in_memory_db: sqlite3.Connection) -> None:
        assert database.get_dead_workshop_ids() == set()


class TestLoadOrder:
    def test_save_and_load(self, _in_memory_db: sqlite3.Connection) -> None:
        order = ["mod_a", "mod_b", "mod_c"]
        database.save_load_order(order)
        loaded = database.load_latest_order()
        assert loaded == order

    def test_load_returns_none_when_empty(self, _in_memory_db: sqlite3.Connection) -> None:
        assert database.load_latest_order() is None

    def test_save_overwrites_previous(self, _in_memory_db: sqlite3.Connection) -> None:
        database.save_load_order(["old"])
        database.save_load_order(["new"])
        loaded = database.load_latest_order()
        assert loaded == ["new"]


class TestModFingerprints:
    def test_set_and_get(self, _in_memory_db: sqlite3.Connection) -> None:
        database.set_mod_fingerprint("mod_folder", "abc123", ["file1.png", "file2.lua"], "quick_token_1")
        fp = database.get_mod_fingerprint("mod_folder")
        assert fp is not None
        assert fp["fingerprint"] == "abc123"
        assert json.loads(fp["files_json"]) == ["file1.png", "file2.lua"]
        assert fp["token"] == "quick_token_1"

    def test_get_missing_returns_none(self, _in_memory_db: sqlite3.Connection) -> None:
        assert database.get_mod_fingerprint("nonexistent") is None

    def test_delete(self, _in_memory_db: sqlite3.Connection) -> None:
        database.set_mod_fingerprint("mod", "fp", ["f"], "t")
        database.delete_mod_fingerprint("mod")
        assert database.get_mod_fingerprint("mod") is None

    def test_update_existing(self, _in_memory_db: sqlite3.Connection) -> None:
        database.set_mod_fingerprint("mod", "old_fp", ["old"], "old_t")
        database.set_mod_fingerprint("mod", "new_fp", ["new"], "new_t")
        fp = database.get_mod_fingerprint("mod")
        assert fp["fingerprint"] == "new_fp"
