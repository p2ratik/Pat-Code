"""
persistence.py — SQLite persistence for repo_intel.

Three tables: nodes, edges, file_hashes.
WAL mode for concurrent reads; a per-instance threading.Lock serialises writes.
"""

import hashlib
import logging
import sqlite3
import threading
from pathlib import Path

from repo_intel.entity_index import EntityRecord


_DDL = """
CREATE TABLE IF NOT EXISTS nodes (
    entity_id    TEXT PRIMARY KEY,
    rel_fname    TEXT NOT NULL,
    fname        TEXT NOT NULL,
    kind         TEXT NOT NULL,
    start_line   INTEGER NOT NULL,
    end_line     INTEGER NOT NULL,
    content_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS edges (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    src        TEXT NOT NULL,
    dst        TEXT NOT NULL,
    edge_type  TEXT NOT NULL,
    file       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS file_hashes (
    rel_fname    TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS edges_file ON edges (file);
CREATE INDEX IF NOT EXISTS nodes_rel  ON nodes (rel_fname);
"""


def file_hash(path: str | Path) -> str:
    """Return sha256 hex digest of a file's raw bytes."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ""


class Persistence:
    """SQLite-backed store for nodes, edges, and per-file content hashes."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.executescript("PRAGMA journal_mode=WAL;" + _DDL)
        self._conn.commit()
        self._lock = threading.Lock()

    # ── read API ──────────────────────────────────────────────────────────────

    def get_all_file_hashes(self) -> dict[str, str]:
        """Return {rel_fname: content_hash} for every indexed file."""
        cur = self._conn.execute("SELECT rel_fname, content_hash FROM file_hashes")
        return {row[0]: row[1] for row in cur.fetchall()}

    def load_all_records(self) -> list[EntityRecord]:
        """Reconstruct all EntityRecords from the nodes table."""
        cur = self._conn.execute(
            "SELECT entity_id, rel_fname, fname, kind, start_line, end_line, content_hash FROM nodes"
        )
        return [
            EntityRecord(
                entity_id=row[0],
                rel_fname=row[1],
                fname=row[2],
                kind=row[3],
                start_line=row[4],
                end_line=row[5],
                content_hash=row[6],
            )
            for row in cur.fetchall()
        ]

    def load_all_edges(self) -> list[tuple[str, str, str, str]]:
        """Return all (src, dst, edge_type, file) edge tuples."""
        cur = self._conn.execute("SELECT src, dst, edge_type, file FROM edges")
        return [(row[0], row[1], row[2], row[3]) for row in cur.fetchall()]

    # ── write API ─────────────────────────────────────────────────────────────

    def save_file(
        self,
        rel_fname: str,
        content_hash: str,
        records: list[EntityRecord],
        edges: list[tuple[str, str, str]],  # (src, dst, edge_type)
    ) -> None:
        """Atomically replace all stored data for rel_fname."""
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "DELETE FROM nodes WHERE rel_fname = ?", (rel_fname,)
                )
                self._conn.execute(
                    "DELETE FROM edges WHERE file = ?", (rel_fname,)
                )
                self._conn.execute(
                    "INSERT OR REPLACE INTO file_hashes VALUES (?, ?)",
                    (rel_fname, content_hash),
                )
                self._conn.executemany(
                    "INSERT OR REPLACE INTO nodes VALUES (?,?,?,?,?,?,?)",
                    [
                        (r.entity_id, r.rel_fname, r.fname, r.kind,
                         r.start_line, r.end_line, r.content_hash)
                        for r in records
                    ],
                )
                self._conn.executemany(
                    "INSERT INTO edges (src, dst, edge_type, file) VALUES (?,?,?,?)",
                    [(src, dst, etype, rel_fname) for src, dst, etype in edges],
                )
        logging.debug("persistence: saved %s (%d nodes, %d edges)", rel_fname, len(records), len(edges))

    def delete_file(self, rel_fname: str) -> None:
        """Remove all persisted data for rel_fname."""
        with self._lock:
            with self._conn:
                self._conn.execute("DELETE FROM nodes WHERE rel_fname = ?", (rel_fname,))
                self._conn.execute("DELETE FROM edges WHERE file = ?", (rel_fname,))
                self._conn.execute("DELETE FROM file_hashes WHERE rel_fname = ?", (rel_fname,))
        logging.debug("persistence: deleted %s", rel_fname)

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()
