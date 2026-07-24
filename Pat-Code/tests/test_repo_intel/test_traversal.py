"""
Unit tests for traversal.py.

Verifies BFS direction, hop limiting, edge_type filtering, node_type
filtering, and the TraversalResult shape.
"""

import networkx as nx
import pytest

from repo_intel.traversal import traverse_graph, TraversalResult


def _build_graph() -> nx.MultiDiGraph:
    """
    Build a small graph for traversal tests:

        A --[contain]--> B --[invoke]--> C
        A --[import]-->  D
    """
    g = nx.MultiDiGraph()
    g.add_node("A", kind="class",    file="a.py")
    g.add_node("B", kind="method",   file="a.py")
    g.add_node("C", kind="function", file="b.py")
    g.add_node("D", kind="module",   file="c.py")
    g.add_edge("A", "B", edge_type="contain", file="a.py")
    g.add_edge("B", "C", edge_type="invoke",  file="a.py")
    g.add_edge("A", "D", edge_type="import",  file="a.py")
    return g


def test_outward_bfs_reaches_all(tmp_path) -> None:
    g = _build_graph()
    result = traverse_graph(g, ["A"], direction="out", hops=2)
    assert set(result.distances.keys()) == {"A", "B", "C", "D"}


def test_hop_limit(tmp_path) -> None:
    g = _build_graph()
    result = traverse_graph(g, ["A"], direction="out", hops=1)
    assert "C" not in result.distances  # C is 2 hops away
    assert "B" in result.distances
    assert "D" in result.distances


def test_inward_bfs(tmp_path) -> None:
    g = _build_graph()
    result = traverse_graph(g, ["C"], direction="in", hops=2)
    assert "B" in result.distances
    assert "A" in result.distances


def test_edge_type_filter(tmp_path) -> None:
    g = _build_graph()
    result = traverse_graph(g, ["A"], direction="out", hops=2, edge_types=["contain"])
    assert "B" in result.distances
    assert "D" not in result.distances  # D reached via import, filtered out


def test_node_type_filter(tmp_path) -> None:
    g = _build_graph()
    result = traverse_graph(g, ["A"], direction="out", hops=2, node_types=["method"])
    assert "B" in result.distances
    assert "C" not in result.distances  # C is function, filtered
    assert "D" not in result.distances  # D is module, filtered


def test_unknown_start_id_is_ignored() -> None:
    g = _build_graph()
    result = traverse_graph(g, ["NONEXISTENT"], direction="out", hops=2)
    assert result.distances == {}


def test_start_node_distance_is_zero() -> None:
    g = _build_graph()
    result = traverse_graph(g, ["A"], direction="out", hops=2)
    assert result.distances["A"] == 0


def test_subgraph_contains_only_visited_nodes() -> None:
    g = _build_graph()
    result = traverse_graph(g, ["A"], direction="out", hops=1)
    assert set(result.subgraph.nodes).issubset(set(result.distances.keys()))


def test_returns_traversal_result() -> None:
    g = _build_graph()
    result = traverse_graph(g, ["A"])
    assert isinstance(result, TraversalResult)
    assert isinstance(result.subgraph, nx.MultiDiGraph)
    assert isinstance(result.distances, dict)
