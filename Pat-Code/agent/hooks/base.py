from __future__ import annotations

import time
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tools.base import ExecutionResult, Tool, Toolkind


class RetryMode(str, Enum):
    NONE = "none"
    ENGINE = "engine"
    AGENT = "agent"


@dataclass
class VerificationResult:
    passed: bool
    confidence: float
    issues: list[str]
    retry_mode: RetryMode = RetryMode.NONE
    repair_instruction: str | None = None
    level: str = "deterministic"


@dataclass
class ExecutionState:
    verification: VerificationResult | None = None
    retry_requested: bool = False
    retry_instruction: str | None = None

    def reset(self) -> None:
        self.verification = None
        self.retry_requested = False
        self.retry_instruction = None


@dataclass
class ExecutionContext:
    tool_name: str
    tool: Tool | None
    tool_kind: Toolkind | None
    params: dict[str, Any]
    cwd: Path
    session: Any

    attempt: int = 1
    max_attempts: int = 1
    start_time: float = field(default_factory=time.perf_counter)
    state: ExecutionState = field(default_factory=ExecutionState)


class ExecutionHook(ABC):
    async def before_execute(self, ctx: ExecutionContext) -> None:
        pass

    async def after_execute(
        self, ctx: ExecutionContext, result: ExecutionResult,
    ) -> ExecutionResult:
        return result
