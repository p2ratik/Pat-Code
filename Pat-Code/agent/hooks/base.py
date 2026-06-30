from __future__ import annotations

import time
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tools.base import ExecutionResult, Tool, Toolkind


@dataclass
class VerificationResult:
    passed: bool
    confidence: float
    issues: list[str]
    retryable: bool
    repair_instruction: str | None = None
    level: str = "deterministic"


@dataclass
class ExecutionState:
    verification: VerificationResult | None = None
    retry_requested: bool = False
    retry_instruction: str | None = None


@dataclass
class ExecutionContext:
    tool_name: str
    tool: Tool | None
    tool_kind: Toolkind | None
    params: dict[str, Any]
    cwd: Path
    session: Any

    attempt: int = 1
    max_attempts: int = 3
    start_time: float = field(default_factory=time.perf_counter)
    state: ExecutionState = field(default_factory=ExecutionState)


class ExecutionHook(ABC):
    async def before_execute(self, ctx: ExecutionContext) -> None:
        pass

    async def after_execute(
        self, ctx: ExecutionContext, result: ExecutionResult,
    ) -> ExecutionResult:
        return result
