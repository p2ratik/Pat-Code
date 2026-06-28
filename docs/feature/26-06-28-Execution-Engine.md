# Feature — Tool Execution Engine & Contract Decoupling

## Overview

Centralized the tool invocation pathway by routing all tool executions through `ExecutionEngine`. We decoupled the tools themselves (which produce a `ToolResult`) from runtime concerns (which consume an `ExecutionResult`).

## What Was Implemented

1.  **`ExecutionResult` Dataclass**:
    *   Created a wrapper model in `tools/base.py` containing `tool_result: ToolResult`.
    *   Added metadata tracking properties: `execution_id`, `duration_ms`, and `attempts`.
    *   Added placeholder state fields for future integrations: `verified`, `classification`, and `recovered`.
    *   Exposed proxy properties (`success`, `output`, `error`, `metadata`, `diff`, `truncated`, `exit_code`) so the rest of the runtime interfaces only with `ExecutionResult`.

2.  **`ExecutionEngine` Lifecycle**:
    *   Refactored `agent/execution_engine.py` to process requests via three async methods: `_pre_execute`, `_invoke`, and `_post_execute`.
    *   `_invoke` measures wall-clock execution time and wraps the underlying tool's output into the `ExecutionResult`.

3.  **Observability Integration**:
    *   Updated `agent/events.py` to type-hint `ExecutionResult` and capture `execution_id`, `duration_ms`, and `attempts` inside the `TOOL_CALL_COMPLETE` event payload.

## Bugs Solved

*   **Runtime `AttributeError` on Tool Execution**:
    *   **Symptom**: When a tool finished executing, the agent failed with `AttributeError: 'ExecutionResult' object has no attribute 'output'`.
    *   **Cause**: The execution engine returned `ExecutionResult`, but `events.py` and other parts of the agentic loop accessed fields directly off it assuming a `ToolResult`.
    *   **Resolution**: Added getter property decorators (`output`, `error`, `diff`, `truncated`, `exit_code`, `metadata`) to `ExecutionResult` to seamlessly proxy to the inner `ToolResult`.
