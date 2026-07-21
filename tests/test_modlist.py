"""Tests for source/components/modlist.py."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import pytest

from source.components.modlist import (
    SEPARATOR_SUFFIX,
    _scan_mods_directory,
    normalize_mod_name,
)


class TestNormalizeModName:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("  Some Mod  ", "Some Mod"),
            ("123Some Mod", "Some Mod"),
            ("!!!Hello", "Hello"),
            ("AlreadyClean", "AlreadyClean"),
            ("", ""),
        ],
    )
    def test_normalizes_correctly(self, name: str, expected: str) -> None:
        assert normalize_mod_name(name) == expected


class TestScanModsDirectory:
    @staticmethod
    def _make_mod(tmp_path: str, folder: str, name: str) -> str:
        """Create a mod folder with metadata.xml and return its path."""
        path = os.path.join(tmp_path, folder)
        os.makedirs(path)
        metadata = ET.Element("metadata")
        name_elem = ET.SubElement(metadata, "name")
        name_elem.text = name
        ET.ElementTree(metadata).write(os.path.join(path, "metadata.xml"))
        return path

    def test_returns_empty_entries_for_empty_dir(self, tmp_path: str) -> None:
        result = _scan_mods_directory(tmp_path, [])
        assert result["entries"] == []

    def test_discovers_mods(self, tmp_path: str) -> None:
        self._make_mod(tmp_path, "MyMod", "My Amazing Mod")
        result = _scan_mods_directory(tmp_path, [])
        assert len(result["entries"]) == 1
        entry = result["entries"][0]
        assert entry[1] == "MyMod"  # folder_name

    def test_skips_ignored_items(self, tmp_path: str) -> None:
        os.makedirs(os.path.join(tmp_path, ".git"))
        os.makedirs(os.path.join(tmp_path, "__pycache__"))
        self._make_mod(tmp_path, "RealMod", "Real Mod")
        ignored = [".git", "__pycache__"]
        result = _scan_mods_directory(tmp_path, ignored)
        entries = result["entries"]
        folder_names = [e[1] for e in entries]
        assert ".git" not in folder_names
        assert "__pycache__" not in folder_names
        assert "RealMod" in folder_names

    def test_detects_separators(self, tmp_path: str) -> None:
        sep_dir = os.path.join(tmp_path, f"Separator{SEPARATOR_SUFFIX}")
        os.makedirs(sep_dir)
        sep_xml = ET.Element("separator")
        name_elem = ET.SubElement(sep_xml, "name")
        name_elem.text = "My Separator"
        ET.ElementTree(sep_xml).write(os.path.join(sep_dir, "separator.xml"))
        result = _scan_mods_directory(tmp_path, [])
        assert result["separator_map"] != {}
        sep_key = f"Separator{SEPARATOR_SUFFIX}"
        assert sep_key in result["separator_map"]

    def test_skips_non_directories(self, tmp_path: str) -> None:
        open(os.path.join(tmp_path, "file.txt"), "w").close()
        result = _scan_mods_directory(tmp_path, [])
        assert result["entries"] == []

    def test_handles_os_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _broken_listdir(_path: str) -> None:
            raise OSError("Permission denied")

        monkeypatch.setattr(os, "listdir", _broken_listdir)
        result = _scan_mods_directory("/nonexistent", [])
        assert "error" in result
