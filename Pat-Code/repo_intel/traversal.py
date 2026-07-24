"""
traversal.py — BFS graph traversal for repo_intel.

Implements direction-aware, hop-limited BFS over a TypedGraph with optional
edge_type and node_type filters. Returns node distances for tree rendering.
"""

from collections import deque
from dataclasses import dataclass
from typing import Literal

import networkx as nx


Direction = Literal["out", "in", "both"]


@dataclass(frozen=True)
class TraversalResult:
    # Induced subgraph over all visited nodes (preserves edge attributes)
    subgraph: nx.MultiDiGraph
    # node_id → BFS distance from the nearest start node
    distances: dict[str, int]


def _neighbours(
    graph: nx.MultiDiGraph,
    node: str,
    direction: Direction,
    edge_types: set[str] | None,
) -> list[tuple[str, str, dict]]:
    """
    Return (neighbour, edge_key, data) tuples reachable from node
    given direction and optional edge_type filter.
    """
    candidates: list[tuple[str, str, str, dict]] = []

    if direction in ("out", "both"):
        candidates += [
            (v, k, data)
            for _, v, k, data in graph.out_edges(node, keys=True, data=True)
        ]
    if direction in ("in", "both"):
        candidates += [
            (u, k, data)
            for u, _, k, data in graph.in_edges(node, keys=True, data=True)
        ]

    if edge_types is not None:
        candidates = [(n, k, d) for n, k, d in candidates if d.get("edge_type") in edge_types]

    return candidates


def traverse_graph(
    graph: nx.MultiDiGraph,
    start_ids: list[str],
    direction: Direction = "out",
    hops: int = 2,
    edge_types: list[str] | None = None,
    node_types: list[str] | None = None,
) -> TraversalResult:
    """
    BFS from start_ids up to hops steps, respecting direction and filter args.
    Returns a TraversalResult with an induced subgraph and per-node distances.
    """
    edge_type_set = set(edge_types) if edge_types else None
    node_type_set = set(node_types) if node_types else None

    visited: dict[str, int] = {}  # node_id → distance
    queue: deque[tuple[str, int]] = deque()

    for sid in start_ids:
        if sid in graph and sid not in visited:
            visited[sid] = 0
            queue.append((sid, 0))

    while queue:
        node, dist = queue.popleft()
        if dist >= hops:
            continue

        for neighbour, _key, _data in _neighbours(graph, node, direction, edge_type_set):
            if neighbour in visited:
                continue
            node_data = graph.nodes.get(neighbour, {})
            if node_type_set is not None and node_data.get("kind") not in node_type_set:
                continue
            visited[neighbour] = dist + 1
            queue.append((neighbour, dist + 1))

    subgraph = graph.subgraph(visited.keys()).copy()
    return TraversalResult(subgraph=subgraph, distances=visited)
