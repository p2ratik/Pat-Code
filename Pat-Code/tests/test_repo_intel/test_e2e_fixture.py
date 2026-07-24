"""
End-to-end integration test for repo_intel against the sample_repo fixture.

This test indexes the fixture repo (base.py, animals.py, shelter.py) and
asserts known expected entities and edges. Its primary purpose is to catch
tree-sitter grammar regressions: a grammar version bump that silently matches
zero nodes will pass all unit tests but fail here.
"""

import sys
from pathlib import Path

import pytest

# Ensure Pat-Code root is importable
_PAT_CODE = Path(__file__).parent.parent.parent.resolve()
if str(_PAT_CODE) not in sys.path:
    sys.path.insert(0, str(_PAT_CODE))

from repo_intel.entity_index import index_file
from repo_intel.tag_extractor import extract_tags
from repo_intel.typed_graph import TypedGraph, EDGE_CONTAIN, EDGE_IMPORT, EDGE_INHERIT
from repo_intel.traversal import traverse_graph
from repo_intel.search import SearchEngine


FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


# ── helpers ──────────────────────────────────────────────────────────────────

def _abs(name: str) -> str:
    return str(FIXTURE / name)


def _entities(name: str) -> dict[str, object]:
    return {r.entity_id: r for r in index_file(_abs(name), name)}


def _tags_by_kind(name: str, kind: str) -> set[str]:
    return {t.name for t in extract_tags(_abs(name), name) if t.kind == kind}


# ── tag_extractor regression checks ──────────────────────────────────────────

def test_base_py_defs() -> None:
    defs = _tags_by_kind("base.py", "def")
    assert "Animal" in defs, "class Animal must be captured as def"
    assert "speak"  in defs, "method speak must be captured as def"
    assert "breathe" in defs, "method breathe must be captured as def"
    assert "BASE_CONSTANT" in defs, "module constant must be captured"


def test_animals_py_imports() -> None:
    imports = _tags_by_kind("animals.py", "import")
    assert "base" in imports, "import base must produce an import tag"


def test_animals_py_inherits() -> None:
    inherits = _tags_by_kind("animals.py", "inherit")
    assert "Animal" in inherits, "Dog(Animal) must produce an inherit tag for Animal"


def test_shelter_py_imports_both_modules() -> None:
    imports = _tags_by_kind("shelter.py", "import")
    assert "animals" in imports, "from animals import ... must produce an import tag"
    assert "base"    in imports, "from base import ... must produce an import tag"


# ── entity_index regression checks ───────────────────────────────────────────

def test_base_entity_ids() -> None:
    entities = _entities("base.py")
    assert "base.py:Animal"         in entities
    assert "base.py:Animal.speak"   in entities
    assert "base.py:Animal.breathe" in entities
    assert "base.py:BASE_CONSTANT"  in entities


def test_animals_entity_ids() -> None:
    entities = _entities("animals.py")
    assert "animals.py:Dog"        in entities
    assert "animals.py:Dog.speak"  in entities
    assert "animals.py:Dog.fetch"  in entities
    assert "animals.py:Cat"        in entities
    assert "animals.py:Cat.speak"  in entities
    assert "animals.py:Cat.purr"   in entities


def test_shelter_entity_ids() -> None:
    entities = _entities("shelter.py")
    assert "shelter.py:Shelter"            in entities
    assert "shelter.py:Shelter.__init__"   in entities
    assert "shelter.py:Shelter.admit"      in entities
    assert "shelter.py:Shelter.count"      in entities
    assert "shelter.py:Shelter.make_noise" in entities


def test_entity_kinds() -> None:
    base = _entities("base.py")
    assert base["base.py:Animal"].kind == "class"
    assert base["base.py:Animal.speak"].kind == "method"
    assert base["base.py:Animal.breathe"].kind == "method"

    animals = _entities("animals.py")
    assert animals["animals.py:Dog"].kind == "class"
    assert animals["animals.py:Dog.fetch"].kind == "method"


# ── typed_graph edge regression checks ───────────────────────────────────────

@pytest.fixture(scope="module")
def graph() -> TypedGraph:
    root = str(FIXTURE)
    g = TypedGraph()
    for name in ("base.py", "animals.py", "shelter.py"):
        g.index_file(_abs(name), name, root)
    return g


def test_contain_edges_present(graph: TypedGraph) -> None:
    edges = {(u, v, d["edge_type"]) for u, v, d in graph.graph.edges(data=True)}
    assert ("base.py:Animal", "base.py:Animal.speak",   EDGE_CONTAIN) in edges
    assert ("base.py:Animal", "base.py:Animal.breathe", EDGE_CONTAIN) in edges


def test_import_edges_present(graph: TypedGraph) -> None:
    edge_types = {d["edge_type"] for _, _, d in graph.graph.edges(data=True)
                  if d.get("file") == "animals.py"}
    assert EDGE_IMPORT in edge_types


def test_inherit_edges_present(graph: TypedGraph) -> None:
    edge_types = {d["edge_type"] for _, _, d in graph.graph.edges(data=True)
                  if d.get("file") == "animals.py"}
    assert EDGE_INHERIT in edge_types


# ── traversal regression checks ───────────────────────────────────────────────

def test_traversal_from_animal_class(graph: TypedGraph) -> None:
    result = traverse_graph(graph.graph, ["base.py:Animal"], direction="out", hops=1)
    assert "base.py:Animal.speak"   in result.distances
    assert "base.py:Animal.breathe" in result.distances


def test_traversal_inward_finds_parent(graph: TypedGraph) -> None:
    result = traverse_graph(graph.graph, ["base.py:Animal.speak"], direction="in", hops=1)
    assert "base.py:Animal" in result.distances


# ── search regression checks ──────────────────────────────────────────────────

def test_search_finds_shelter_class(graph: TypedGraph) -> None:
    records = []
    for name in ("base.py", "animals.py", "shelter.py"):
        from repo_intel.entity_index import index_file as _idx
        records.extend(_idx(_abs(name), name))

    engine = SearchEngine()
    engine.rebuild(records)

    result = engine.search("Shelter")
    ids = {m.entity_id for m in result.matches}
    assert "shelter.py:Shelter" in ids


def test_search_finds_method_by_name(graph: TypedGraph) -> None:
    records = []
    for name in ("base.py", "animals.py", "shelter.py"):
        from repo_intel.entity_index import index_file as _idx
        records.extend(_idx(_abs(name), name))

    engine = SearchEngine()
    engine.rebuild(records)

    result = engine.search("make_noise")
    ids = {m.entity_id for m in result.matches}
    assert "shelter.py:Shelter.make_noise" in ids
