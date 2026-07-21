"""Tests for source/paths.py."""

from __future__ import annotations

import os

import pytest

from source import paths


class TestExtractWorkshopId:
    def test_extracts_id_from_suffix(self) -> None:
        assert paths._extract_workshop_id("mod_12345") == "12345"

    def test_returns_none_when_no_id(self) -> None:
        assert paths._extract_workshop_id("MyCustomMod") is None

    def test_handles_multi_digit_id(self) -> None:
        assert paths._extract_workshop_id("workshop_2890734921") == "2890734921"

    def test_ignores_trailing_non_digit(self) -> None:
        result = paths._extract_workshop_id("mod_123beta")
        assert result is None

    def test_requires_underscore_prefix(self) -> None:
        assert paths._extract_workshop_id("workshop-2890734921") is None

    def test_empty_string(self) -> None:
        assert paths._extract_workshop_id("") is None


class TestInitialize:
    def test_version_read_from_pyproject(self) -> None:
        assert paths.version != "0.0.0", (
            f"version is still the fallback {paths.version!r} \u2014 "
            "initialize() likely failed to read pyproject.toml"
        )

    def test_version_format(self) -> None:
        assert paths.version.startswith("v"), f"Expected v-prefixed version, got {paths.version!r}"
        parts = paths.version.lstrip("v").split(".")
        assert len(parts) == 3, f"Expected semver, got {paths.version!r}"


class TestBaseDir:
    def test_base_dir_exists(self) -> None:
        assert os.path.isdir(paths.BASE_DIR), f"BASE_DIR {paths.BASE_DIR!r} does not exist"


class TestFindIsaacModsFolder:
    def test_returns_none_when_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(paths, "_resolve_linux_path", lambda: None)
        monkeypatch.setattr(paths, "_resolve_windows_path", lambda: None)
        monkeypatch.setattr("sys.platform", "linux")
        result = paths.find_isaac_mods_folder()
        assert result is None


class TestParseVdfPath:
    def test_parses_vdf_correctly(self, tmp_path: str) -> None:
        steam_dir = os.path.join(tmp_path, "steam")
        config_dir = os.path.join(steam_dir, "config")
        os.makedirs(config_dir)

        real_lib_path = os.path.join(tmp_path, "games")
        candidate = os.path.join(
            real_lib_path, "steamapps", "common",
            "The Binding of Isaac Rebirth", "mods",
        )
        os.makedirs(candidate)

        vdf_content = f'''
"libraryfolders"
{{
    "0"
    {{
        "path" "{real_lib_path}"
        "apps"
        {{
            "250900" "whatever"
        }}
    }}
}}
'''
        vdf_path = os.path.join(config_dir, "libraryfolders.vdf")
        with open(vdf_path, "w") as f:
            f.write(vdf_content)

        result = paths._parse_vdf_path(steam_dir)
        assert result == real_lib_path, f"Expected {real_lib_path!r}, got {result!r}"

    def test_returns_none_when_mods_dir_missing(self, tmp_path: str) -> None:
        """VDF is parsed but mods directory must also exist."""
        steam_dir = os.path.join(tmp_path, "steam")
        config_dir = os.path.join(steam_dir, "config")
        os.makedirs(config_dir)

        vdf_content = '''
"libraryfolders"
{
    "0"
    {
        "path" "/nonexistent"
        "apps" { "250900" "x" }
    }
}
'''
        with open(os.path.join(config_dir, "libraryfolders.vdf"), "w") as f:
            f.write(vdf_content)

        result = paths._parse_vdf_path(steam_dir)
        assert result is None
