"""
Unit tests for search.py.

Verifies exact-ID matching, BM25 fallback, tier selection, and graceful
handling of an empty corpus.
"""

from pathlib import Path
import tempfile

import pytest

from repo_intel.entity_index import EntityRecord
from repo_intel.search import SearchEngine, SearchResult, _pick_tier


def _record(entity_id: str, kind: str = "function", fname: str = "/tmp/x.py") -> EntityRecord:
    return EntityRecord(
        entity_id=entity_id,
        rel_fname="x.py",
        fname=fname,
        kind=kind,
        start_line=0,
        end_line=5,
        content_hash="abc" * 21 + "d",
    )


@pytest.fixture()
def engine_with_records() -> SearchEngine:
    engine = SearchEngine()
    records = [
        _record("agent/agent.py:Agent"),
        _record("agent/agent.py:Agent._agentic_loop", "method"),
        _record("tools/base.py:ToolResult", "class"),
        _record("tools/base.py:ToolResult.error_result", "method"),
        _record("repo_intel/search.py:SearchEngine", "class"),
    ]
    engine.rebuild(records)
    return engine


def test_exact_id_match(engine_with_records: SearchEngine) -> None:
    result = engine_with_records.search("Agent")
    ids = {m.entity_id for m in result.matches}
    assert "agent/agent.py:Agent" in ids
    assert "agent/agent.py:Agent._agentic_loop" in ids


def test_exact_match_scores_high(engine_with_records: SearchEngine) -> None:
    result = engine_with_records.search("Agent")
    for m in result.matches:
        if "Agent" in m.entity_id:
            assert m.score == 100.0


def test_empty_corpus_returns_empty() -> None:
    engine = SearchEngine()
    result = engine.search("anything")
    assert result.total_hits == 0
    assert result.matches == []


def test_bm25_fallback(engine_with_records: SearchEngine) -> None:
    # "search" doesn't appear as a substring of any entity_id literally with the token
    # we use a token that triggers BM25 instead of exact: full module-style token
    result = engine_with_records.search("searchengine")
    # BM25 should surface SearchEngine
    ids = {m.entity_id for m in result.matches}
    assert any("SearchEngine" in eid for eid in ids)


def test_tier_fold() -> None:
    assert _pick_tier(21) == "fold"


def test_tier_preview() -> None:
    assert _pick_tier(10) == "preview"
    assert _pick_tier(20) == "preview"


def test_tier_full() -> None:
    assert _pick_tier(4) == "full"
    assert _pick_tier(0) == "full"


def test_search_result_type(engine_with_records: SearchEngine) -> None:
    result = engine_with_records.search("Tool")
    assert isinstance(result, SearchResult)
    assert isinstance(result.tier, str)
    assert isinstance(result.total_hits, int)
