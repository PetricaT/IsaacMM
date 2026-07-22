"""Tests for source/mods/backup.py."""

from __future__ import annotations

import os
import tarfile
import zipfile
import xml.etree.ElementTree as ET

import pytest


# ---- Bootstrap: inject mocks BEFORE any source import -----------------------
import sys
import types

# Ensure source package structure exists in sys.modules so relative imports work
for pkg in ("source", "source.mods", "source.core", "source.updater", "source.ui",
            "source.ui.dialogs", "source.theme", "source.controller"):
    if pkg not in sys.modules:
        mod = types.ModuleType(pkg)
        mod.__path__ = [pkg.replace(".", "/")]
        mod.__package__ = pkg
        sys.modules[pkg] = mod

# Mock PySide6
pyside = types.ModuleType("PySide6")
pyside.QtCore = types.ModuleType("PySide6.QtCore")
pyside.QtCore.QSettings = type("QSettings", (), {})
pyside.QtCore.Signal = type("Signal", (), {})
pyside.QtCore.Qt = type("Qt", (), {"AlignmentFlag": type("AF", (), {})})()
sys.modules["PySide6"] = pyside
sys.modules["PySide6.QtCore"] = pyside.QtCore

# Mock toml
toml = types.ModuleType("toml")
toml.load = lambda f: {}
toml.dump = lambda d, f: None
sys.modules["toml"] = toml

# Mock loguru
loguru = types.ModuleType("loguru")
loguru.logger = type("Logger", (), {"opt": lambda self, **kw: self, "info": lambda *a, **kw: None, "debug": lambda *a, **kw: None, "warning": lambda *a, **kw: None, "error": lambda *a, **kw: None, "critical": lambda *a, **kw: None, "trace": lambda *a, **kw: None, "remove": lambda *a, **kw: None, "add": lambda *a, **kw: None})()
sys.modules["loguru"] = loguru

# Mock httpx
httpx = types.ModuleType("httpx")
httpx.RequestError = type("RequestError", (Exception,), {})
httpx.Client = type("Client", (), {"__enter__": lambda s: s, "__exit__": lambda *a: None, "get": lambda *a, **kw: type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: {}})(), "stream": lambda *a, **kw: type("S", (), {"__enter__": lambda s: s, "__exit__": lambda *a: None, "__iter__": lambda s: iter([]), "iter_bytes": lambda s, **kw: iter([]), "headers": {}})()})
sys.modules["httpx"] = httpx

# Mock tenacity
tenacity = types.ModuleType("tenacity")
sys.modules["tenacity"] = tenacity

# Mock source.core.database so config.py can load
source_core_db = types.ModuleType("source.core.database")
source_core_db._DB = None
source_core_db.init = lambda: None
sys.modules["source.core.database"] = source_core_db

# Mock source.mods.sorter so config.py can load
source_mods_sorter = types.ModuleType("source.mods.sorter")
sys.modules["source.mods.sorter"] = source_mods_sorter

# Load core modules via importlib (avoid source.__init__ which triggers full chain)
import importlib

config_spec = importlib.util.spec_from_file_location("source.core.config", "source/core/config.py")
config = importlib.util.module_from_spec(config_spec)
sys.modules["source.core.config"] = config
config_spec.loader.exec_module(config)

paths_spec = importlib.util.spec_from_file_location("source.core.paths", "source/core/paths.py")
paths = importlib.util.module_from_spec(paths_spec)
sys.modules["source.core.paths"] = paths
paths_spec.loader.exec_module(paths)

# Minimal config values
config.mods_path = ""
config.backup_path = None
config.backup_enabled = False
config.backup_archive_enabled = False
config.backup_archive_format = "auto"
config.backup_max_keep = 2

backup_spec = importlib.util.spec_from_file_location("source.mods.backup", "source/mods/backup.py")
backup = importlib.util.module_from_spec(backup_spec)
sys.modules["source.mods.backup"] = backup
backup_spec.loader.exec_module(backup)


# ---- helpers ----------------------------------------------------------------


def _make_fake_mod(tmp_path: str, mod_name: str, version: str) -> str:
    mod_dir = os.path.join(tmp_path, mod_name)
    os.makedirs(mod_dir, exist_ok=True)
    metadata = ET.Element("metadata")
    version_elem = ET.SubElement(metadata, "version")
    version_elem.text = version
    ET.ElementTree(metadata).write(os.path.join(mod_dir, "metadata.xml"))
    with open(os.path.join(mod_dir, "main.lua"), "w") as f:
        f.write("-- test")
    return mod_dir


# ---- existing tests ---------------------------------------------------------


class TestVersionsDiffer:
    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ("1.0.0", "1.0.1", True),
            ("1.0.0", "1.0.0", False),
            ("v1.0.0", "1.0.0", False),
            ("", "1.0.0", True),
        ],
    )
    def test_detects_differences(self, a: str, b: str, expected: bool) -> None:
        assert backup._versions_differ(a, b) is expected


class TestClassifyMagnitude:
    @pytest.mark.parametrize(
        ("old", "new", "expected"),
        [
            ("1.0.0", "2.0.0", "major"),
            ("1.0.0", "1.1.0", "minor"),
            ("1.0.0", "1.0.1", "patch"),
            ("1.0.0", "1.0.0", "patch"),
            ("abc", "def", "?"),
        ],
    )
    def test_classifies_correctly(self, old: str, new: str, expected: str) -> None:
        assert backup._classify_magnitude(old, new) == expected


class TestReadVersion:
    def test_reads_from_metadata_xml(self, tmp_path: str) -> None:
        mod_dir = os.path.join(tmp_path, "test_mod")
        os.makedirs(mod_dir)
        metadata = ET.Element("metadata")
        version_elem = ET.SubElement(metadata, "version")
        version_elem.text = "1.2.3"
        ET.ElementTree(metadata).write(os.path.join(mod_dir, "metadata.xml"))
        result = backup._read_version(mod_dir, tmp_path)
        assert result == "1.2.3"

    def test_returns_question_mark_when_no_metadata(self, tmp_path: str) -> None:
        mod_dir = os.path.join(tmp_path, "test_mod")
        os.makedirs(mod_dir)
        result = backup._read_version(mod_dir, tmp_path)
        assert result == "?"

    def test_returns_question_mark_when_no_version_tag(self, tmp_path: str) -> None:
        mod_dir = os.path.join(tmp_path, "test_mod")
        os.makedirs(mod_dir)
        metadata = ET.Element("metadata")
        ET.ElementTree(metadata).write(os.path.join(mod_dir, "metadata.xml"))
        result = backup._read_version(mod_dir, tmp_path)
        assert result == "?"


# ---- new tests --------------------------------------------------------------


class TestFormatSize:
    @pytest.mark.parametrize(
        ("bytes_in", "expected"),
        [
            (0, "0.0 B"),
            (1, "1.0 B"),
            (512, "512.0 B"),
            (1024, "1.0 KB"),
            (1536, "1.5 KB"),
            (1048576, "1.0 MB"),
            (1073741824, "1.0 GB"),
            (1610612736, "1.5 GB"),
        ],
    )
    def test_format_size(self, bytes_in: int, expected: str) -> None:
        assert backup.format_size(bytes_in) == expected


class TestGetBackupSize:
    def test_nonexistent_dir_returns_zero(self) -> None:
        assert backup.get_backup_size("/nonexistent_path_xyz") == 0

    def test_returns_total_file_size(self, tmp_path: str) -> None:
        os.makedirs(os.path.join(tmp_path, "sub"))
        with open(os.path.join(tmp_path, "a.txt"), "w") as f:
            f.write("x" * 100)
        with open(os.path.join(tmp_path, "sub", "b.txt"), "w") as f:
            f.write("y" * 200)
        assert backup.get_backup_size(tmp_path) == 300


class TestArchiveHelpers:
    def test_get_available_formats_contains_zip(self) -> None:
        fmts = backup.get_available_formats()
        assert "zip" in fmts
        assert "tar.gz" in fmts
        assert "tar.xz" in fmts

    def test_resolve_format_auto_returns_valid(self) -> None:
        fmt = backup._resolve_format("auto")
        assert fmt in ("zip", "tar.gz", "tar.xz", "7z")

    def test_resolve_format_explicit_passthrough(self) -> None:
        assert backup._resolve_format("zip") == "zip"
        assert backup._resolve_format("tar.gz") == "tar.gz"

    def test_resolve_format_invalid_falls_back_to_zip(self) -> None:
        assert backup._resolve_format("invalid") == "zip"

    @pytest.mark.parametrize(
        ("fmt", "suffix"),
        [
            ("zip", ".zip"),
            ("tar.gz", ".tar.gz"),
            ("tar.xz", ".tar.xz"),
            ("7z", ".7z"),
        ],
    )
    def test_archive_suffix(self, fmt: str, suffix: str) -> None:
        assert backup._archive_suffix(fmt) == suffix

    def test_should_ignore_known_patterns(self) -> None:
        assert backup._should_ignore(".git")
        assert backup._should_ignore("__pycache__")
        assert backup._should_ignore(".DS_Store")
        assert not backup._should_ignore("metadata.xml")
        assert not backup._should_ignore("main.lua")


class TestCreateArchive:
    @pytest.mark.parametrize("fmt", ["zip", "tar.gz", "tar.xz"])
    def test_creates_readable_archive(self, tmp_path: str, fmt: str) -> None:
        source = _make_fake_mod(tmp_path, "MyMod", "1.0.0")
        archive_path = os.path.join(tmp_path, f"archive{backup._archive_suffix(fmt)}")
        backup._create_archive(source, archive_path, fmt)
        assert os.path.isfile(archive_path)
        assert os.path.getsize(archive_path) > 0

    def test_zip_contains_files(self, tmp_path: str) -> None:
        source = _make_fake_mod(tmp_path, "MyMod", "1.0.0")
        archive_path = os.path.join(tmp_path, "test.zip")
        sub_dir = os.path.join(source, "content")
        os.makedirs(sub_dir)
        with open(os.path.join(sub_dir, "item.txt"), "w") as f:
            f.write("data")
        backup._create_archive(source, archive_path, "zip")
        with zipfile.ZipFile(archive_path, "r") as zf:
            names = zf.namelist()
            assert "metadata.xml" in names
            assert "main.lua" in names
            assert "content/item.txt" in names

    def test_tar_gz_contains_files(self, tmp_path: str) -> None:
        source = _make_fake_mod(tmp_path, "MyMod", "1.0.0")
        archive_path = os.path.join(tmp_path, "test.tar.gz")
        sub_dir = os.path.join(source, "content")
        os.makedirs(sub_dir)
        with open(os.path.join(sub_dir, "item.txt"), "w") as f:
            f.write("data")
        backup._create_archive(source, archive_path, "tar.gz")
        with tarfile.open(archive_path, "r:gz") as tar:
            names = tar.getnames()
            assert "metadata.xml" in names
            assert "main.lua" in names
            assert "content/item.txt" in names


class TestPruneBackups:
    def test_keeps_only_max_keep(self, tmp_path: str) -> None:
        mod_dir = os.path.join(tmp_path, "MyMod")
        os.makedirs(mod_dir)
        for i in range(4):
            with open(os.path.join(mod_dir, f"MyMod_20240101_{i:04d}.zip"), "w") as f:
                f.write("x")
        backup._prune_backups(mod_dir, "MyMod", ".zip", 2)
        remaining = sorted(os.listdir(mod_dir))
        assert len(remaining) == 2
        assert remaining[0].endswith("0002.zip")
        assert remaining[1].endswith("0003.zip")

    def test_no_prune_if_under_limit(self, tmp_path: str) -> None:
        mod_dir = os.path.join(tmp_path, "MyMod")
        os.makedirs(mod_dir)
        with open(os.path.join(mod_dir, "MyMod_20240101_0000.zip"), "w") as f:
            f.write("x")
        backup._prune_backups(mod_dir, "MyMod", ".zip", 5)
        assert len(os.listdir(mod_dir)) == 1

    def test_empty_dir_no_error(self, tmp_path: str) -> None:
        mod_dir = os.path.join(tmp_path, "MyMod")
        os.makedirs(mod_dir)
        backup._prune_backups(mod_dir, "MyMod", ".zip", 2)
        assert os.listdir(mod_dir) == []


class TestReadArchivedVersion:
    @pytest.mark.parametrize("fmt", ["zip", "tar.gz"])
    def test_reads_version_from_archive(self, tmp_path: str, fmt: str) -> None:
        mod_dir = _make_fake_mod(tmp_path, "MyMod", "2.0.0")
        backup_dir = os.path.join(tmp_path, "backup", "MyMod")
        os.makedirs(backup_dir)
        suffix = backup._archive_suffix(fmt)
        archive_path = os.path.join(backup_dir, f"MyMod_20240101_000000{suffix}")
        backup._create_archive(mod_dir, archive_path, fmt)
        version = backup._read_archived_version("MyMod", os.path.join(tmp_path, "backup"), fmt)
        assert version == "2.0.0"

    def test_no_archive_returns_question_mark(self, tmp_path: str) -> None:
        version = backup._read_archived_version("MyMod", tmp_path, "zip")
        assert version == "?"


class TestBackupModArchived:
    def test_creates_archive_and_prunes(self, tmp_path: str) -> None:
        _make_fake_mod(tmp_path, "MyMod", "1.0.0")
        backup_root = os.path.join(tmp_path, "backup")
        os.makedirs(backup_root)

        backup._backup_mod_archived("MyMod", tmp_path, backup_root, "zip", 2)
        mod_backup_dir = os.path.join(backup_root, "MyMod")
        files = os.listdir(mod_backup_dir)
        assert len(files) == 1
        assert files[0].endswith(".zip")

        _make_fake_mod(tmp_path, "MyMod", "1.1.0")
        import time; time.sleep(1.1)
        backup._backup_mod_archived("MyMod", tmp_path, backup_root, "zip", 2)
        files = sorted(os.listdir(mod_backup_dir))
        assert len(files) == 2

        _make_fake_mod(tmp_path, "MyMod", "1.2.0")
        time.sleep(1.1)
        backup._backup_mod_archived("MyMod", tmp_path, backup_root, "zip", 2)
        files = sorted(os.listdir(mod_backup_dir))
        assert len(files) == 2


class TestBackupNeeded:
    def test_needed_when_no_backup_dir(self, tmp_path: str) -> None:
        _make_fake_mod(tmp_path, "MyMod", "1.0.0")
        backup_root = os.path.join(tmp_path, "backup")
        config.backup_archive_enabled = False
        assert backup.backup_needed("MyMod", tmp_path, backup_root) is True

    def test_not_needed_when_versions_match_directory(self, tmp_path: str) -> None:
        mod_dir = _make_fake_mod(tmp_path, "MyMod", "1.0.0")
        backup_root = os.path.join(tmp_path, "backup")
        os.makedirs(os.path.join(backup_root, "MyMod"))
        import shutil
        shutil.copytree(mod_dir, os.path.join(backup_root, "MyMod"), dirs_exist_ok=True)
        config.backup_archive_enabled = False
        assert backup.backup_needed("MyMod", tmp_path, backup_root) is False

    def test_needed_archive_mode_no_backup(self, tmp_path: str) -> None:
        _make_fake_mod(tmp_path, "MyMod", "1.0.0")
        backup_root = os.path.join(tmp_path, "backup")
        config.backup_archive_enabled = True
        config.backup_archive_format = "zip"
        assert backup.backup_needed("MyMod", tmp_path, backup_root) is True

    def test_not_needed_archive_mode_versions_match(self, tmp_path: str) -> None:
        _make_fake_mod(tmp_path, "MyMod", "1.0.0")
        backup_root = os.path.join(tmp_path, "backup")
        backup_dir = os.path.join(backup_root, "MyMod")
        os.makedirs(backup_dir)
        suffix = backup._archive_suffix("zip")
        archive_path = os.path.join(backup_dir, f"MyMod_20240101_000000{suffix}")
        backup._create_archive(os.path.join(tmp_path, "MyMod"), archive_path, "zip")
        config.backup_archive_enabled = True
        config.backup_archive_format = "zip"
        assert backup.backup_needed("MyMod", tmp_path, backup_root) is False
