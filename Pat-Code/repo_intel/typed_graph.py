"""
typed_graph.py — typed-edge knowledge graph for repo_intel.

Wraps nx.MultiDiGraph; edges carry an 'edge_type' attribute
('contain' | 'invoke' | 'import' | 'inherit'). Cross-file invalidation
drops and rebuilds every edge where the changed file is source or target.
"""

import logging
from pathlib import Path
from typing import Iterable

import networkx as nx

from repo_intel.entity_index import EntityRecord, index_file
from repo_intel.tag_extractor import extract_tags, _LANG_REGISTRY


EDGE_CONTAIN = "contain"
EDGE_INVOKE  = "invoke"
EDGE_IMPORT  = "import"
EDGE_INHERIT = "inherit"


# Helper funcs
def _rel(fname: str, root: str) -> str:
    """Return a POSIX-style path relative to root, or fname if outside root."""
    try:
        return Path(fname).relative_to(root).as_posix()
    except ValueError:
        return fname


def _entity_id(rel_fname: str, name: str) -> str:
    return f"{rel_fname}:{name}"


def _records_by_line(records: list[EntityRecord]) -> dict[int, EntityRecord]:
    """Map start_line → EntityRecord for quick lookup during invoke-edge building."""
    return {r.start_line: r for r in records}


def _contain_edges(
    records: list[EntityRecord],
) -> Iterable[tuple[str, str, str]]:
    """
    Yield (parent_id, child_id, edge_type) contain edges.
    A child is 'contained' by the innermost record whose line range encloses it.
    """
    # Sort by start_line; use a stack to track enclosing scopes
    stack: list[EntityRecord] = []
    for rec in sorted(records, key=lambda r: r.start_line):
        # Pop scopes that ended before this record starts
        while stack and stack[-1].end_line < rec.start_line:
            stack.pop()
        if stack:
            yield stack[-1].entity_id, rec.entity_id, EDGE_CONTAIN
        stack.append(rec)


def _invoke_edges(
    fname: str, rel_fname: str, records: list[EntityRecord], root: str
) -> Iterable[tuple[str, str, str]]:
    """
    Yield (caller_id, callee_ref, edge_type) invoke edges from ref tags.
    Callee is a bare name (ref); resolution to a full entity_id happens later
    at query time via the entity index — we store the raw ref name as the target
    so the graph stays self-contained without a global name-resolution pass.
    """
    by_line = _records_by_line(records)
    all_tags = extract_tags(fname, rel_fname)
    ref_tags = [t for t in all_tags if t.kind == "ref"]

    for ref in ref_tags:
        # Find the enclosing definition for this reference line
        caller = _find_enclosing(records, ref.line)
        if caller is None:
            continue
        target_id = f"ref:{rel_fname}:{ref.name}@{ref.line}"
        yield caller.entity_id, target_id, EDGE_INVOKE


def _relation_edges(
    fname: str, rel_fname: str
) -> Iterable[tuple[str, str, str]]:
    """Yield (source_id, target_name, edge_type) for import and inherit tags."""
    all_tags = extract_tags(fname, rel_fname)
    for tag in all_tags:
        if tag.kind in ("import", "inherit"):
            source_id = f"{rel_fname}:__module__"
            yield source_id, tag.name, tag.kind


def _find_enclosing(records: list[EntityRecord], line: int) -> EntityRecord | None:
    """Return the narrowest EntityRecord whose [start_line, end_line] contains line."""
    best: EntityRecord | None = None
    for rec in records:
        if rec.start_line <= line <= rec.end_line:
            if best is None or (rec.end_line - rec.start_line) < (best.end_line - best.start_line):
                best = rec
    return best

class TypedGraph:
    """
    Typed-edge knowledge graph over a repository.
    Nodes are entity_ids; edges carry 'edge_type' and 'file' metadata.
    """

    def __init__(self) -> None:
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()
        # rel_fname → set of entity_ids defined in that file
        self._file_nodes: dict[str, set[str]] = {}


    @property
    def graph(self) -> nx.MultiDiGraph:
        return self._g

    def index_file(self, fname: str, rel_fname: str, root: str) -> None:
        """Index a single file: add nodes + edges, replacing stale ones first."""
        self._invalidate_file(rel_fname)

        records = index_file(fname, rel_fname)
        if not records:
            return

        node_ids: set[str] = set()

        # Add nodes
        for rec in records:
            self._g.add_node(
                rec.entity_id,
                file=rel_fname,
                kind=rec.kind,
                start_line=rec.start_line,
                end_line=rec.end_line,
                content_hash=rec.content_hash,
            )
            node_ids.add(rec.entity_id)

        # contain edges
        for src, dst, etype in _contain_edges(records):
            self._g.add_edge(src, dst, edge_type=etype, file=rel_fname)

        # invoke edges (ref tags → caller entity)
        for src, dst, etype in _invoke_edges(fname, rel_fname, records, root):
            self._g.add_edge(src, dst, edge_type=etype, file=rel_fname)

        # import + inherit edges
        for src, dst, etype in _relation_edges(fname, rel_fname):
            src_node = src if src in node_ids else rel_fname + ":__module__"
            if src_node not in self._g:
                self._g.add_node(src_node, file=rel_fname, kind="module")
                node_ids.add(src_node)
            self._g.add_edge(src_node, dst, edge_type=etype, file=rel_fname)

        self._file_nodes[rel_fname] = node_ids

    def index_files(self, file_pairs: Iterable[tuple[str, str]], root: str) -> None:
        """Index multiple (fname, rel_fname) pairs."""
        for fname, rel_fname in file_pairs:
            self.index_file(fname, rel_fname, root)

    def remove_file(self, rel_fname: str) -> None:
        """Remove all nodes and edges contributed by rel_fname."""
        self._invalidate_file(rel_fname)

    def nodes_for_file(self, rel_fname: str) -> set[str]:
        """Return the entity_ids defined in rel_fname."""
        return self._file_nodes.get(rel_fname, set())


    def _invalidate_file(self, rel_fname: str) -> None:
        """
        Drop all edges tagged with rel_fname as source or target file,
        then remove nodes that belong to rel_fname.
        This implements the cross-file edge invalidation rule.
        """
        # Collect edges to drop (cannot mutate during iteration)
        edges_to_remove: list[tuple] = [
            (u, v, k)
            for u, v, k, data in self._g.edges(keys=True, data=True)
            if data.get("file") == rel_fname
        ]
        self._g.remove_edges_from(edges_to_remove)

        # Remove nodes owned by this file
        nodes_to_remove = list(self._file_nodes.get(rel_fname, set()))
        # Only remove nodes that still exist (paranoia guard)
        existing = [n for n in nodes_to_remove if self._g.has_node(n)]
        self._g.remove_nodes_from(existing)

        self._file_nodes.pop(rel_fname, None)
        logging.debug("typed_graph: invalidated %s (%d nodes, %d edges removed)",
                      rel_fname, len(existing), len(edges_to_remove))
