"""
search.py — BM25-backed entity search engine for repo_intel.

Indexes entity IDs and source content snippets. Returns results in one of
three tiers based on match count: fold (>20), preview (5-20), full (<5).
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rank_bm25 import BM25Okapi

from repo_intel.entity_index import EntityRecord


Tier = Literal["fold", "preview", "full"]

_FOLD_THRESHOLD    = 20
_PREVIEW_THRESHOLD = 5


_TOKEN_RE = re.compile(r"[A-Za-z][a-z0-9]*|[0-9]+")

def _tokenize(text: str) -> list[str]:
    """Lowercase split on camelCase, snake_case, dots, slashes, colons."""
    return [m.group().lower() for m in _TOKEN_RE.finditer(text)]


def _read_source(rec: EntityRecord) -> str:
    """Read the source lines for the entity from disk (start_line..end_line inclusive)."""
    try:
        lines = Path(rec.fname).read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[rec.start_line : rec.end_line + 1])
    except OSError:
        return ""


def _first_line(rec: EntityRecord) -> str:
    """Return the first non-empty source line of the entity for preview tier."""
    try:
        lines = Path(rec.fname).read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines[rec.start_line : rec.end_line + 1]:
            stripped = line.strip()
            if stripped:
                return stripped
    except OSError:
        pass
    return ""


@dataclass(frozen=True)
class SearchMatch:
    entity_id: str
    kind: str
    rel_fname: str
    score: float
    # Populated depending on tier
    preview: str   # first non-empty line  (preview + full tier)
    source: str    # full source text      (full tier only)


@dataclass(frozen=True)
class SearchResult:
    tier: Tier
    matches: list[SearchMatch]
    total_hits: int


class SearchEngine:
    """BM25 search over a corpus of EntityRecords. Call rebuild() after indexing."""

    def __init__(self) -> None:
        self._records: list[EntityRecord] = []
        self._bm25: BM25Okapi | None = None

    def rebuild(self, records: list[EntityRecord]) -> None:
        """Replace the current corpus with records and refit the BM25 model."""
        self._records = list(records)
        # Corpus = entity_id tokens + file tokens — rich enough without reading source
        corpus = [_tokenize(rec.entity_id) for rec in self._records]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, keyword: str, top_k: int = 50) -> SearchResult:
        """
        Search for keyword using exact-ID prefix match first, then BM25 fallback.
        Returns a tiered SearchResult.
        """
        if not self._records:
            return SearchResult(tier="full", matches=[], total_hits=0)

        ranked = self._rank(keyword, top_k)
        return _to_result(ranked)


    def _rank(self, keyword: str, top_k: int) -> list[tuple[EntityRecord, float]]:
        kw_lower = keyword.lower()

        # Exact / prefix match on entity_id gets a synthetic high score
        exact: list[tuple[EntityRecord, float]] = [
            (rec, 100.0)
            for rec in self._records
            if kw_lower in rec.entity_id.lower()
        ]
        if exact:
            return exact[:top_k]

        # BM25 fallback
        if self._bm25 is None:
            return []
        query_tokens = _tokenize(keyword)
        scores: list[float] = self._bm25.get_scores(query_tokens).tolist()
        paired = sorted(zip(self._records, scores), key=lambda p: p[1], reverse=True)
        return [(rec, score) for rec, score in paired[:top_k] if score > 0.0]


def _to_result(ranked: list[tuple[EntityRecord, float]]) -> SearchResult:
    """Convert ranked (record, score) pairs to a tiered SearchResult."""
    total = len(ranked)
    tier = _pick_tier(total)

    matches = [
        SearchMatch(
            entity_id=rec.entity_id,
            kind=rec.kind,
            rel_fname=rec.rel_fname,
            score=score,
            preview=_first_line(rec) if tier in ("preview", "full") else "",
            source=_read_source(rec)  if tier == "full"              else "",
        )
        for rec, score in ranked
    ]
    return SearchResult(tier=tier, matches=matches, total_hits=total)


def _pick_tier(count: int) -> Tier:
    """Return the display tier for a given result count."""
    if count > _FOLD_THRESHOLD:
        return "fold"
    if count > _PREVIEW_THRESHOLD:
        return "preview"
    return "full"
