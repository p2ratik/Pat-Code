"""
Unit tests for tag_extractor.py.

Tests that extract_tags returns the correct Tags for known Python source.
These tests catch tree-sitter grammar regressions early (before the E2E test).
"""

import tempfile
from pathlib import Path

import pytest

from repo_intel.tag_extractor import extract_tags, Tag


_PY_SOURCE = """\
import os
from pathlib import Path

BASE = "value"

class Animal:
    def speak(self) -> str:
        pass

class Dog(Animal):
    def fetch(self) -> str:
        return "ball"
"""


@pytest.fixture()
def py_file(tmp_path: Path) -> Path:
    f = tmp_path / "sample.py"
    f.write_text(_PY_SOURCE, encoding="utf-8")
    return f


def _names(tags: list[Tag], kind: str) -> set[str]:
    return {t.name for t in tags if t.kind == kind}


def test_extract_def_tags(py_file: Path) -> None:
    tags = extract_tags(str(py_file), "sample.py")
    defs = _names(tags, "def")
    assert "Animal" in defs
    assert "Dog" in defs
    assert "speak" in defs
    assert "fetch" in defs


def test_extract_constant_tag(py_file: Path) -> None:
    tags = extract_tags(str(py_file), "sample.py")
    defs = _names(tags, "def")
    assert "BASE" in defs


def test_extract_import_tags(py_file: Path) -> None:
    tags = extract_tags(str(py_file), "sample.py")
    imports = _names(tags, "import")
    assert "os" in imports
    assert "pathlib" in imports


def test_extract_inherit_tags(py_file: Path) -> None:
    tags = extract_tags(str(py_file), "sample.py")
    inherits = _names(tags, "inherit")
    assert "Animal" in inherits


def test_unsupported_extension_returns_empty(tmp_path: Path) -> None:
    f = tmp_path / "notes.txt"
    f.write_text("hello world", encoding="utf-8")
    assert extract_tags(str(f), "notes.txt") == []


def test_missing_file_returns_empty() -> None:
    assert extract_tags("/nonexistent/path/to/file.py", "file.py") == []


def test_tag_fields_are_populated(py_file: Path) -> None:
    tags = extract_tags(str(py_file), "sample.py")
    for t in tags:
        assert t.rel_fname == "sample.py"
        assert t.fname == str(py_file)
        assert isinstance(t.line, int)
        assert isinstance(t.end_line, int)
        assert t.end_line >= t.line
