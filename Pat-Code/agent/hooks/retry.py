from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agent.hooks.base import ExecutionHook, ExecutionContext, RetryMode

if TYPE_CHECKING:
    from tools.base import ExecutionResult

logger = logging.getLogger(__name__)


class RetryHook(ExecutionHook):
    """Executes the retry decision made by VerificationHook."""

    def __init__(self, max_attempts: int = 3):
        self._max_attempts = max_attempts

    async def before_execute(self, ctx: ExecutionContext) -> None:
        ctx.max_attempts = self._max_attempts

    async def after_execute(
        self, ctx: ExecutionContext, result: ExecutionResult,
    ) -> ExecutionResult:
        verification = ctx.state.verification
        if not verification or verification.passed:
            return result

        if verification.retry_mode == RetryMode.ENGINE:
            if ctx.attempt < ctx.max_attempts:
                ctx.state.retry_requested = True
                logger.debug(
                    "Engine retry for %s (attempt %d/%d)",
                    ctx.tool_name, ctx.attempt, ctx.max_attempts,
                )
            return result

        if verification.retry_mode == RetryMode.AGENT:
            if verification.repair_instruction:
                result.repair_instruction = verification.repair_instruction
            return result

        return result
