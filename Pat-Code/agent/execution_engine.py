from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from agent.hooks.base import ExecutionContext, ExecutionHook, ExecutionState
from tools.base import ExecutionResult, ToolResult


class ExecutionEngine:
    """
    Gateway for every tool call made by the agent.

    Lifecycle
    ---------
    before_execute hooks  → _invoke() → after_execute hooks
    Engine owns the retry loop; hooks own the retry decision.
    """

    def __init__(self, runtime: Any, hooks: list[ExecutionHook] | None = None):
        self.runtime = runtime
        self.hooks = hooks or []

    async def execute(
        self,
        name: str,
        params: dict,
        cwd: Path,
        session: Any,
        approval_manager: Any = None,
    ) -> ExecutionResult:
        tool = self.runtime.tool_registry.get(name)

        ctx = ExecutionContext(
            tool_name=name,
            tool=tool,
            tool_kind=tool.kind if tool else None,
            params=params,
            cwd=cwd,
            session=session,
        )

        for hook in self.hooks:
            await hook.before_execute(ctx)

        result = None
        while ctx.attempt <= ctx.max_attempts:
            result = await self._invoke(name, params, cwd, session, approval_manager)

            for hook in self.hooks:
                result = await hook.after_execute(ctx, result)

            if ctx.state.retry_requested:
                ctx.state.retry_requested = False
                ctx.state.verification = None
                ctx.attempt += 1
                continue

            break

        result.attempts = ctx.attempt
        if ctx.state.verification:
            result.verified = ctx.state.verification.passed
        result.recovered = ctx.attempt > 1 and result.success

        return result

    async def _invoke(
        self,
        name: str,
        params: dict,
        cwd: Path,
        session: Any,
        approval_manager: Any,
    ) -> ExecutionResult:
        t0 = time.perf_counter()

        tool_result: ToolResult = await self.runtime.tool_registry.invoke(
            name,
            params,
            cwd,
            session,
            approval_manager,
        )

        duration_ms = (time.perf_counter() - t0) * 1000

        return ExecutionResult(
            tool_result=tool_result,
            tool_name=name,
            duration_ms=round(duration_ms, 2),
            attempts=1,
            verified=None,
            classification=None,
            recovered=False,
        )
