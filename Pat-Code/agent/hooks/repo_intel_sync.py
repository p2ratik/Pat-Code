from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from agent.hooks.base import ExecutionHook, ExecutionContext

if TYPE_CHECKING:
    from tools.base import ExecutionResult

logger = logging.getLogger(__name__)

# Tools that mutate files and need index sync
_WRITE_TOOLS = frozenset({"edit", "write_file", "apply_patch"})


def _to_rel(abs_path: Path, root: Path) -> str:
    try:
        return abs_path.relative_to(root).as_posix()
    except ValueError:
        return abs_path.as_posix()


def _extract_changes(
    tool_name: str, params: dict, metadata: dict
) -> list[dict]:
    """Return a list of {path, op, old_path?} dicts from the tool result."""
    if tool_name in ("edit", "write_file"):
        path = metadata.get("path")
        if not path:
            return []
        op = "create" if metadata.get("is_new_file") else "update"
        return [{"path": path, "op": op}]

    if tool_name == "apply_patch":
        return metadata.get("changes", [])

    return []


def _safe_index(ri, fname: str, rel_fname: str) -> None:
    """Index one file; on failure remove it cleanly rather than leaving it half-broken."""
    try:
        ri._index_file(fname, rel_fname)
        ri._search_dirty = True
    except Exception as exc:
        logger.warning(
            "repo_intel: failed to index %s (%s) — removing from graph",
            rel_fname, exc,
        )
        try:
            ri._remove_file(rel_fname)
            ri._search_dirty = True
        except Exception:
            pass


def _apply_change(ri, change: dict) -> None:
    root = ri._root

    path_str = change.get("path")
    old_path_str = change.get("old_path")
    op = change.get("op", "update")

    if not path_str:
        return

    path = Path(path_str)
    rel = _to_rel(path, root)

    if op in ("create", "update"):
        _safe_index(ri, str(path), rel)

    elif op == "delete":
        ri._remove_file(rel)
        ri._search_dirty = True

    elif op == "rename" and old_path_str:
        old_rel = _to_rel(Path(old_path_str), root)
        ri._remove_file(old_rel)
        ri._search_dirty = True
        _safe_index(ri, str(path), rel)


class RepoIntelSyncHook(ExecutionHook):
    """After a write tool succeeds, incrementally update the repo_intel index."""

    async def after_execute(
        self, ctx: ExecutionContext, result: ExecutionResult,
    ) -> ExecutionResult:
        if ctx.tool_name not in _WRITE_TOOLS:
            return result
        if not result.success:
            return result

        session = getattr(ctx, "session", None)
        if session is None:
            return result

        ri = getattr(session, "_repo_intel", None)
        # Skip if ri was never bootstrapped this session — avoids triggering
        # a cold-start index just because the agent wrote a file before reading code.
        if ri is None or not ri._ready:
            return result

        changes = _extract_changes(ctx.tool_name, ctx.params, result.metadata or {})
        for change in changes:
            _apply_change(ri, change)

        return result
