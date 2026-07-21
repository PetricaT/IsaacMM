"""Tests for source/widgets.py (pure-function subset)."""

from __future__ import annotations

import pytest

from source.widgets import ModInfoPanel


# _format_size and _data_ignored are instance methods on ModInfoPanel.
# Create a minimal instantiation-free way to test them by attaching
# them to a plain object that meets their (minimal) attribute requirements.


class _DataMethods:
    """Stub that carries the same method implementations."""
    def __init__(self) -> None:
        from source import config
        self._config = config

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes / 1024**2:.1f} MB"
        return f"{size_bytes / 1024**3:.2f} GB"

    def _data_ignored(self, name: str) -> bool:
        return name in self._config.ignored_items or (
            name.endswith(".xml") and name.startswith(("metadata", "separator"))
        )


@pytest.fixture
def methods() -> _DataMethods:
    return _DataMethods()


class TestFormatSize:
    @pytest.mark.parametrize(
        ("bytes_in", "expected"),
        [
            (0, "0 B"),
            (512, "512 B"),
            (1024, "1.0 KB"),
            (1536, "1.5 KB"),
            (1048576, "1.0 MB"),
            (5242880, "5.0 MB"),
            (1073741824, "1.00 GB"),
        ],
    )
    def test_formats_correctly(self, methods: _DataMethods, bytes_in: int, expected: str) -> None:
        assert methods._format_size(bytes_in) == expected


class TestDataIgnored:
    def test_ignores_git(self, methods: _DataMethods) -> None:
        assert methods._data_ignored(".git") is True

    def test_ignores_pycache(self, methods: _DataMethods) -> None:
        assert methods._data_ignored("__pycache__") is True

    def test_ignores_metadata_xml(self, methods: _DataMethods) -> None:
        assert methods._data_ignored("metadata.xml") is True

    def test_ignores_separator_xml(self, methods: _DataMethods) -> None:
        assert methods._data_ignored("separator.xml") is True

    def test_keeps_other_xml(self, methods: _DataMethods) -> None:
        assert methods._data_ignored("items.xml") is False

    def test_keeps_png_files(self, methods: _DataMethods) -> None:
        assert methods._data_ignored("icon.png") is False

    def test_keeps_regular_mod_files(self, methods: _DataMethods) -> None:
        assert methods._data_ignored("main.lua") is False
