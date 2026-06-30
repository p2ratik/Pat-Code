from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from agent.hooks.base import ExecutionHook, ExecutionContext, VerificationResult

if TYPE_CHECKING:
    from tools.base import ExecutionResult

logger = logging.getLogger(__name__)


class VerificationHook(ExecutionHook):
    """Level 1 deterministic verification. Pure Python, runs every time."""

    async def after_execute(
        self, ctx: ExecutionContext, result: ExecutionResult,
    ) -> ExecutionResult:
        verification = self._deterministic_verify(ctx, result)
        ctx.state.verification = verification

        if not verification.passed:
            logger.debug(
                "Verification failed for %s: %s",
                ctx.tool_name, verification.issues,
            )

        return result

    def _deterministic_verify(
        self, ctx: ExecutionContext, result: ExecutionResult,
    ) -> VerificationResult:
        issues: list[str] = []

        if result.success and not result.output.strip():
            issues.append("Tool succeeded but returned empty output")

        if ctx.tool_name == "shell":
            if result.exit_code is not None and result.exit_code != 0:
                issues.append(f"Non-zero exit code: {result.exit_code}")

        if result.success and result.output.strip():
            self._check_json_output(result.output, issues)

        passed = len(issues) == 0
        return VerificationResult(
            passed=passed,
            confidence=1.0 if passed else 0.0,
            issues=issues,
            retryable=not passed,
            repair_instruction=self._build_repair(issues) if issues else None,
            level="deterministic",
        )

    def _check_json_output(self, output: str, issues: list[str]) -> None:
        stripped = output.strip()
        if not (stripped.startswith("{") or stripped.startswith("[")):
            return
        try:
            json.loads(stripped)
        except json.JSONDecodeError as e:
            issues.append(f"Output looks like JSON but fails to parse: {e}")

    def _build_repair(self, issues: list[str]) -> str:
        lines = ["The previous tool call had issues:"]
        for issue in issues:
            lines.append(f"- {issue}")
        lines.append("Please address these issues and try again.")
        return "\n".join(lines)
