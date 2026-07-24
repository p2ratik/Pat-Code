"""
Unit tests for entity_index.py.

Verifies scope-qualified entity IDs, method/class/function kind inference,
content hashing, and graceful handling of unrecognised files.
"""

from pathlib import Path

import pytest

from repo_intel.entity_index import index_file, EntityRecord


_PY_SOURCE = """\
CONSTANT = 42

class MyClass:
    def method_one(self) -> None:
        pass

    def method_two(self) -> int:
        return 1

def top_level_func() -> str:
    return "hello"
"""


@pytest.fixture()
def py_file(tmp_path: Path) -> tuple[Path, str]:
    f = tmp_path / "mod.py"
    f.write_text(_PY_SOURCE, encoding="utf-8")
    return f, "mod.py"


def _by_name(records: list[EntityRecord]) -> dict[str, EntityRecord]:
    return {r.entity_id.split(":")[-1]: r for r in records}


def test_returns_entity_records(py_file: tuple) -> None:
    f, rel = py_file
    records = index_file(str(f), rel)
    assert len(records) > 0
    assert all(isinstance(r, EntityRecord) for r in records)


def test_class_entity_id(py_file: tuple) -> None:
    f, rel = py_file
    by_name = _by_name(index_file(str(f), rel))
    assert "MyClass" in by_name
    assert by_name["MyClass"].kind == "class"


def test_method_qualified_id(py_file: tuple) -> None:
    f, rel = py_file
    ids = {r.entity_id for r in index_file(str(f), rel)}
    assert "mod.py:MyClass.method_one" in ids
    assert "mod.py:MyClass.method_two" in ids


def test_method_kind(py_file: tuple) -> None:
    f, rel = py_file
    by_name = _by_name(index_file(str(f), rel))
    assert by_name["MyClass.method_one"].kind == "method"
    assert by_name["MyClass.method_two"].kind == "method"


def test_top_level_function_kind(py_file: tuple) -> None:
    f, rel = py_file
    by_name = _by_name(index_file(str(f), rel))
    assert "top_level_func" in by_name
    assert by_name["top_level_func"].kind == "function"


def test_line_ranges_are_valid(py_file: tuple) -> None:
    f, rel = py_file
    for rec in index_file(str(f), rel):
        assert rec.start_line >= 0
        assert rec.end_line >= rec.start_line


def test_content_hash_populated(py_file: tuple) -> None:
    f, rel = py_file
    for rec in index_file(str(f), rel):
        assert len(rec.content_hash) == 64  # sha256 hex


def test_unsupported_file_returns_empty(tmp_path: Path) -> None:
    f = tmp_path / "data.txt"
    f.write_text("hello", encoding="utf-8")
    assert index_file(str(f), "data.txt") == []


def test_missing_file_returns_empty() -> None:
    assert index_file("/no/such/file.py", "file.py") == []
