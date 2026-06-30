from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.hooks.base import ExecutionContext
    from tools.base import ExecutionResult

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
COMPRESS_THRESHOLD = 12_000


@dataclass
class ProcessedOutput:
    content: str
    original_size: int
    processed_size: int
    was_compressed: bool
    strategy: str = "passthrough"


class OutputProcessor(ABC):
    max_chars: int = COMPRESS_THRESHOLD

    def process(
        self, output: str, result: ExecutionResult, ctx: ExecutionContext,
    ) -> ProcessedOutput:
        cleaned = self._normalize(output)
        if len(cleaned) <= self.max_chars:
            return ProcessedOutput(
                content=cleaned,
                original_size=len(output),
                processed_size=len(cleaned),
                was_compressed=False,
            )
        return self._compress(cleaned, result, ctx)

    @abstractmethod
    def _compress(
        self, output: str, result: ExecutionResult, ctx: ExecutionContext,
    ) -> ProcessedOutput: ...

    def _normalize(self, output: str) -> str:
        return _ANSI_RE.sub("", output)

    def _build_metadata_footer(
        self, original_size: int, sent_size: int, strategy: str,
        escape_hatch: str | None = None,
    ) -> str:
        parts = [
            f"\n--- Output Summary ---",
            f"Original: {original_size:,} chars | Sent: {sent_size:,} chars | Strategy: {strategy}",
        ]
        if escape_hatch:
            parts.append(escape_hatch)
        return "\n".join(parts)
