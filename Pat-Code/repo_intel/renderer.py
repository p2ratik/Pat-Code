"""
renderer.py \u2014 tree-formatted output renderer for traversal results.

Converts a TraversalResult into an indented tree string with edge-type
labels, BFS-distance indentation, and reversed-edge markers.
"""

from __future__ import annotations

from collections import defaultdict

import networkx as nx

from repo_intel.traversal import TraversalResult


_BRANCH = "\u251c\u2500\u2500 "
_LAST   = "\u2514\u2500\u2500 "
_PIPE   = "\u2502   "
_SPACE  = "    "


def _node_label(graph: nx.MultiDiGraph, node_id: str) -> str:
    """Return 'node_id (kind)' using graph node metadata."""
    kind = graph.nodes.get(node_id, {}).get("kind", "")
    return f"{node_id} ({kind})" if kind else node_id


def _edge_label(graph: nx.MultiDiGraph, src: str, dst: str, reversed_: bool) -> str:
    """Return '[edge_type]' or '[edge_type \u2190]' for the first edge between src\u2192dst."""
    edges = graph.get_edge_data(src, dst) or {}
    edge_type = next((d.get("edge_type", "?") for d in edges.values()), "?")
    return f"[{edge_type} \u2190]" if reversed_ else f"[{edge_type}]"


def _build_children(
    graph: nx.MultiDiGraph,
    distances: dict[str, int],
) -> dict[str, list[tuple[str, str, str, bool]]]:
    """
    Build parent \u2192 [(child, src, dst, reversed)] for BFS-distance-ordered tree.

    For each edge, the node at smaller BFS distance is the parent.
    'reversed' is True when the raw graph edge runs from child to parent.
    """
    children: dict[str, list[tuple[str, str, str, bool]]] = defaultdict(list)
    for src, dst in graph.edges():
        d_src = distances.get(src, 999)
        d_dst = distances.get(dst, 999)
        if d_src <= d_dst:
            children[src].append((dst, src, dst, False))
        else:
            children[dst].append((src, src, dst, True))
    return children


def _render_children(
    graph: nx.MultiDiGraph,
    children_map: dict[str, list[tuple[str, str, str, bool]]],
    node: str,
    prefix: str,
    visited: set[str],
    lines: list[str],
) -> None:
    """Recursively append child lines under node into lines."""
    kids = [c for c in children_map.get(node, []) if c[0] not in visited]
    for i, (child, src, dst, rev) in enumerate(kids):
        is_last    = i == len(kids) - 1
        connector  = _LAST if is_last else _BRANCH
        edge       = _edge_label(graph, src, dst, rev)
        lines.append(f"{prefix}{connector}{edge} {_node_label(graph, child)}")
        visited.add(child)
        child_prefix = prefix + (_SPACE if is_last else _PIPE)
        _render_children(graph, children_map, child, child_prefix, visited, lines)


def render_traversal(result: TraversalResult, start_ids: list[str]) -> str:
    """
    Render a TraversalResult as an indented tree string.

    Root nodes (distance=0) are rendered without a connector; their
    descendants get tree connectors and edge-type labels.
    """
    graph     = result.subgraph
    distances = result.distances

    if not graph.nodes:
        return "(empty result)"

    children_map = _build_children(graph, distances)
    visited: set[str] = set()
    lines:   list[str] = []

    roots = sorted(
        (n for n in graph.nodes if distances.get(n, 999) == 0),
        key=lambda n: n,
    )

    for i, root in enumerate(roots):
        if i > 0:
            lines.append("")
        lines.append(_node_label(graph, root))
        visited.add(root)
        _render_children(graph, children_map, root, "", visited, lines)

    orphans = sorted(n for n in graph.nodes if n not in visited)
    if orphans:
        lines.append("")
        lines.append("(unreachable via tree)")
        for n in orphans:
            lines.append(f"  {_node_label(graph, n)}")

    return "\n".join(lines)
