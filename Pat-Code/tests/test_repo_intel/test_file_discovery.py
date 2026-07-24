"""
Unit tests for file_discovery.py.

Verifies that discover_files returns source files, excludes build artifacts,
respects .gitignore, and ignores files with unrecognised extensions.
"""

from pathlib import Path

import pytest

from repo_intel.file_discovery import discover_files


def _setup_repo(root: Path) -> None:
    """Create a small directory tree for discovery tests."""
    (root / "app.py").write_text("x = 1", encoding="utf-8")
    (root / "lib.js").write_text("const x = 1;", encoding="utf-8")
    (root / "README.md").write_text("# readme", encoding="utf-8")

    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "app.cpython-312.pyc").write_bytes(b"")

    (root / "node_modules").mkdir()
    (root / "node_modules" / "index.js").write_text("", encoding="utf-8")

    (root / "build").mkdir()
    (root / "build" / "output.js").write_text("", encoding="utf-8")

    sub = root / "src"
    sub.mkdir()
    (sub / "utils.py").write_text("def helper(): pass", encoding="utf-8")


def test_discovers_source_files(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    found = {p.name for p in discover_files(tmp_path)}
    assert "app.py" in found
    assert "lib.js" in found
    assert "utils.py" in found


def test_excludes_non_source_extensions(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    found = {p.name for p in discover_files(tmp_path)}
    assert "README.md" not in found


def test_excludes_pycache(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    found = {p.name for p in discover_files(tmp_path)}
    assert "app.cpython-312.pyc" not in found


def test_excludes_node_modules(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    paths = discover_files(tmp_path)
    assert not any("node_modules" in p.parts for p in paths)


def test_excludes_build_dir(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    paths = discover_files(tmp_path)
    assert not any("build" in p.parts for p in paths)


def test_respects_gitignore(tmp_path: Path) -> None:
    (tmp_path / "secret.py").write_text("password = 'x'", encoding="utf-8")
    (tmp_path / "keep.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("secret.py\n", encoding="utf-8")

    found = {p.name for p in discover_files(tmp_path)}
    assert "keep.py" in found
    assert "secret.py" not in found


def test_returns_absolute_paths(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1", encoding="utf-8")
    paths = discover_files(tmp_path)
    assert all(p.is_absolute() for p in paths)
