from __future__ import annotations

from typing import TYPE_CHECKING

from agent.hooks.base import ExecutionHook, ExecutionContext
from agent.hooks.processors import (
    ProcessedOutput,
    ShellProcessor,
    FileProcessor,
    DirectoryProcessor,
    GrepProcessor,
    SearchProcessor,
    HTTPProcessor,
    DefaultProcessor,
)

if TYPE_CHECKING:
    from tools.base import ExecutionResult

_PROCESSORS = {
    "shell": ShellProcessor(),
    "read_file": FileProcessor(),
    "list_dir": DirectoryProcessor(),
    "grep": GrepProcessor(),
    "web_search": SearchProcessor(),
    "web_fetch": HTTPProcessor(),
}
_DEFAULT = DefaultProcessor()


class OutputProcessingHook(ExecutionHook):
    """Compresses tool output for LLM context. Never mutates the raw ToolResult."""

    async def after_execute(
        self, ctx: ExecutionContext, result: ExecutionResult,
    ) -> ExecutionResult:
        if result.repair_instruction:
            return result

        output = result.tool_result.to_model_output()
        if not output:
            return result

        processor = _PROCESSORS.get(ctx.tool_name, _DEFAULT)
        processed = processor.process(output, result, ctx)
        result.processed_output = processed

        return result
