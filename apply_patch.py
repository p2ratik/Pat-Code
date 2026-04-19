from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from tools.base import (
    ToolConfirmation,
    ToolInvocation,
    Toolkind,
    ToolResult,
    Tool,
)
from utils.paths import resolve_path, ensure_parent_directory


class PatchAction(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RENAME = "rename"


@dataclass
class PatchOperation:
    action: PatchAction
    path: Path
    new_path: Path | None = None  # For renames
    content: str | None = None  # For create/update
    move_path: Path | None = None  # Source for renames


@dataclass
class ParsedPatch:
    operations: list[PatchOperation]
    errors: list[str]


class ApplyPatchParams(BaseModel):
    patch: str = Field(..., description="The patch content in the specified format")
    dry_run: bool = Field(
        False, description="Preview changes without applying them (default: false)"
    )


class ApplyPatchTool(Tool):
    """
    Supports a simple patch format:

    ```
    *** Begin Patch
    *** Update File: path/to/file.py
    <<<<<<< SEARCH
    old content to find
    =======
    new content to replace with
    >>>>>>> REPLACE
    *** End Patch
    ```

    Also supports:
    - *** Create File: path/to/new/file.py
    - *** Delete File: path/to/file.py
    - *** Rename File: old/path.py -> new/path.py
    """

    name = "apply_patch"
    description = (
        "Apply a multi-file patch. Supports creating, updating, deleting, and "
        "renaming files in a single operation. **PREFERRED** when editing 2 or more files "
        "instead of making multiple separate edit calls. More efficient and allows "
        "batching multiple file operations atomically.\n\n"
        "Format:\n"
        "*** Begin Patch\n"
        "*** Update File: path/to/file.py\n"
        "<<<<<<< SEARCH\n"
        "old content\n"
        "=======\n"
        "new content\n"
        ">>>>>>> REPLACE\n"
        "*** End Patch\n\n"
        "Also supports:\n"
        "*** Create File: path - creates new file with content after it\n"
        "*** Delete File: path - deletes the file\n"
        "*** Rename File: old -> new - renames/moves a file"
    )
    kind = Toolkind.WRITE
    schema = ApplyPatchParams

    PATCH_START = re.compile(r"^\*\*\*\s*Begin\s+Patch\s*$", re.IGNORECASE)
    PATCH_END = re.compile(r"^\*\*\*\s*End\s+Patch\s*$", re.IGNORECASE)
    UPDATE_FILE = re.compile(r"^\*\*\*\s*Update\s+File:\s*(.+)$", re.IGNORECASE)
    ADD_FILE = re.compile(r"^\*\*\*\s*Add\s+File:\s*(.+)$", re.IGNORECASE)
    CREATE_FILE = re.compile(r"^\*\*\*\s*Create\s+File:\s*(.+)$", re.IGNORECASE)
    DELETE_FILE = re.compile(r"^\*\*\*\s*Delete\s+File:\s*(.+)$", re.IGNORECASE)
    RENAME_FILE = re.compile(r"^\*\*\*\s*Rename\s+File:\s*(.+)\s*->\s*(.+)$", re.IGNORECASE)

    SEARCH_START = re.compile(r"^<{7}\s*SEARCH\s*$")
    SEPARATOR = re.compile(r"^={7}\s*$")
    REPLACE_END = re.compile(r"^>{7}\s*REPLACE\s*$")

    def _parse_patch(self, patch_text: str, cwd: Path) -> ParsedPatch:
        operations: list[PatchOperation] = []
        errors: list[str] = []

        lines = patch_text.splitlines()
        i = 0

        while i < len(lines):
            if self.PATCH_START.match(lines[i].strip()):
                i += 1
                break
            i += 1
        else:
            i = 0

        while i < len(lines):
            line = lines[i].strip()

            if self.PATCH_END.match(line):
                break

            if not line:
                i += 1
                continue

            if match := self.UPDATE_FILE.match(line):
                path = resolve_path(cwd, match.group(1).strip())
                i += 1
                ops, i, err = self._parse_update(lines, i, path)
                if err:
                    errors.append(err)
                else:
                    operations.extend(ops)

            elif match := self.CREATE_FILE.match(line):
                path = resolve_path(cwd, match.group(1).strip())
                i += 1
                content, i = self._read_until_next_operation(lines, i)
                operations.append(
                    PatchOperation(
                        action=PatchAction.CREATE,
                        path=path,
                        content=content,
                    )
                )

            elif match := self.ADD_FILE.match(line):
                path = resolve_path(cwd, match.group(1).strip())
                i += 1
                content, i = self._read_until_next_operation(lines, i)
                content_lines = [
                    ln[1:] if ln.startswith("+") else ln for ln in content.splitlines()
                ]
                operations.append(
                    PatchOperation(
                        action=PatchAction.CREATE,
                        path=path,
                        content="\n".join(content_lines),
                    )
                )

            elif match := self.DELETE_FILE.match(line):
                path = resolve_path(cwd, match.group(1).strip())
                operations.append(
                    PatchOperation(
                        action=PatchAction.DELETE,
                        path=path,
                    )
                )
                i += 1

            elif match := self.RENAME_FILE.match(line):
                old_path = resolve_path(cwd, match.group(1).strip())
                new_path = resolve_path(cwd, match.group(2).strip())
                operations.append(
                    PatchOperation(
                        action=PatchAction.RENAME,
                        path=new_path,
                        move_path=old_path,
                    )
                )
                i += 1

            else:
                i += 1

        return ParsedPatch(operations=operations, errors=errors)

    def _parse_update(
        self,
        lines: list[str],
        start: int,
        path: Path,
    ) -> tuple[list[PatchOperation], int, str | None]:
        """Parse an update operation in either SEARCH/REPLACE or @@ +/- style."""
        block_lines, i = self._read_update_block(lines, start)

        if any(self.SEARCH_START.match(line.strip()) for line in block_lines):
            op, err = self._parse_search_replace_update(block_lines, path)
            if err:
                return [], i, err
            return ([op] if op else []), i, None

        ops, err = self._parse_diff_style_update(block_lines, path)
        if err:
            return [], i, err

        return ops, i, None

    def _read_update_block(
        self,
        lines: list[str],
        start: int,
    ) -> tuple[list[str], int]:
        """Read update body until next operation directive or patch end."""
        block: list[str] = []
        i = start

        while i < len(lines):
            stripped = lines[i].strip()
            if (
                self.UPDATE_FILE.match(stripped)
                or self.ADD_FILE.match(stripped)
                or self.CREATE_FILE.match(stripped)
                or self.DELETE_FILE.match(stripped)
                or self.RENAME_FILE.match(stripped)
                or self.PATCH_END.match(stripped)
            ):
                break
            block.append(lines[i])
            i += 1

        return block, i

    def _parse_search_replace_update(
        self,
        block_lines: list[str],
        path: Path,
    ) -> tuple[PatchOperation | None, str | None]:
        i = 0
        while i < len(block_lines) and not self.SEARCH_START.match(block_lines[i].strip()):
            i += 1
        if i >= len(block_lines):
            return None, f"Missing <<<<<<< SEARCH for {path}"
        i += 1

        search_lines = []
        while i < len(block_lines) and not self.SEPARATOR.match(block_lines[i].strip()):
            search_lines.append(block_lines[i])
            i += 1
        if i >= len(block_lines):
            return None, f"Missing ======= separator for {path}"
        i += 1

        replace_lines = []
        while i < len(block_lines) and not self.REPLACE_END.match(block_lines[i].strip()):
            replace_lines.append(block_lines[i])
            i += 1
        if i >= len(block_lines):
            return None, f"Missing >>>>>>> REPLACE for {path}"

        search_content = "\n".join(search_lines)
        replace_content = "\n".join(replace_lines)

        return (
            PatchOperation(
                action=PatchAction.UPDATE,
                path=path,
                content=f"{search_content}\x00{replace_content}",
            ),
            None,
        )

    def _parse_diff_style_update(
        self,
        block_lines: list[str],
        path: Path,
    ) -> tuple[list[PatchOperation], str | None]:
        """Parse hunks with optional @@ markers and +/- line prefixes."""
        operations: list[PatchOperation] = []
        old_lines: list[str] = []
        new_lines: list[str] = []
        has_changes = False

        def commit_hunk() -> None:
            nonlocal old_lines, new_lines, has_changes
            if not has_changes:
                old_lines = []
                new_lines = []
                return
            operations.append(
                PatchOperation(
                    action=PatchAction.UPDATE,
                    path=path,
                    content=f"{'\\n'.join(old_lines)}\x00{'\\n'.join(new_lines)}",
                )
            )
            old_lines = []
            new_lines = []
            has_changes = False

        for raw_line in block_lines:
            stripped = raw_line.strip()

            if stripped.startswith("@@"):
                commit_hunk()
                continue

            if stripped.startswith("---") or stripped.startswith("+++"):
                continue

            if raw_line.startswith("-"):
                old_lines.append(raw_line[1:])
                has_changes = True
            elif raw_line.startswith("+"):
                new_lines.append(raw_line[1:])
                has_changes = True
            else:
                old_lines.append(raw_line)
                new_lines.append(raw_line)

        commit_hunk()

        if operations:
            return operations, None

        return [], (
            f"No valid update hunks found for {path}. Expected either SEARCH/REPLACE "
            "or @@ with +/- lines."
        )

    def _read_until_next_operation(
        self,
        lines: list[str],
        start: int,
    ) -> tuple[str, int]:
        """Read content until the next operation directive."""
        content_lines = []
        i = start

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if (
                self.UPDATE_FILE.match(stripped)
                or self.ADD_FILE.match(stripped)
                or self.CREATE_FILE.match(stripped)
                or self.DELETE_FILE.match(stripped)
                or self.RENAME_FILE.match(stripped)
                or self.PATCH_END.match(stripped)
            ):
                break

            content_lines.append(line)
            i += 1

        while content_lines and not content_lines[-1].strip():
            content_lines.pop()

        return "\n".join(content_lines), i

    async def get_confirmation(
        self,
        invocation: ToolInvocation,
    ) -> ToolConfirmation | None:
        try:
            params = ApplyPatchParams(**invocation.params)
        except Exception:
            return None

        parsed = self._parse_patch(params.patch, invocation.cwd)

        if parsed.errors:
            return None

        affected_paths = []
        descriptions = []

        for op in parsed.operations:
            affected_paths.append(op.path)
            if op.move_path:
                affected_paths.append(op.move_path)

            if op.action == PatchAction.CREATE:
                descriptions.append(f"Create: {op.path}")
            elif op.action == PatchAction.UPDATE:
                descriptions.append(f"Update: {op.path}")
            elif op.action == PatchAction.DELETE:
                descriptions.append(f"Delete: {op.path}")
            elif op.action == PatchAction.RENAME:
                descriptions.append(f"Rename: {op.move_path} -> {op.path}")

        return ToolConfirmation(
            tool_name=self.name,
            params=invocation.params,
            description="\n".join(descriptions) if descriptions else "Apply patch",
            affected_paths=affected_paths,
            is_dangerous=any(op.action == PatchAction.DELETE for op in parsed.operations),
        )

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            params = ApplyPatchParams(**invocation.params)
        except Exception as e:
            return ToolResult.error_result(f"Invalid parameters: {e}")

        parsed = self._parse_patch(params.patch, invocation.cwd)

        if parsed.errors:
            return ToolResult.error_result(
                "Patch parsing errors:\n" + "\n".join(f"- {e}" for e in parsed.errors)
            )

        if not parsed.operations:
            return ToolResult.error_result("No operations found in patch")

        results = []

        for op in parsed.operations:
            if op.action == PatchAction.CREATE:
                result = await self._apply_create(op, params.dry_run)
            elif op.action == PatchAction.UPDATE:
                result = await self._apply_update(op, params.dry_run)
            elif op.action == PatchAction.DELETE:
                result = await self._apply_delete(op, params.dry_run)
            elif op.action == PatchAction.RENAME:
                result = await self._apply_rename(op, params.dry_run)
            else:
                result = f"Unknown action: {op.action}"

            results.append(result)

        prefix = "[DRY RUN] " if params.dry_run else ""
        return ToolResult.success_result(
            f"{prefix}Applied patch with {len(parsed.operations)} operation(s):\n"
            + "\n".join(f"- {r}" for r in results),
            metadata={
                "operations": len(parsed.operations),
                "dry_run": params.dry_run,
            },
        )

    async def _apply_create(self, op: PatchOperation, dry_run: bool) -> str:
        if op.path.exists():
            return f"SKIP: {op.path} already exists"

        if not dry_run:
            ensure_parent_directory(op.path)
            op.path.write_text(op.content or "", encoding="utf-8")

        return f"Created: {op.path}"

    async def _apply_update(self, op: PatchOperation, dry_run: bool) -> str:
        if not op.path.exists():
            return f"ERROR: {op.path} does not exist"

        if not op.content or "\x00" not in op.content:
            return f"ERROR: Invalid update content for {op.path}"

        search, replace = op.content.split("\x00", 1)

        try:
            content = op.path.read_text(encoding="utf-8")
        except Exception:
            return f"ERROR: Failed to read {op.path}"

        if search not in content:
            return f"ERROR: Search content not found in {op.path}"

        # Apply the replacement once to avoid accidental broad rewrites.
        new_content = content.replace(search, replace, 1)

        if not dry_run:
            op.path.write_text(new_content, encoding="utf-8")

        return f"Updated: {op.path}"

    async def _apply_delete(self, op: PatchOperation, dry_run: bool) -> str:
        if not op.path.exists():
            return f"SKIP: {op.path} does not exist"

        if not dry_run:
            op.path.unlink()

        return f"Deleted: {op.path}"

    async def _apply_rename(self, op: PatchOperation, dry_run: bool) -> str:
        if not op.move_path or not op.move_path.exists():
            return f"ERROR: Source file {op.move_path} does not exist"

        if op.path.exists():
            return f"ERROR: Target file {op.path} already exists"

        if not dry_run:
            ensure_parent_directory(op.path)
            op.move_path.rename(op.path)

        return f"Renamed: {op.move_path} -> {op.path}"