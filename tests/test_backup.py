"""Tests for source/backup.py."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import pytest

from source import backup


class TestVersionsDiffer:
    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ("1.0.0", "1.0.1", True),
            ("1.0.0", "1.0.0", False),
            # Version() normalises "v1.0.0" == "1.0.0"
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
            # Same version falls through to "patch" (no InvalidVersion raised)
            ("1.0.0", "1.0.0", "patch"),
            # Unparseable -> "?"
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
