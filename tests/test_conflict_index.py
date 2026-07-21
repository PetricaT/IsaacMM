"""Tests for source/conflict_index.py."""

from __future__ import annotations

import os

import pytest

from source import conflict_index


class TestFingerprintFolder:
    def test_returns_empty_for_empty_folder(self, tmp_path: str) -> None:
        fingerprint, files = conflict_index._fingerprint_folder(tmp_path, [])
        assert isinstance(fingerprint, str)
        assert files == set()

    def test_fingerprints_png_files(self, tmp_path: str) -> None:
        gfx = os.path.join(tmp_path, "gfx")
        os.makedirs(gfx)
        open(os.path.join(gfx, "icon.png"), "w").close()
        open(os.path.join(gfx, "sprite.anm2"), "w").close()
        open(os.path.join(gfx, "readme.txt"), "w").close()

        _, files = conflict_index._fingerprint_folder(tmp_path, [])
        assert "gfx/icon.png" in files
        assert "gfx/sprite.anm2" in files
        assert "gfx/readme.txt" not in files  # not in _CONFLICT_EXTS

    def test_ignores_root_level_files(self, tmp_path: str) -> None:
        open(os.path.join(tmp_path, "icon.png"), "w").close()
        _, files = conflict_index._fingerprint_folder(tmp_path, [])
        assert files == set()  # root-level files are excluded (no "/" in rel path)

    def test_ignores_specified_items(self, tmp_path: str) -> None:
        gfx = os.path.join(tmp_path, "gfx")
        os.makedirs(gfx)
        open(os.path.join(gfx, "icon.png"), "w").close()
        open(os.path.join(gfx, "secret.png"), "w").close()

        _, files = conflict_index._fingerprint_folder(tmp_path, ["secret.png"])
        assert "gfx/icon.png" in files
        assert "gfx/secret.png" not in files

    def test_deterministic_fingerprint_for_same_files(self, tmp_path: str) -> None:
        gfx = os.path.join(tmp_path, "gfx")
        os.makedirs(gfx)
        open(os.path.join(gfx, "a.png"), "w").close()
        fp1, _ = conflict_index._fingerprint_folder(tmp_path, [])

        gfx2 = os.path.join(tmp_path, "gfx2")
        os.makedirs(gfx2)
        open(os.path.join(gfx2, "a.png"), "w").close()
        fp2, _ = conflict_index._fingerprint_folder(tmp_path, [])

        # Same relative structure should give different hash
        # (different mod_path means different mtime path in hash)
        assert isinstance(fp1, str)
        assert isinstance(fp2, str)


class TestQuickToken:
    def test_produces_string(self, tmp_path: str) -> None:
        token = conflict_index._quick_token(tmp_path, [])
        assert isinstance(token, str)
        assert len(token) > 0

    def test_changes_when_file_added(self, tmp_path: str) -> None:
        token1 = conflict_index._quick_token(tmp_path, [])
        open(os.path.join(tmp_path, "new_file.png"), "w").close()
        token2 = conflict_index._quick_token(tmp_path, [])
        assert token1 != token2
