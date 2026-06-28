from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools.base import ExecutionResult, ToolResult


class ExecutionEngine:
    """
    Gateway for every tool call made by the agent.

    Lifecycle
    ---------
    _pre_execute()           ← placeholder: VerificationEngine pre-checks, rate-limit guards, etc.
    _invoke()                ← actual tool dispatch through the registry
    _post_execute(result)    ← placeholder: ErrorClassifier, RetryPolicy, output verification, etc.

    The engine returns ExecutionResult — the runtime-layer envelope.
    Tools themselves remain unaware of retries, timing, or verification;
    they only return ToolResult (the tool-layer concern).
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    async def execute(
        self,
        name: str,
        params: dict,
        cwd: Path,
        session: Any,
        approval_manager: Any = None,
    ) -> ExecutionResult:
        await self._pre_execute(name, params)

        result = await self._invoke(name, params, cwd, session, approval_manager)

        await self._post_execute(result)

        return result


    async def _pre_execute(self, name: str, params: dict) -> None:
        """
        Pre-execution hook.

        Future integrations (add here when ready):
          - VerificationEngine: validate params / schema before dispatch
          - Rate-limit / quota guard
          - Audit / tracing span start
        """
        pass  

    async def _invoke(
        self,
        name: str,
        params: dict,
        cwd: Path,
        session: Any,
        approval_manager: Any,
    ) -> ExecutionResult:
        """
        Core dispatch: calls the tool registry and wraps the raw ToolResult
        in an ExecutionResult with timing and bookkeeping metadata.
        """
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
            # Placeholder fields — populated by future modules:
            verified=None,       # VerificationEngine
            classification=None, # ErrorClassifier
            recovered=False,     # RetryPolicy
        )

    async def _post_execute(self, result: ExecutionResult) -> None:
        """
        Post-execution hook.

        Future integrations (add here when ready):
          - ErrorClassifier:    classify result.tool_result.error → result.classification
          - RetryPolicy:        decide whether to retry and mutate result.attempts / result.recovered
          - VerificationEngine: verify output correctness → result.verified
          - Audit / tracing span end
        """
        pass  
