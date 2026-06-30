from __future__ import annotations

import json
from typing import TYPE_CHECKING

from agent.hooks.processors.base import OutputProcessor, ProcessedOutput

if TYPE_CHECKING:
    from agent.hooks.base import ExecutionContext
    from tools.base import ExecutionResult


class SearchProcessor(OutputProcessor):
    MAX_RESULTS = 15

    def _compress(
        self, output: str, result: ExecutionResult, ctx: ExecutionContext,
    ) -> ProcessedOutput:
        lines = output.splitlines()
        total = len(lines)
        kept = lines[: self.MAX_RESULTS * 4]
        omitted = total - len(kept)

        content = "\n".join(kept)
        if omitted > 0:
            content += f"\n\n[... {omitted} lines of additional results omitted ...]"

        footer = self._build_metadata_footer(
            len(output), len(content), "top_n",
            escape_hatch="Refine the search query for more specific results.",
        )
        content += footer

        return ProcessedOutput(
            content=content,
            original_size=len(output),
            processed_size=len(content),
            was_compressed=True,
            strategy="top_n",
        )


class HTTPProcessor(OutputProcessor):
    BODY_LIMIT = 8000

    def _compress(
        self, output: str, result: ExecutionResult, ctx: ExecutionContext,
    ) -> ProcessedOutput:
        status = result.metadata.get("status_code", "?")

        json_summary = self._try_json_summary(output)
        if json_summary:
            content = f"HTTP {status}\n\n{json_summary}"
        else:
            content = f"HTTP {status}\n\n{output[:self.BODY_LIMIT]}"
            if len(output) > self.BODY_LIMIT:
                content += "\n\n[... response body truncated ...]"

        footer = self._build_metadata_footer(
            len(output), len(content), "json_keys" if json_summary else "head",
            escape_hatch="Use web_fetch again if you need a different section of the response.",
        )
        content += footer

        return ProcessedOutput(
            content=content,
            original_size=len(output),
            processed_size=len(content),
            was_compressed=True,
            strategy="json_keys" if json_summary else "head",
        )

    def _try_json_summary(self, output: str) -> str | None:
        stripped = output.strip()
        if not (stripped.startswith("{") or stripped.startswith("[")):
            return None
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return None

        if isinstance(data, dict):
            keys = list(data.keys())
            parts = [f"JSON object with {len(keys)} keys: {', '.join(keys[:20])}"]
            sample_key = keys[0] if keys else None
            if sample_key:
                sample = json.dumps(data[sample_key], indent=2, default=str)
                if len(sample) > 2000:
                    sample = sample[:2000] + "\n..."
                parts.append(f"\nSample ({sample_key}):\n{sample}")
            return "\n".join(parts)

        if isinstance(data, list):
            parts = [f"JSON array with {len(data)} items."]
            if data:
                sample = json.dumps(data[0], indent=2, default=str)
                if len(sample) > 2000:
                    sample = sample[:2000] + "\n..."
                parts.append(f"\nFirst item:\n{sample}")
            return "\n".join(parts)

        return None
