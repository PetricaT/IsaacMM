"""Tests for source/updater/updater.py."""

from __future__ import annotations

import sys
import types

# Mock third-party deps before any source import
for mod in ("httpx", "tenacity", "toml", "loguru", "PySide6", "PySide6.QtCore"):
    if mod not in sys.modules:
        sys.modules[mod] = types.ModuleType(mod)

httpx_m = sys.modules["httpx"]
httpx_m.RequestError = type("RequestError", (Exception,), {})

tenacity_m = sys.modules["tenacity"]
tenacity_m.retry = lambda **kw: (lambda fn: fn)
tenacity_m.retry_if_exception_type = lambda *a: None
tenacity_m.stop_after_attempt = lambda *a: None
tenacity_m.wait_exponential = lambda **kw: None

loguru_m = sys.modules["loguru"]
loguru_m.logger = type("L", (), {"opt": lambda s, **kw: s})()

toml_m = sys.modules["toml"]
toml_m.load = lambda f: {}
toml_m.dump = lambda d, f: None

pyside_m = sys.modules["PySide6"]
pyside_qt = sys.modules["PySide6.QtCore"]
pyside_qt.QSettings = type("QSettings", (), {})
pyside_qt.Signal = type("Signal", (), {})

# Ensure source.core subpackage is loadable
for pkg in ("source", "source.core", "source.updater"):
    if pkg not in sys.modules:
        m = types.ModuleType(pkg)
        m.__path__ = [pkg.replace(".", "/")]
        m.__package__ = pkg
        sys.modules[pkg] = m

# Mock source.core submodules
for sub in ("database", "paths", "logger", "config"):
    mod = types.ModuleType(f"source.core.{sub}")
    sys.modules[f"source.core.{sub}"] = mod

sys.modules["source.core"].database = sys.modules["source.core.database"]
sys.modules["source.core"].paths = sys.modules["source.core.paths"]

# Provide version for is_newer_version
sys.modules["source.core.paths"].version = "1.0.0"

import pytest

from source.updater import updater  # noqa: E402


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
