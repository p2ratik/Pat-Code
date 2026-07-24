"""
intelligence.py — RepoIntelligence facade for repo_intel.

Composes file_discovery, entity_index, typed_graph, search, traversal, and
persistence into a single object. Lazy-initialised on first use; only re-indexes
files whose content hash has changed since the last run.
"""

import logging
from pathlib import Path

from repo_intel.entity_index import EntityRecord, index_file as _index_file
from repo_intel.file_discovery import discover_files
from repo_intel.persistence import Persistence, file_hash
from repo_intel.search import SearchEngine, SearchResult
from repo_intel.traversal import TraversalResult, Direction, traverse_graph as _traverse
from repo_intel.typed_graph import TypedGraph


class RepoIntelligence:
    """
    Facade that indexes a repository and exposes search, traversal, and retrieval.
    Thread-safe for concurrent reads; writes are serialised through Persistence.
    """

    def __init__(self, root: str | Path, db_path: str | Path) -> None:
        self._root = Path(root).resolve()
        self._graph = TypedGraph()
        self._search = SearchEngine()
        self._persistence = Persistence(db_path)
        self._record_index: dict[str, EntityRecord] = {}  # entity_id → record
        self._ready = False
        self._search_dirty = False

    # ── public API ────────────────────────────────────────────────────────────

    def search_entity(self, keyword: str, top_k: int = 50) -> SearchResult:
        """Search for entities matching keyword; returns a tiered SearchResult."""
        self._ensure_ready()
        if self._search_dirty:
            self._search.rebuild(list(self._record_index.values()))
            self._search_dirty = False
        return self._search.search(keyword, top_k)

    def traverse_graph(
        self,
        start_ids: list[str],
        direction: Direction = "out",
        hops: int = 2,
        edge_types: list[str] | None = None,
        node_types: list[str] | None = None,
    ) -> TraversalResult:
        """BFS from start_ids with optional filters; returns subgraph + distances."""
        self._ensure_ready()
        return _traverse(self._graph.graph, start_ids, direction, hops, edge_types, node_types)

    def retrieve_entity(self, entity_id: str) -> str:
        """Return the full source text of entity_id, or an empty string if not found."""
        self._ensure_ready()
        rec = self._record_index.get(entity_id)
        if rec is None:
            return ""
        try:
            lines = Path(rec.fname).read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(lines[rec.start_line : rec.end_line + 1])
        except OSError:
            return ""

    def get_entity_record(self, entity_id: str):
        """Return the EntityRecord for entity_id, or None if not found."""
        self._ensure_ready()
        return self._record_index.get(entity_id)

    # ── initialisation & sync ─────────────────────────────────────────────────

    def _ensure_ready(self) -> None:
        if not self._ready:
            self._bootstrap()
            self._ready = True

    def _bootstrap(self) -> None:
        """Load persisted graph from SQLite, then diff against disk and re-index changed files."""
        self._load_from_db()
        self._sync_with_disk()

    def _load_from_db(self) -> None:
        """Reconstruct in-memory graph and search index from SQLite."""
        records = self._persistence.load_all_records()
        edges   = self._persistence.load_all_edges()

        for rec in records:
            self._graph.graph.add_node(
                rec.entity_id,
                file=rec.rel_fname,
                kind=rec.kind,
                start_line=rec.start_line,
                end_line=rec.end_line,
                content_hash=rec.content_hash,
            )
            self._graph._file_nodes.setdefault(rec.rel_fname, set()).add(rec.entity_id)
            self._record_index[rec.entity_id] = rec

        for src, dst, edge_type, file in edges:
            # dst may be a ref-node or import name that isn't in nodes — add implicitly
            if not self._graph.graph.has_node(dst):
                self._graph.graph.add_node(dst)
            self._graph.graph.add_edge(src, dst, edge_type=edge_type, file=file)

        self._search.rebuild(list(self._record_index.values()))
        logging.debug("intelligence: loaded %d nodes, %d edges from DB", len(records), len(edges))

    def _sync_with_disk(self) -> None:
        """Discover files, re-index changed/new ones, drop deleted ones."""
        stored_hashes = self._persistence.get_all_file_hashes()
        disk_files    = {
            p.relative_to(self._root).as_posix(): p
            for p in discover_files(self._root)
        }

        # Files deleted from disk
        for rel in set(stored_hashes) - set(disk_files):
            self._remove_file(rel)

        # New or changed files
        changed = [
            (rel, path)
            for rel, path in disk_files.items()
            if file_hash(path) != stored_hashes.get(rel)
        ]
        for rel, path in changed:
            self._index_file(str(path), rel)

        if changed or (set(stored_hashes) - set(disk_files)):
            self._search_dirty = True
            logging.debug("intelligence: re-indexed %d file(s)", len(changed))

    # ── per-file index/remove ─────────────────────────────────────────────────

    def _index_file(self, fname: str, rel_fname: str) -> None:
        """Index one file: update graph, persistence, and record index."""
        fhash   = file_hash(fname)
        records = _index_file(fname, rel_fname)

        # Update TypedGraph (handles its own invalidation)
        self._graph.index_file(fname, rel_fname, str(self._root))

        # Collect edges added by typed_graph for this file so we can persist them
        edges: list[tuple[str, str, str]] = [
            (u, v, data["edge_type"])
            for u, v, data in self._graph.graph.edges(data=True)
            if data.get("file") == rel_fname
        ]

        # Update persistence
        self._persistence.save_file(rel_fname, fhash, records, edges)

        # Update record index
        for rec in self._record_index.copy():
            if self._record_index[rec].rel_fname == rel_fname:
                del self._record_index[rec]
        for rec in records:
            self._record_index[rec.entity_id] = rec

    def _remove_file(self, rel_fname: str) -> None:
        """Remove a deleted file from the graph, persistence, and record index."""
        self._graph.remove_file(rel_fname)
        self._persistence.delete_file(rel_fname)
        for eid in [k for k, v in self._record_index.items() if v.rel_fname == rel_fname]:
            del self._record_index[eid]
        logging.debug("intelligence: removed deleted file %s", rel_fname)
