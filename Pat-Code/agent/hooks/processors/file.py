from __future__ import annotations

from typing import TYPE_CHECKING

from agent.hooks.processors.base import OutputProcessor, ProcessedOutput

if TYPE_CHECKING:
    from agent.hooks.base import ExecutionContext
    from tools.base import ExecutionResult


class FileProcessor(OutputProcessor):
    HEAD_LINES = 150
    TAIL_LINES = 100

    def _compress(
        self, output: str, result: ExecutionResult, ctx: ExecutionContext,
    ) -> ProcessedOutput:
        lines = output.splitlines()
        total = len(lines)

        head = lines[: self.HEAD_LINES]
        tail = lines[-self.TAIL_LINES :]
        omitted = total - self.HEAD_LINES - self.TAIL_LINES

        parts = head
        parts.append(f"\n[... {omitted} lines omitted ...]")
        parts.extend(tail)

        content = "\n".join(parts)
        path_param = ctx.params.get("path", "")
        escape = f"Use read_file with offset={self.HEAD_LINES + 1} for the omitted section."
        footer = self._build_metadata_footer(
            len(output), len(content), "head_tail", escape_hatch=escape,
        )
        content += footer

        return ProcessedOutput(
            content=content,
            original_size=len(output),
            processed_size=len(content),
            was_compressed=True,
            strategy="head_tail",
        )


class DirectoryProcessor(OutputProcessor):
    MAX_ENTRIES = 60

    def _compress(
        self, output: str, result: ExecutionResult, ctx: ExecutionContext,
    ) -> ProcessedOutput:
        lines = output.splitlines()
        total = len(lines)

        shown = lines[: self.MAX_ENTRIES]
        omitted = total - self.MAX_ENTRIES

        content = f"Directory contains {total} entries.\n\n"
        content += "\n".join(shown)
        content += f"\n\n[... {omitted} entries omitted ...]"

        footer = self._build_metadata_footer(
            len(output), len(content), "top_n",
            escape_hatch="Use list_dir with a subdirectory for more detail.",
        )
        content += footer

        return ProcessedOutput(
            content=content,
            original_size=len(output),
            processed_size=len(content),
            was_compressed=True,
            strategy="top_n",
        )


class GrepProcessor(OutputProcessor):
    MAX_MATCHES = 50

    def _compress(
        self, output: str, result: ExecutionResult, ctx: ExecutionContext,
    ) -> ProcessedOutput:
        lines = output.splitlines()
        total_matches = result.metadata.get("matches", "?")

        kept: list[str] = []
        match_count = 0
        for line in lines:
            if line.startswith("==="):
                kept.append(line)
            elif line.strip() == "":
                kept.append(line)
            else:
                match_count += 1
                if match_count <= self.MAX_MATCHES:
                    kept.append(line)

        content = f"Found {total_matches} matches. Showing first {min(match_count, self.MAX_MATCHES)}:\n\n"
        content += "\n".join(kept)

        if match_count > self.MAX_MATCHES:
            content += f"\n\n[... {match_count - self.MAX_MATCHES} matches omitted ...]"

        footer = self._build_metadata_footer(
            len(output), len(content), "top_n",
            escape_hatch="Narrow the search pattern or target a specific file for remaining matches.",
        )
        content += footer

        return ProcessedOutput(
            content=content,
            original_size=len(output),
            processed_size=len(content),
            was_compressed=True,
            strategy="top_n",
        )
