"""Tests for source/updater.py."""

from __future__ import annotations

import pytest

from source import updater


class TestParseVersion:
    @pytest.mark.parametrize(
        ("tag", "expected"),
        [
            ("v1.2.3", (1, 2, 3)),
            ("1.2.3", (1, 2, 3)),
            ("v0.0.1", (0, 0, 1)),
            ("V5.10.0", (5, 10, 0)),
            # pre-release: "3-beta" → strip suffix → 3
            ("v1.2.3-beta", (1, 2, 3)),
            ("1.0", (1, 0)),
            ("0", (0,)),
            # empty string: [""] → "".isdigit() is False → (0,)
            ("", (0,)),
        ],
    )
    def test_parses_valid_tags(self, tag: str, expected: tuple) -> None:
        assert updater._parse_version(tag) == expected


class TestIsNewerVersion:
    def test_newer_is_newer(self) -> None:
        assert updater.is_newer_version("v2.0.0", "v1.0.0")

    def test_older_is_not_newer(self) -> None:
        assert not updater.is_newer_version("v1.0.0", "v2.0.0")


class TestGetDownloadAsset:
    @pytest.mark.parametrize(
        ("platform_name", "asset_name"),
        [
            ("Linux", "IsaacMM-v1.0.0-x86_64.AppImage"),
            ("Windows", "IsaacMM-v1.0.0-win64-setup.exe"),
        ],
    )
    def test_selects_correct_asset(self, monkeypatch: pytest.MonkeyPatch, platform_name: str, asset_name: str) -> None:
        monkeypatch.setattr("platform.system", lambda: platform_name)
        monkeypatch.setattr("platform.machine", lambda: "x86_64")
        release = {
            "assets": [
                {"name": "IsaacMM-v1.0.0-x86_64.AppImage"},
                {"name": "IsaacMM-v1.0.0-win64-setup.exe"},
                {"name": "IsaacMM-v1.0.0-arm64.AppImage"},
            ]
        }
        asset = updater.get_download_asset(release)
        assert asset is not None
        assert asset["name"] == asset_name

    def test_no_matching_asset_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setattr("platform.machine", lambda: "riscv64")
        release = {"assets": [{"name": "IsaacMM-v1.0.0-x86_64.AppImage"}]}
        assert updater.get_download_asset(release) is None
