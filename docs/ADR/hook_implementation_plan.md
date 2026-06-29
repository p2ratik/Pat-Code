# Hook Pipeline — Implementation Plan

## Decisions Log

| # | Decision | Choice |
|---|----------|--------|
| 1 | Retry loop ownership | **Engine owns loop**, hook owns decision (`ctx.shared["retry_requested"]`) |
| 2 | Semantic verifier LLM | **Reuse `LLMClient`**, inject into hook. No new abstraction. |
| 3 | OutputProcessingHook | **Last after-hook**. Retry sees full output; conversation sees processed output. |
| 4 | Hook registration | **Global only**. Per-tool behavior handled inside hook via `ctx.tool_name` branching. |
| 5 | ApprovalHook | **Deferred**. Approval stays in `ToolRegistry.invoke()` for now. |
| 6 | Shared state | **`ExecutionContext.shared`** — hooks communicate through context, not `ExecutionResult`. |

---

## 1. File Structure

```
Pat-Code/agent/
├── execution_engine.py          # Refactored
└── hooks/
    ├── __init__.py               # Re-exports
    ├── base.py                   # ExecutionHook ABC, ExecutionContext, VerificationResult
    ├── verification.py           # VerificationHook (L1 + L2)
    ├── retry.py                  # RetryHook
    └── output_processing.py      # OutputProcessingHook + per-tool policies
```

No changes to `tools/base.py`, `Tool` ABC, or individual tool files.

---

## 2. New Abstractions — `hooks/base.py`

### ExecutionContext

The shared state object every hook receives. Hooks communicate through `shared`, **not** through `ExecutionResult`.

```python
@dataclass
class ExecutionContext:
    tool_name: str
    tool: Tool                          # The Tool instance from registry
    tool_kind: Toolkind                 # Shortcut: tool.kind
    params: dict[str, Any]
    cwd: Path
    session: Any

    attempt: int = 1
    max_attempts: int = 3
    start_time: float = field(default_factory=time.perf_counter)
    shared: dict[str, Any] = field(default_factory=dict)
```

**Key `shared` keys used across hooks:**

| Key | Writer | Reader | Type |
|-----|--------|--------|------|
| `"verification"` | VerificationHook | RetryHook | `VerificationResult` |
| `"retry_requested"` | RetryHook | Engine, OutputProcessingHook | `bool` |
| `"retry_instruction"` | RetryHook | Engine | `str` |

### ExecutionHook ABC

```python
class ExecutionHook(ABC):
    async def before_execute(self, ctx: ExecutionContext) -> None:
        """Runs once, before the invoke loop."""
        pass

    async def after_execute(
        self, ctx: ExecutionContext, result: ExecutionResult
    ) -> ExecutionResult:
        """Runs after each invoke attempt. May transform result."""
        return result
```

Most hooks implement only one side. Example: VerificationHook → `after_execute` only.

### VerificationResult

```python
@dataclass
class VerificationResult:
    passed: bool
    confidence: float                   # 0.0 – 1.0
    issues: list[str]
    retryable: bool
    repair_instruction: str | None = None
    level: str = "deterministic"        # "deterministic" | "semantic"
```

---

## 3. VerificationHook — `hooks/verification.py`

### Constructor

```python
class VerificationHook(ExecutionHook):
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        semantic_model: str | None = None,
    ):
        self.llm_client = llm_client
        self.semantic_model = semantic_model
```

LLM is injected. If `llm_client` is `None`, only L1 runs.

### Pipeline

```
after_execute
    │
    ├─ L1: _deterministic_verify(ctx, result) → VerificationResult
    │       Always runs. Pure Python. Free.
    │       If failed → store in ctx.shared["verification"], return early
    │
    └─ L2: _semantic_verify(ctx, result) → VerificationResult
            Only if L1 passed AND tool requires semantic verification.
            Uses LLM. Store in ctx.shared["verification"].
```

### Level 1 — Deterministic Checks

All pure Python. Run for **every** tool invocation.

| Check | Applies To | Logic |
|-------|-----------|-------|
| **Empty output** | All (success=True) | `not result.output.strip()` |
| **JSON parseable** | Tools returning JSON metadata | `json.loads()` on output |
| **Exit code ≠ 0** | Shell (has `exit_code`) | `result.exit_code is not None and result.exit_code != 0` |
| **File exists** | read_file, edit, write_file | Check `params["path"]` exists after execution |
| **Output length** | All | Output > 0 chars when success |
| **Schema valid** | All | `tool.validate_params(params)` — already done in registry, but belt-and-suspenders for retry scenarios |

Implementation: a list of small check functions. Each returns `(passed: bool, issue: str | None)`. Aggregate into a single `VerificationResult`.

```python
def _deterministic_verify(self, ctx: ExecutionContext, result: ExecutionResult) -> VerificationResult:
    issues = []

    # Universal checks
    if result.success and not result.output.strip():
        issues.append("Tool succeeded but returned empty output")

    # Shell-specific
    if ctx.tool_name == "shell":
        if result.exit_code is not None and result.exit_code != 0:
            issues.append(f"Non-zero exit code: {result.exit_code}")

    # File-tool checks
    if ctx.tool_name in ("edit", "write_file"):
        path = ctx.params.get("path")
        if path and not Path(path).exists():
            issues.append(f"File does not exist after operation: {path}")

    passed = len(issues) == 0
    return VerificationResult(
        passed=passed,
        confidence=1.0 if passed else 0.0,
        issues=issues,
        retryable=not passed,  # deterministic failures are retryable
        repair_instruction=self._build_repair(issues) if issues else None,
        level="deterministic",
    )
```

### Level 2 — Semantic Checks

Only runs when:
1. L1 passed (no point running LLM if deterministic checks already failed)
2. Tool is in the semantic-verification set
3. `self.llm_client` is available

**Tools requiring semantic verification:**

```python
SEMANTIC_TOOLS: set[str] = {
    "web_search", "web_fetch",              # Network: did results answer the query?
    "edit", "write_file",                   # Write: is the edit faithful?
}
SEMANTIC_TOOL_PREFIXES: list[str] = [
    "subagent_",                            # Multi-agent: did subagent accomplish goal?
]
```

> [!NOTE]
> Tools like `read_file`, `list_dir`, `grep`, `glob`, `shell` have deterministic outputs — semantic verification adds no value.

**LLM call:** Uses the injected `LLMClient` with `stream=False, tools=None`.

```python
async def _semantic_verify(self, ctx, result) -> VerificationResult:
    prompt = self._build_verification_prompt(ctx, result)
    messages = [
        {"role": "system", "content": VERIFIER_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    # Reuse LLMClient non-streaming path
    response = await self._call_llm(messages)
    return self._parse_verifier_response(response)
```

The verifier prompt includes:
- Tool name + params (what was requested)
- Tool output (what was returned)
- Question: "Does this output correctly fulfill the request?"
- Expected response: JSON with `{passed, confidence, issues, repair_instruction}`

---

## 4. RetryHook — `hooks/retry.py`

### Constructor

```python
class RetryHook(ExecutionHook):
    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts
```

### Logic

```python
async def after_execute(self, ctx, result):
    verification: VerificationResult | None = ctx.shared.get("verification")

    if verification is None or verification.passed:
        return result  # Nothing to retry

    if not verification.retryable:
        return result  # Not retryable

    if ctx.attempt >= ctx.max_attempts:
        return result  # Exhausted attempts

    # Signal retry to the engine
    ctx.shared["retry_requested"] = True
    ctx.shared["retry_instruction"] = verification.repair_instruction
    return result
```

### Two Retry Outcomes

| Scenario | Who handles it | Example |
|----------|---------------|---------|
| **Transient failure** (rate limit, timeout) | Engine re-invokes same tool | Network blip on `web_search` |
| **Param/semantic failure** | Result returned to agent loop with enriched error | `{"path": 123}` → schema fail → repair instruction in output |

For param failures where re-invoking with the same params is pointless, the RetryHook can mark `retryable=False` or the engine can detect "same error twice" and break.

> [!IMPORTANT]
> The engine enriches the `ExecutionResult` error output with the repair instruction before returning to the agent loop. The LLM naturally re-generates based on the enriched error message.

---

## 5. OutputProcessingHook — `hooks/output_processing.py`

### Purpose

Transform `result.tool_result.output` **after** verification and retry decisions are made. This is what the LLM conversation sees — not what verification/retry saw.

### Skip on Retry

```python
async def after_execute(self, ctx, result):
    if ctx.shared.get("retry_requested"):
        return result  # Don't process yet — we're retrying
    return self._process(ctx, result)
```

### Per-Tool Policies

```python
class OutputPolicy(ABC):
    @abstractmethod
    def process(self, output: str, ctx: ExecutionContext, result: ExecutionResult) -> str:
        ...
```

| Tool | Policy | Behavior |
|------|--------|----------|
| `shell` | `ShellOutputPolicy` | Keep exit code, first error, last error, traceback summary. Compress middle. |
| `read_file` | `PassthroughPolicy` | No compression. Whole point is reading. |
| `web_search` | `TopNResultsPolicy` | Keep top N results (configurable, default 5). |
| `grep` | `MatchedLinesPolicy` | Keep matched lines only. Already compact. |
| `list_dir` | `PassthroughPolicy` | Already compact. |
| `edit` / `write_file` | `PassthroughPolicy` | Already compact (just confirmation). |
| `glob` | `PassthroughPolicy` | Already compact. |
| `web_fetch` | `TruncationPolicy` | Truncate to max tokens, preserve head. |
| Default (MCP, subagent) | `TruncationPolicy` | Truncate to configurable max length. |

### ShellOutputPolicy (most complex)

```python
class ShellOutputPolicy(OutputPolicy):
    def process(self, output, ctx, result):
        lines = output.splitlines()

        # Always preserve
        preserved = {
            "exit_code": self._extract_exit_code(lines),
            "first_error": self._first_error_line(lines),
            "last_error": self._last_error_line(lines),
            "traceback": self._extract_traceback(lines),
        }

        if len(output) <= self.max_chars:
            return output  # Short enough, keep everything

        return self._compress(preserved, lines)
```

Detection heuristics:
- **Traceback**: Lines starting with `Traceback`, `File "`, or indented code lines followed by error
- **Error lines**: Lines containing `Error:`, `error:`, `FAILED`, `Exception`
- **Exit code**: Already in `result.exit_code`

---

## 6. ExecutionEngine Refactor

### New Constructor

```python
class ExecutionEngine:
    def __init__(self, runtime: Any, hooks: list[ExecutionHook] | None = None):
        self.runtime = runtime
        self.hooks = hooks or []
```

### New `execute()` — The Complete Pipeline

```python
async def execute(self, name, params, cwd, session, approval_manager=None):
    tool = self.runtime.tool_registry.get(name)

    ctx = ExecutionContext(
        tool_name=name,
        tool=tool,
        tool_kind=tool.kind if tool else None,
        params=params,
        cwd=cwd,
        session=session,
        max_attempts=3,
    )

    # ── Pre-hooks (run once) ──
    for hook in self.hooks:
        await hook.before_execute(ctx)

    # ── Invoke + After-hook loop (engine owns retry loop) ──
    result = None
    while ctx.attempt <= ctx.max_attempts:
        result = await self._invoke(name, params, cwd, session, approval_manager)

        # Run after-hooks in order: Verification → Retry → OutputProcessing
        for hook in self.hooks:
            result = await hook.after_execute(ctx, result)

        # Check retry signal
        if ctx.shared.pop("retry_requested", False):
            ctx.attempt += 1
            continue

        break

    # ── Finalize ──
    result.attempts = ctx.attempt
    verification = ctx.shared.get("verification")
    if verification:
        result.verified = verification.passed
    result.recovered = ctx.attempt > 1 and result.success

    return result
```

### `_invoke()` — Unchanged

Stays exactly as-is. Creates `ExecutionResult` with timing. No hooks inside.

---

## 7. Integration Points

### Files Modified

| File | Change | Size |
|------|--------|------|
| [execution_engine.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/agent/execution_engine.py) | Refactor `execute()`, add `hooks` param, add retry loop | Medium |
| [runtime.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/agent/runtime.py) | No change needed (engine constructor is internal) | None |
| [session.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/agent/session.py) | Pass hooks list when creating `ExecutionEngine` | Small |
| [base.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/tools/base.py) | No change. `ExecutionResult` fields stay same. | None |

### Files Created

| File | Contents |
|------|----------|
| `agent/hooks/__init__.py` | Re-exports |
| `agent/hooks/base.py` | `ExecutionHook`, `ExecutionContext`, `VerificationResult` |
| `agent/hooks/verification.py` | `VerificationHook` (L1 + L2) |
| `agent/hooks/retry.py` | `RetryHook` |
| `agent/hooks/output_processing.py` | `OutputProcessingHook` + policy classes |

### Hook Wiring (in Session / CloudRuntime)

```python
from agent.hooks import VerificationHook, RetryHook, OutputProcessingHook

hooks = [
    VerificationHook(llm_client=self.client, semantic_model=config.model_name),
    RetryHook(max_attempts=3),
    OutputProcessingHook(),
]

self.execution_engine = ExecutionEngine(runtime=self, hooks=hooks)
```

---

## 8. Data Flow Diagram

```
Agent Loop calls engine.execute(name, params, ...)
       │
       ▼
 ┌─ ExecutionEngine ──────────────────────────────────┐
 │                                                     │
 │  1. Create ExecutionContext                          │
 │  2. Pre-hooks: [MetricsHook.before_execute]         │
 │                                                     │
 │  ┌─ Retry Loop (engine owns) ───────────────────┐   │
 │  │                                               │   │
 │  │  3. _invoke() → ExecutionResult               │   │
 │  │                                               │   │
 │  │  4. After-hooks (in order):                   │   │
 │  │     ├─ VerificationHook                       │   │
 │  │     │   L1 deterministic → VerificationResult │   │
 │  │     │   L2 semantic (if needed) → VR          │   │
 │  │     │   Stores in ctx.shared["verification"]  │   │
 │  │     │                                         │   │
 │  │     ├─ RetryHook                              │   │
 │  │     │   Reads ctx.shared["verification"]      │   │
 │  │     │   Sets ctx.shared["retry_requested"]    │   │
 │  │     │                                         │   │
 │  │     └─ OutputProcessingHook                   │   │
 │  │         Skips if retry_requested              │   │
 │  │         Applies per-tool compression policy   │   │
 │  │                                               │   │
 │  │  5. if retry_requested → loop                 │   │
 │  │                                               │   │
 │  └───────────────────────────────────────────────┘   │
 │                                                     │
 │  6. Finalize: set attempts, verified, recovered     │
 │  7. Return ExecutionResult                          │
 └─────────────────────────────────────────────────────┘
       │
       ▼
 Agent Loop: result.to_model_output() → conversation
```

---

## 9. Implementation Order

### Phase 1 — Foundation (no behavioral change)
1. Create `agent/hooks/base.py` — `ExecutionHook`, `ExecutionContext`, `VerificationResult`
2. Refactor `ExecutionEngine` to accept `hooks=[]` and run the hook pipeline
3. With empty hooks list, behavior is **identical** to current code
4. **Test**: all existing flows work unchanged

### Phase 2 — VerificationHook (L1 only)
1. Create `agent/hooks/verification.py` with deterministic checks only
2. Wire it into `Session` / `CloudRuntime` hook list
3. **Test**: verification results appear in `ctx.shared`, `result.verified` is populated

### Phase 3 — RetryHook
1. Create `agent/hooks/retry.py`
2. Add retry loop logic to engine's `execute()`
3. **Test**: transient failures get retried, param failures get repair instructions

### Phase 4 — OutputProcessingHook
1. Create `agent/hooks/output_processing.py` with all policies
2. Wire as last hook
3. **Test**: shell output compressed, read_file untouched, search results truncated

### Phase 5 — Semantic Verification (L2)
1. Add `_semantic_verify()` to VerificationHook
2. Wire `LLMClient` injection
3. Add verifier system prompt + response parsing
4. **Test**: semantic checks fire for `web_search`, `subagent_*`, etc.

> [!TIP]
> Each phase is independently shippable. Phase 1 is a pure refactor with zero behavioral change. Phases 2–5 add capabilities incrementally.
