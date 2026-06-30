from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from agent.hooks.base import ExecutionHook, ExecutionContext, RetryMode, VerificationResult

if TYPE_CHECKING:
    from tools.base import ExecutionResult

logger = logging.getLogger(__name__)


class VerificationHook(ExecutionHook):
    """Level 1 deterministic verification. Decides both pass/fail and retry mode."""

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
        modes: list[RetryMode] = []

        if not result.success:
            error_summary = result.error or "Tool returned a failure"
            issues.append(error_summary)
            modes.append(RetryMode.AGENT)

        if result.success and not result.output.strip():
            issues.append("Tool succeeded but returned empty output")
            modes.append(RetryMode.ENGINE)

        if ctx.tool_name == "shell":
            if result.exit_code is not None and result.exit_code != 0:
                issues.append(f"Non-zero exit code: {result.exit_code}")
                modes.append(RetryMode.AGENT)

        if result.success and result.output.strip():
            json_issues = self._check_json_output(result.output)
            if json_issues:
                issues.extend(json_issues)
                modes.append(RetryMode.AGENT)

        passed = len(issues) == 0
        retry_mode = self._resolve_retry_mode(modes) if not passed else RetryMode.NONE

        return VerificationResult(
            passed=passed,
            confidence=1.0 if passed else 0.0,
            issues=issues,
            retry_mode=retry_mode,
            repair_instruction=self._build_repair(ctx, issues, result) if not passed else None,
            level="deterministic",
        )

    def _resolve_retry_mode(self, modes: list[RetryMode]) -> RetryMode:
        """AGENT takes precedence over ENGINE."""
        if RetryMode.AGENT in modes:
            return RetryMode.AGENT
        if RetryMode.ENGINE in modes:
            return RetryMode.ENGINE
        return RetryMode.NONE

    def _check_json_output(self, output: str) -> list[str]:
        stripped = output.strip()
        if not (stripped.startswith("{") or stripped.startswith("[")):
            return []
        try:
            json.loads(stripped)
            return []
        except json.JSONDecodeError as e:
            return [f"Output looks like JSON but fails to parse: {e}"]

    def _build_repair(
        self, ctx: ExecutionContext, issues: list[str], result: ExecutionResult,
    ) -> str:
        parts = [
            "SYSTEM REPAIR NOTICE",
            f"\nTool: {ctx.tool_name}",
        ]

        for issue in issues:
            parts.append(f"\nIssue: {issue}")

        root_cause = self._extract_root_cause(ctx, result)
        if root_cause:
            parts.append(f"\nRoot cause: {root_cause}")

        parts.append(f"\nAction: {self._suggest_action(issues)}")
        return "\n".join(parts)

    def _extract_root_cause(self, ctx: ExecutionContext, result: ExecutionResult) -> str | None:
        if ctx.tool_name != "shell" or not result.error:
            return None

        error = result.error
        for marker in ("SyntaxError", "NameError", "ImportError", "FileNotFoundError",
                        "ModuleNotFoundError", "TypeError", "ValueError", "PermissionError"):
            if marker in error:
                for line in error.splitlines():
                    if marker in line:
                        return line.strip()
        return None

    def _suggest_action(self, issues: list[str]) -> str:
        for issue in issues:
            lower = issue.lower()
            if "exit code" in lower:
                return "Fix the error and retry. Do not repeat the same command unchanged."
            if "json" in lower:
                return "Ensure the tool produces valid JSON output."
        return "Verify the parameters and try a different approach."
