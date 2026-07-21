"""Shared fixtures for IsaacMM tests."""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Generator
from typing import Any

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


@pytest.fixture
def tmp_path() -> Generator[str, Any, None]:
    """Provide a temporary directory path (cleaned up after test)."""
    with tempfile.TemporaryDirectory(prefix="isaacmm_test_") as td:
        yield td


@pytest.fixture
def mods_dir(tmp_path: str) -> str:
    """Create a fake mods directory with a couple of mod subdirectories."""
    os.makedirs(os.path.join(tmp_path, "resources"), exist_ok=True)
    return tmp_path
