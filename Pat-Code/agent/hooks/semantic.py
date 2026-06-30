from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from agent.hooks.base import ExecutionHook, ExecutionContext, RetryMode, VerificationResult

if TYPE_CHECKING:
    from tools.base import ExecutionResult

logger = logging.getLogger(__name__)

_SEMANTIC_PROMPT = """\
You are a tool-call verifier for an AI agent.

A tool was invoked and produced the result below. Your job is to decide:
1. Did the tool accomplish what was asked?
2. If not, write a structured SYSTEM REPAIR NOTICE the agent should act on.

Tool name: {tool_name}
Parameters: {params}
Tool output:
{output}
Tool error: {error}

If the tool succeeded and the output is useful, respond with exactly: PASS

If the tool failed or the output is wrong, respond with a SYSTEM REPAIR NOTICE using this exact format:

SYSTEM REPAIR NOTICE

The previous tool invocation failed verification.

Reason:
<one sentence describing what went wrong>

Recovery strategy:
- <specific action 1>
- <specific action 2>
- <specific action 3>

Think step by step and choose the best recovery action."""


class SemanticVerificationHook(ExecutionHook):
    """Level 2 semantic verification using an injected LLM client."""

    def __init__(self, llm_client: Any, model: str | None = None):
        self._client = llm_client
        self._model = model

    async def after_execute(
        self, ctx: ExecutionContext, result: ExecutionResult,
    ) -> ExecutionResult:
        needs_semantic = self._should_run(ctx, result)
        if not needs_semantic:
            return result

        verdict = await self._call_llm(ctx, result)
        if verdict is None or verdict.strip().upper() == "PASS":
            return result

        ctx.state.verification = VerificationResult(
            passed=False,
            confidence=0.7,
            issues=["Semantic verification failed"],
            retry_mode=RetryMode.AGENT,
            repair_instruction=verdict.strip(),
            level="semantic",
        )
        result.repair_instruction = verdict.strip()

        logger.debug("Semantic verification failed for %s", ctx.tool_name)
        return result

    def _should_run(self, ctx: ExecutionContext, result: ExecutionResult) -> bool:
        if not result.success:
            return True
        if ctx.tool and ctx.tool.requires_semantic_verification:
            return True
        return False

    async def _call_llm(
        self, ctx: ExecutionContext, result: ExecutionResult,
    ) -> str | None:
        prompt = _SEMANTIC_PROMPT.format(
            tool_name=ctx.tool_name,
            params=ctx.params,
            output=result.output[:3000] if result.output else "(none)",
            error=result.error or "(none)",
        )

        messages = [{"role": "user", "content": prompt}]

        original_model = self._client.config.model_name
        if self._model:
            self._client.config.model_name = self._model

        try:
            text = ""
            async for event in self._client.chat_completion(
                messages=messages,
                tools=None,
                stream=False,
            ):
                if event.text_delta and event.text_delta.content:
                    text += event.text_delta.content
            return text or None
        except Exception as e:
            logger.warning("Semantic verifier LLM call failed: %s", e)
            return None
        finally:
            if self._model:
                self._client.config.model_name = original_model
