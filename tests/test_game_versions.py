"""Tests for source/game_versions.py."""

from __future__ import annotations

import pytest

from source import game_versions


class TestParseMajorMinor:
    @pytest.mark.parametrize(
        ("version_str", "expected"),
        [
            ("1.2", (1, 2)),
            ("v1.2", None),  # "v" prefix → int("v1") raises ValueError
            ("1.2.3", (1, 2)),
            ("abc", None),
            ("", None),
            # Single part returns (N, 0)
            ("1", (1, 0)),
        ],
    )
    def test_parses_correctly(self, version_str: str, expected: tuple | None) -> None:
        assert game_versions._parse_major_minor(version_str) == expected
