from __future__ import annotations

from typing import TYPE_CHECKING

from agent.hooks.processors.base import OutputProcessor, ProcessedOutput

if TYPE_CHECKING:
    from agent.hooks.base import ExecutionContext
    from tools.base import ExecutionResult


class ShellProcessor(OutputProcessor):
    HEAD_LINES = 80
    TAIL_LINES = 40

    def _compress(
        self, output: str, result: ExecutionResult, ctx: ExecutionContext,
    ) -> ProcessedOutput:
        lines = output.splitlines()
        total = len(lines)

        head = lines[: self.HEAD_LINES]
        tail = lines[-self.TAIL_LINES :]
        omitted = total - self.HEAD_LINES - self.TAIL_LINES

        stderr_block = self._extract_stderr(output)

        parts = head
        parts.append(f"\n[... {omitted} lines omitted ...]")
        parts.extend(tail)

        if stderr_block:
            parts.append(stderr_block)

        content = "\n".join(parts)
        footer = self._build_metadata_footer(
            len(output), len(content), "head_tail",
        )
        content += footer

        return ProcessedOutput(
            content=content,
            original_size=len(output),
            processed_size=len(content),
            was_compressed=True,
            strategy="head_tail",
        )

    def _extract_stderr(self, output: str) -> str | None:
        marker = "--- stderr ---"
        idx = output.find(marker)
        if idx == -1:
            return None
        return output[idx:]
