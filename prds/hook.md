                ExecutionEngine
                        │
                        ▼
              Execution Pipeline
                        │
      ┌─────────────────┼─────────────────┐
      ▼                 ▼                 ▼
 Pre Hooks         Tool Execution     Post Hooks

The engine owns:

the lifecycle
execution context
ordering
cancellation
timing
state transitions

The hooks own:

validation
verification
retries
logging
telemetry
recovery
approvals
I'd make hooks first-class citizens

Something like

class ExecutionHook(ABC):

    async def before_execute(
        self,
        ctx: ExecutionContext,
    ) -> None:
        pass

    async def after_execute(
        self,
        ctx: ExecutionContext,
        result: ExecutionResult,
    ) -> ExecutionResult:
        return result

Then

class ExecutionEngine:

    async def execute(...):

        for hook in self.pre_hooks:
            await hook.before_execute(ctx)

        result = await self._invoke(...)

        execution = ExecutionResult(...)

        for hook in self.post_hooks:
            execution = await hook.after_execute(ctx, execution)

        return execution

Notice how the engine doesn't know what the hooks do.

I would actually avoid naming one hook "ErrorClassifier"

Instead think about capabilities.

For example

ValidationHook

VerificationHook

RetryHook

MetricsHook

LoggingHook

ApprovalHook

TracingHook

CachingHook

Each hook has exactly one concern.

RetryHook is especially interesting

The RetryHook can literally wrap the execution loop.

Imagine

invoke

↓

failed

↓

RetryHook

↓

retry?

↓

invoke again

The ExecutionEngine doesn't need to know why something was retried.

The hook decides.

VerificationHook

This is where I'd move things like

empty output
malformed JSON
invalid tool output
output invariants

Example

if not result.output:
    result.verified = False

No exceptions.

Just verification.

ClassificationHook

Instead of parsing every error itself, it can simply normalize.

result.classification = ErrorClass.USER_ERROR

or

RATE_LIMIT

based on the metadata already present.

Here's one thing I would add

I wouldn't have before and after hooks as two completely separate systems.

I'd define a single hook interface:

class ExecutionHook(ABC):

    async def before_execute(...):
        ...

    async def after_execute(...):
        ...

Most hooks will implement only one.

For example

class RateLimitHook:

    async def before_execute(...):
        ...

No after.

class VerificationHook:

    async def after_execute(...):
        ...

No before.

class MetricsHook:

    async def before_execute(...):
        self.start = time.perf_counter()

    async def after_execute(...):
        ...

Uses both.

Very flexible.

The one hook I would not implement

I wouldn't create a generic

ErrorHook

Errors are already represented by ExecutionResult.

The hook should transform

ExecutionResult

↓

ExecutionResult

instead of throwing exceptions around.

One architectural tweak I'd make

Instead of

ExecutionEngine

↓

Hook A

↓

Hook B

↓

Hook C

I'd introduce an ExecutionContext.

class ExecutionContext:

    invocation

    tool

    attempt

    start_time

    metadata

    shared_state

Every hook receives the same context.

That way hooks can communicate without mutating ExecutionResult.

For example:

ctx.shared["retry_after"] = 30

The RetryHook can read it later.

Or

ctx.shared["approval_granted"] = True

The ApprovalHook sets it.

No coupling between hooks.

This is the architecture I'd personally build
ExecutionEngine
│
├── Create ExecutionContext
│
├── Run before hooks
│      ├── ApprovalHook
│      ├── RateLimitHook
│      ├── ValidationHook
│      └── MetricsHook(start)
│
├── Invoke Tool
│
├── Create ExecutionResult
│
├── Run after hooks
│      ├── VerificationHook
│      ├── ClassificationHook
│      ├── RetryHook
│      ├── LoggingHook
│      └── MetricsHook(stop)
│
└── Return ExecutionResult
One final suggestion

Since PAT is growing into a proper runtime, I'd make hooks registerable rather than hard-coded:

engine = ExecutionEngine(
    hooks=[
        ValidationHook(),
        MetricsHook(),
        VerificationHook(),
        ClassificationHook(),
        RetryHook(),
    ]
)

