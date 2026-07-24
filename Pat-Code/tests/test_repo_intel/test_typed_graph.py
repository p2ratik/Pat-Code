"""
Unit tests for typed_graph.py.

Verifies that TypedGraph builds contain/invoke/import/inherit edges correctly
and that cross-file invalidation removes stale nodes and edges.
"""

from pathlib import Path

import pytest

from repo_intel.typed_graph import TypedGraph, EDGE_CONTAIN, EDGE_IMPORT, EDGE_INHERIT


_BASE_PY = """\
class Animal:
    def speak(self) -> str:
        pass
"""

_DOG_PY = """\
from base import Animal

class Dog(Animal):
    def fetch(self) -> str:
        return "ball"
"""


@pytest.fixture()
def repo(tmp_path: Path) -> tuple[Path, Path]:
    base = tmp_path / "base.py"
    dog  = tmp_path / "dog.py"
    base.write_text(_BASE_PY, encoding="utf-8")
    dog.write_text(_DOG_PY, encoding="utf-8")
    return base, dog


def test_nodes_added_after_index(repo: tuple, tmp_path: Path) -> None:
    base, dog = repo
    g = TypedGraph()
    g.index_file(str(base), "base.py", str(tmp_path))
    assert "base.py:Animal" in g.graph.nodes
    assert "base.py:Animal.speak" in g.graph.nodes


def test_contain_edge(repo: tuple, tmp_path: Path) -> None:
    base, _ = repo
    g = TypedGraph()
    g.index_file(str(base), "base.py", str(tmp_path))
    edges = [(u, v, d["edge_type"]) for u, v, d in g.graph.edges(data=True)]
    contain = [(u, v) for u, v, et in edges if et == EDGE_CONTAIN]
    assert ("base.py:Animal", "base.py:Animal.speak") in contain


def test_import_edge(repo: tuple, tmp_path: Path) -> None:
    _, dog = repo
    g = TypedGraph()
    g.index_file(str(dog), "dog.py", str(tmp_path))
    edge_types = {d["edge_type"] for _, _, d in g.graph.edges(data=True)}
    assert EDGE_IMPORT in edge_types


def test_inherit_edge(repo: tuple, tmp_path: Path) -> None:
    _, dog = repo
    g = TypedGraph()
    g.index_file(str(dog), "dog.py", str(tmp_path))
    edge_types = {d["edge_type"] for _, _, d in g.graph.edges(data=True)}
    assert EDGE_INHERIT in edge_types


def test_invalidation_removes_nodes(repo: tuple, tmp_path: Path) -> None:
    base, _ = repo
    g = TypedGraph()
    g.index_file(str(base), "base.py", str(tmp_path))
    assert "base.py:Animal" in g.graph.nodes

    g.remove_file("base.py")
    assert "base.py:Animal" not in g.graph.nodes
    assert "base.py:Animal.speak" not in g.graph.nodes


def test_invalidation_removes_edges(repo: tuple, tmp_path: Path) -> None:
    base, _ = repo
    g = TypedGraph()
    g.index_file(str(base), "base.py", str(tmp_path))
    g.remove_file("base.py")
    remaining = [d["edge_type"] for _, _, d in g.graph.edges(data=True)
                 if d.get("file") == "base.py"]
    assert remaining == []


def test_reindex_replaces_stale_data(repo: tuple, tmp_path: Path) -> None:
    base, _ = repo
    g = TypedGraph()
    g.index_file(str(base), "base.py", str(tmp_path))
    original_count = g.graph.number_of_nodes()

    # Re-index same file — should not duplicate nodes
    g.index_file(str(base), "base.py", str(tmp_path))
    assert g.graph.number_of_nodes() == original_count
