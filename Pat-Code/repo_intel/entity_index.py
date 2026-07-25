"""
entity_index.py — scope-aware entity ID builder for repo_intel.

Walks Tag output from tag_extractor and produces qualified EntityRecords
like 'file.py:ClassName.method_name' by maintaining a scope stack over
class definition line ranges.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Query, QueryCursor
from repo_intel.tag_extractor import (
    extract_tags,
    _get_language_and_parser,
    _LANG_REGISTRY,
    _load_scm,
)


@dataclass(frozen=True)
class EntityRecord:
    entity_id: str    # e.g. 'agent/agent.py:Agent._agentic_loop'
    rel_fname: str    # e.g. 'agent/agent.py'
    fname: str        # absolute path
    kind: str         # 'class' | 'function' | 'method' | 'constant'
    start_line: int   # 0-based
    end_line: int     # 0-based, inclusive
    content_hash: str # sha256 of the entity's source text



def _entity_hash(lines: list[str], start: int, end: int) -> str:
    """Return sha256 of the entity's source text slice (inclusive line range)."""
    return hashlib.sha256("\n".join(lines[start : end + 1]).encode()).hexdigest()


@dataclass
class _ScopeFrame:
    name: str
    end_line: int  # inclusive, 0-based


def _evict_dead_frames(frames: list[_ScopeFrame], current_line: int) -> list[_ScopeFrame]:
    """Return only frames whose scope extends to or past current_line (non-mutating)."""
    return [f for f in frames if f.end_line >= current_line]


def _qualified_name(scope_stack: list[_ScopeFrame], name: str) -> str:
    """Dot-join active scope names with the entity name."""
    return ".".join([f.name for f in scope_stack] + [name])


def _infer_kind(scope_stack: list[_ScopeFrame], raw_kind: str) -> str:
    """Promote 'function' to 'method' when inside a class scope."""
    return "method" if raw_kind == "function" and scope_stack else raw_kind



def index_file(fname: str, rel_fname: str) -> list[EntityRecord]:
    """Extract scope-qualified EntityRecords from a single source file."""
    ext = Path(fname).suffix.lower()
    pair = _get_language_and_parser(ext)
    if pair is None:
        return []

    language, parser = pair
    lang_name = _LANG_REGISTRY[ext][0]
    tags_scm = _load_scm(lang_name, "tags")
    if not tags_scm:
        return []

    try:
        code = Path(fname).read_bytes()
        lines = code.decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []

    caps = QueryCursor(Query(language, tags_scm)).captures(parser.parse(code).root_node)

    # line -> capture suffix  (class | function | constant)
    line_to_kind: dict[int, str] = {
        node.start_point[0]: cap_name[len("name.definition."):]
        for cap_name, nodes in caps.items()
        if cap_name.startswith("name.definition.")
        for node in nodes
    }

    # start lines of class definitions — only these push a scope frame
    class_lines: set[int] = {
        node.start_point[0]
        for cap_name, nodes in caps.items()
        if cap_name == "name.definition.class"
        for node in nodes
    }

    def_tags = sorted(
        (t for t in extract_tags(fname, rel_fname) if t.kind == "def"),
        key=lambda t: t.line,
    )

    records: list[EntityRecord] = []
    scope_stack: list[_ScopeFrame] = []

    for tag in def_tags:
        scope_stack = _evict_dead_frames(scope_stack, tag.line)
        raw_kind = line_to_kind.get(tag.line, "function")
        records.append(EntityRecord(
            entity_id=f"{rel_fname}:{_qualified_name(scope_stack, tag.name)}",
            rel_fname=rel_fname,
            fname=fname,
            kind=_infer_kind(scope_stack, raw_kind),
            start_line=tag.line,
            end_line=tag.end_line,
            content_hash=_entity_hash(lines, tag.line, tag.end_line),
        ))
        if tag.line in class_lines:
            scope_stack.append(_ScopeFrame(name=tag.name, end_line=tag.end_line))

    return _dedup_records(records)


def _dedup_records(records: list[EntityRecord]) -> list[EntityRecord]:
    """Drop records with duplicate entity_ids (e.g. property getter + setter).

    tree-sitter captures both the @property and the @X.setter as
    name.definition.function with the same name, producing identical entity_ids.
    We keep the first occurrence (the getter / original definition).
    """
    seen: set[str] = set()
    deduped: list[EntityRecord] = []
    for rec in records:
        if rec.entity_id in seen:
            import logging as _logging
            _logging.debug(
                "entity_index: dropping duplicate entity_id %s (line %d)",
                rec.entity_id, rec.start_line,
            )
            continue
        seen.add(rec.entity_id)
        deduped.append(rec)
    return deduped
