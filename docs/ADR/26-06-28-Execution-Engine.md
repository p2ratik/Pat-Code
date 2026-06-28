# Architectural Decision Record — Tool Execution Gateway

## Context & Motivation

To handle retries, check safety/validation rules, and handle failures in tool executions, we needed a centralized gateway. Previously, tools were executed directly, returning `ToolResult` to the agent. This coupled the agentic loop to tool-specific internals and made it hard to introduce runtime policies.

## Decision

We introduced `ExecutionEngine` to serve as a gateway for all tool execution requests. It decouples the tool layer from the runtime layer using two distinct result wrappers:

*   **`ToolResult`**: Produced by individual tools (tool's concern). Contains stdout, stderr, and file diffs.
*   **`ExecutionResult`**: Produced by `ExecutionEngine` (runtime's concern). Envelopes the `ToolResult` and appends runtime metadata (timing, attempts, IDs) and policy status.

## Lifecycle Architecture

The tool execution pipeline is split into three phases:

```
        [Tool Call Request]
                 │
                 ▼
        1. _pre_execute()      ◄── Future: VerificationEngine (pre-validation/budget limits)
                 │
                 ▼
        2. _invoke()           ◄── Run tool ──► returns ToolResult (wrapped into ExecutionResult)
                 │
                 ▼
        3. _post_execute()     ◄── Future: ErrorClassifier & RetryPolicy (retry, backoff, recover)
                 │
                 ▼
        [ExecutionResult]
```

1.  **`_pre_execute()`**: Place for pre-execution tasks (e.g., VerificationEngine checking pre-conditions, rate-limits, or parameters).
2.  **`_invoke()`**: Triggers tool execution, measures duration, and builds the initial `ExecutionResult`.
3.  **`_post_execute()`**: Place for post-execution tasks (e.g., ErrorClassifier evaluating failure types, RetryPolicy triggering retries, or VerificationEngine verifying output).

## Status

Implemented hooks as asynchronous placeholders. Downstream consumers (events, context manager) interface with `ExecutionResult` as the stable public contract.
