# PAT Cloud Migration — Implementation Plan v2

> **Critical Rule**: Extend, don't replace. Agent, Session, Events, ToolRegistry, ContextManager, ApprovalManager, MCPManager remain untouched.

---

## Ship Order (5 Phases)

| Phase | What | Ship When Done |
|-------|------|----------------|
| 1 | Postgres + Users + PATService + Chat API | ✅ Ship |
| 2 | Roles + Tool Filtering + Agent Profiles | ✅ Ship |
| 3 | MCP APIs + Dynamic Config | ✅ Ship |
| 4 | Event Bus + Observability | ✅ Ship |
| 5 | Memory Extraction + Failure Learning | ✅ Ship |

Each phase is independently deployable.

---

## Critical Fix: Conversation Rehydration Pipeline

Every API request must reload conversation state. The Agent is stateless per-request.

```
POST /chat (conversation_id)
         ↓
Load conversation from DB
         ↓
Load previous messages from DB
         ↓
Build Config (from DB + env)
         ↓
Create Agent + Session
         ↓
Rebuild ContextManager with loaded messages
         ↓
agent.run(new_message)
         ↓
Persist new messages to DB
         ↓
Persist conversation summary if compressed
         ↓
Return response
```

The `conversations.summary` column stores compressed context. When a summary exists, load **summary + last N messages** (not summary alone) to preserve recent context.

```
Summary exists?
     ↓ YES                    ↓ NO
Load summary              Load full message history
+                         → inject into ContextManager
Load last 20 messages
→ inject both into ContextManager
```

Implementation in PATService:

```python
REHYDRATION_RECENT_LIMIT = 20

async def _rehydrate_context(self, agent: Agent, conversation_id: str):
    """Load previous messages into ContextManager before running."""
    conversation = await self.db.fetchrow(
        "SELECT summary FROM conversations WHERE id = $1", conversation_id
    )

    if conversation["summary"]:
        # Load summary as base context
        agent.session.context_manager.replace_with_summary(conversation["summary"])

        # ALSO load last N messages so recent context is not lost
        recent = await self.db.fetch(
            "SELECT role, content, tool_call_id, tool_calls FROM messages "
            "WHERE conversation_id = $1 ORDER BY created_at DESC LIMIT $2",
            conversation_id, self.REHYDRATION_RECENT_LIMIT
        )
        recent.reverse()  # chronological order
        self._inject_messages(agent, recent)
        return

    # No summary — load full message history
    messages = await self.db.fetch(
        "SELECT role, content, tool_call_id, tool_calls FROM messages "
        "WHERE conversation_id = $1 ORDER BY created_at", conversation_id
    )
    self._inject_messages(agent, messages)

def _inject_messages(self, agent: Agent, messages: list):
    for msg in messages:
        if msg["role"] == "user":
            agent.session.context_manager.add_user_message(msg["content"])
        elif msg["role"] == "assistant":
            agent.session.context_manager.add_assistant_message(
                msg["content"], msg["tool_calls"]  # requires JSONB column
            )
        elif msg["role"] == "tool":
            agent.session.context_manager.add_tool_result(
                msg["tool_call_id"], msg["content"]  # requires tool_call_id column
            )
```

When compression happens during a run, persist the summary:

```python
await self.db.execute(
    "UPDATE conversations SET summary = $1 WHERE id = $2",
    summary_text, conversation_id
)
```

---

## PATService — Planned Decomposition

V1: Single `PATService` class. Acceptable at this scale.

Planned split when it hits ~500 lines:

```
PATService (orchestrator)
    ↓
ConversationService    — load/create/persist conversations + messages
AgentExecutionService  — build config, run agent, collect events
MemoryPipeline         — extraction, failure analysis, summarization
```

Not implemented now. But the internal methods are named to make this split trivial:
- `_rehydrate_context()` → moves to ConversationService
- `_build_config()` → moves to AgentExecutionService
- `_run_post_processing()` → moves to MemoryPipeline

---

## Phase 1: Postgres + Users + PATService + Chat API

### ORM: SQLAlchemy (async)

Use SQLAlchemy with `asyncpg` driver. Matches the directness of the existing codebase — no magic, explicit queries.

### Files to Create

#### `api/db/models.py`
SQLAlchemy ORM models (from `db_design.md`). All V1 tables:

- `users`, `roles`, `user_roles`
- `conversations`, `messages` (messages includes `tool_call_id TEXT`, `tool_calls JSONB`)
- `memories`
- `agent_profiles`, `user_agent_profiles`
- `prompts`
- `tools`, `profile_tools`
- `agent_runs`, `agent_steps`
- `mcp_servers`, `mcp_server_scopes`, `mcp_user_connections`, `mcp_credentials`, `mcp_server_configs`
- `audit_logs`

Postponed: `user_channels`, `files`, `artifacts`, `agent_checkpoints`

> **messages table note**: Must include `tool_call_id TEXT NULL` and `tool_calls JSONB NULL` columns — required for conversation rehydration to reconstruct assistant tool calls.

Seed data function for roles (`super_admin`, `admin`, `user`, `premium`) and default agent profiles.

#### `api/db/database.py`
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

class CloudDatabase:
    def __init__(self, database_url: str):
        # Convert postgresql:// to postgresql+asyncpg://
        self.engine = create_async_engine(database_url)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialize(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await self._seed_defaults()

    async def shutdown(self):
        await self.engine.dispose()

    def get_session(self) -> AsyncSession:
        return self.session_factory()
```

#### `api/auth/service.py`
```python
class AuthService:
    def __init__(self, db: CloudDatabase):
        self.db = db

    async def create_user(self, email, display_name) -> dict: ...
    async def get_user(self, user_id) -> dict | None: ...
    async def get_user_roles(self, user_id) -> list[str]: ...
    async def assign_role(self, user_id, role_name): ...
    def create_token(self, user_id) -> str: ...
    def verify_token(self, token) -> dict: ...
```

DEV_MODE gating for role assignment:
```python
async def assign_role(self, user_id: str, role_name: str):
    if not os.environ.get("DEV_MODE"):
        raise PermissionError("Role assignment disabled in production")
    ...
```

#### `api/auth/dependencies.py`
FastAPI dependency to extract current user from JWT Bearer token.

#### `api/auth/models.py`
Pydantic request/response models: `UserCreate`, `UserResponse`, `TokenResponse`.

#### `api/pat_service.py`
```python
class PATService:
    def __init__(self, db: CloudDatabase):
        self.db = db

    async def chat(self, user_id, message, conversation_id=None) -> dict:
        # 1. Load user + profile → get allowed_tools
        # 2. Build Config from DB (agent_profiles) + env vars
        # 3. Create/load conversation
        # 4. Create agent_run record with status="running" BEFORE agent starts
        # 5. Create Agent
        # 6. Rehydrate context (summary + last N messages)
        # 7. Run agent.run(message), collect events
        # 8. Persist new messages (with tool_call_id + tool_calls)
        # 9. If compression happened, persist summary
        # 10. Update agent_run status="completed"
        # 11. Return final response
        #
        # On exception: update agent_run status="failed", error_message=str(e)

        run_id = await self._create_agent_run(user_id, conversation_id, message)
        try:
            ...  # steps 5-9
            await self._update_agent_run(run_id, status="completed", response=final_response)
        except Exception as e:
            await self._update_agent_run(run_id, status="failed", error=str(e))
            raise

    async def _create_agent_run(self, user_id, conversation_id, message) -> str:
        # INSERT INTO agent_runs (status='running', started_at=now())
        # Returns run_id
        ...

    async def _update_agent_run(self, run_id, status, response=None, error=None):
        # UPDATE agent_runs SET status=$1, completed_at=now(), final_response=$2, error_message=$3
        ...

    async def _build_config(self, user_id) -> Config:
        # Load agent_profile for user
        # Load prompt from prompts table
        # Build Config with model, temperature, max_turns, allowed_tools
        # MCP configs loaded from mcp_servers + mcp_user_connections
        # approval = ApprovalPolicy.AUTO for API mode

    async def _rehydrate_context(self, agent, conversation_id):
        # Load summary + last N messages → inject into ContextManager

    async def _get_allowed_tools(self, user_id) -> list[str] | None:
        # profile → profile_tools → tool names
        # Returns None for super_admin/admin (all tools)
```

#### `api/routes/users.py`
```
POST /users           → create user (DEV_MODE only for role assignment)
GET  /users/{id}      → get user + roles
```

#### `api/routes/chat.py`
```
POST /chat            → { message, conversation_id? } → { conversation_id, response }
```

Blocks until Agent finishes. No streaming.

#### `api/app.py` (overwrite existing stub)
```python
app = FastAPI(title="PAT API", lifespan=lifespan)
# lifespan: init CloudDatabase, AuthService, PATService
# Include routers, CORS middleware
```

### Dependencies to Add
```
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.30.0
PyJWT>=2.8.0
fastapi>=0.115.0
uvicorn>=0.30.0
```

### Validation
- Terminal agent unchanged (`main.py` works)
- POST /users creates user
- POST /chat returns complete response
- Conversation rehydration works across requests
- Compressed conversations load from summary

---

## Phase 2: Roles + Tool Filtering + Agent Profiles

### What Changes
- `api/auth/service.py` gains `get_allowed_tools_for_profile()`
- Tool authorization flows: `user → user_agent_profiles → agent_profiles → profile_tools → tools`
- PATService passes `allowed_tools` to Config — ToolRegistry filters automatically via existing `config.allowed_tools`

### Files to Create/Modify

#### `api/routes/users.py` — add role endpoints
```
POST /users/{id}/roles  → assign role (DEV_MODE gated)
```

#### `api/auth/service.py` — extend
```python
async def get_user_profile(self, user_id) -> dict:
    # user → user_agent_profiles → agent_profiles
    ...

async def get_allowed_tools(self, user_id) -> list[str] | None:
    # profile → profile_tools → tools.name
    # Returns None for admin profiles (all tools)
    ...
```

### How Tool Authorization Works
```
User Request
     ↓
AuthService.get_allowed_tools(user_id)
     ↓
Returns ["read_file", "grep", "memory", ...]
     ↓
Config(allowed_tools=["read_file", "grep", "memory"])
     ↓
ToolRegistry.get_tools() filters by config.allowed_tools  ← ALREADY EXISTS
     ↓
ToolRegistry.get_schemas() calls get_tools()              ← ALREADY EXISTS
     ↓
Model only sees authorized tools
```

**Verified**: `ToolRegistry.get_tools()` (registry.py:57-59) already filters by `config.allowed_tools`. `get_schemas()` (registry.py:64-65) calls `get_tools()`. Both builtins and MCP tools are filtered. Security chain is complete — zero changes needed.

### Audit Actions
Record to `audit_logs`:
- `ROLE_ASSIGNED` — when role assigned
- `PROFILE_UPDATED` — when profile changed

### Validation
- Admin user sees all tools
- Regular user sees restricted tools
- Model never receives unauthorized tool schemas
- Role assignment blocked without DEV_MODE

---

## Phase 3: MCP APIs + Dynamic Config

### Files to Create

#### `api/mcp/cloud_mcp_service.py`
```python
class CloudMCPService:
    def __init__(self, db: CloudDatabase):
        self.db = db

    async def register_server(self, name, display_name, server_url, transport, ...):
        # Insert into mcp_servers
        ...

    async def connect_for_user(self, user_id, server_name):
        # Create mcp_user_connections record
        # Status: connected
        ...

    async def disconnect_for_user(self, user_id, server_name):
        # Update status: disconnected
        ...

    async def disable_for_user(self, user_id, server_name):
        # Update status: disabled
        ...

    async def get_user_connections(self, user_id) -> list[dict]:
        ...

    async def build_mcp_configs(self, user_id) -> dict[str, MCPServerConfig]:
        """Bridge: DB records → Config.mcp_servers dict.
        Only loads connections with status='connected'.
        MCPManager reads Config.mcp_servers as-is."""
        ...
```

#### `api/routes/mcp.py`
```
POST /mcp/connect       → connect MCP for user
POST /mcp/disconnect    → disconnect MCP for user
GET  /mcp/list          → list available MCP servers
GET  /mcp/status        → user's connection statuses
```

### MCP Connection Statuses

| Status | Meaning |
|--------|---------|
| `connected` | Active, tokens valid |
| `expired` | Token expired, needs refresh |
| `error` | Connection failed |
| `refresh_required` | Refresh token available but access token expired |
| `disabled` | Manually disabled by user/admin |
| `disconnected` | User disconnected |

### MCP OAuth — Defined But Deferred

V1 scope for OAuth:
- Store encrypted tokens in `mcp_credentials`
- Encryption via `cryptography.fernet` with key from `MCP_ENCRYPTION_KEY` env var
- No automatic token refresh in V1
- No OAuth consent flow in V1 — tokens are manually inserted (dev mode)

Future OAuth lifecycle (documented, not built):
```
Consent → callback → store encrypted tokens
         ↓
Token expires → check expires_at → set status = "refresh_required"
         ↓
Refresh attempt → success → status = "connected"
         ↓
Refresh fails → status = "expired"
         ↓
Key rotation → re-encrypt all tokens with new key
```

### Audit Actions
- `MCP_CONNECTED`
- `MCP_DISCONNECTED`

### Validation
- Register MCP server in DB
- Connect server for user
- PATService loads MCP configs from DB → passes to Config
- MCPManager works unchanged

---

## Phase 4: Event Bus + Buffered Observability

### Key Design: Buffered Step Recorder

Events are buffered in memory and flushed in batch — not one DB write per event.

### Files to Create

#### `api/events/event_bus.py`
```python
class EventSubscriber:
    async def handle(self, event: AgentEvent, context: dict):
        raise NotImplementedError

    async def flush(self):
        """Called at end of agent run to flush any buffered data."""
        pass

class EventBus:
    def __init__(self):
        self._subscribers: list[EventSubscriber] = []

    def subscribe(self, subscriber: EventSubscriber):
        self._subscribers.append(subscriber)

    async def publish(self, event: AgentEvent, context: dict):
        for sub in self._subscribers:
            try:
                await sub.handle(event, context)
            except Exception as e:
                logger.exception(f"EventBus subscriber {sub.__class__.__name__} failed: {e}")
                # Never break agent flow, but always log

    async def flush_all(self):
        """Flush all subscriber buffers. Called once after agent completes."""
        for sub in self._subscribers:
            try:
                await sub.flush()
            except Exception as e:
                logger.exception(f"EventBus flush failed for {sub.__class__.__name__}: {e}")
```

#### `api/events/subscribers.py`
```python
class StepRecorder(EventSubscriber):
    """Buffers agent steps in memory, flushes to DB after run completes."""
    def __init__(self, db: CloudDatabase):
        self.db = db
        self._buffer: list[dict] = []
        self._step_count = 0

    async def handle(self, event, context):
        if event.type in (AgentEventType.TOOL_CALL_START,
                          AgentEventType.TOOL_CALL_COMPLETE,
                          AgentEventType.TEXT_COMPLETE,
                          AgentEventType.AGENT_ERROR):
            self._step_count += 1
            self._buffer.append({...})

    async def flush(self):
        if not self._buffer:
            return
        # Batch insert all steps
        await self.db.executemany(
            "INSERT INTO agent_steps (...) VALUES (...)",
            [step.values() for step in self._buffer]
        )
        self._buffer.clear()

class AuditRecorder(EventSubscriber):
    """Records audit-worthy events."""
    ...
```

### Integration with PATService
```python
async for event in agent.run(message):
    await self.event_bus.publish(event, context)
    ...

# After agent completes
await self.event_bus.flush_all()
```

### Audit Actions Recorded
- `ROLE_ASSIGNED`, `MCP_CONNECTED`, `MCP_DISCONNECTED`
- `MEMORY_DELETED`, `PROFILE_UPDATED`

### Validation
- Steps buffered during run
- Single batch insert after completion
- Subscriber failure doesn't crash agent
- agent_steps table populated after chat

---

## Phase 5: Memory Extraction + Failure Learning

### Memory Eligibility Check

Post-processing only runs when warranted:

```python
MEMORY_MIN_MESSAGE_THRESHOLD = 3

def _should_run_post_processing(self, events: list[AgentEvent], messages: list[dict]) -> bool:
    tool_used = any(e.type == AgentEventType.TOOL_CALL_COMPLETE for e in events)
    has_failure = any(
        e.type == AgentEventType.TOOL_CALL_COMPLETE and not e.data.get("success")
        for e in events
    )
    conversation_length = len(messages)

    # Always run if tools were used or failures occurred
    if tool_used or has_failure:
        return True

    # Run if conversation is long enough (user may share personal facts
    # like "my birthday is June 15" without triggering tools)
    if conversation_length >= self.MEMORY_MIN_MESSAGE_THRESHOLD:
        return True

    return False
```

### Memory Importance Scoring

Memories are only stored if importance > threshold:

```python
async def _store_if_important(self, memory: dict, threshold: float = 0.7):
    if memory.get("importance", 0) < threshold:
        return  # Discard low-importance memories
    await self.cloud_memory.add_memory(...)
```

The LLM assigns importance scores during extraction. The threshold prevents memory pollution.

### Files to Create

#### `api/prompts/memory_extractor.py`
```python
def get_memory_extraction_prompt() -> str:
    """Instructs LLM to extract memories with importance scores."""
    ...

async def extract_memories(client: LLMClient, messages: list[dict]) -> list[dict]:
    """Returns [{content, importance, memory_type, source_type}]"""
    ...
```

#### `api/prompts/failure_analyzer.py`
```python
async def analyze_failures(client: LLMClient, events: list[AgentEvent]) -> list[dict]:
    """Analyze failed tool calls → lesson-learned memories.
    Only called when failures exist."""
    ...
```

#### `api/prompts/task_summarizer.py`
```python
async def summarize_task(client: LLMClient, events: list[AgentEvent], response: str) -> dict:
    """Structured summary: task, tools, decisions, outcome.
    importance score included for storage decision."""
    ...
```

### Memory Storage — Qdrant + PostgreSQL

Qdrant for embeddings/similarity search. PostgreSQL `memories` table for metadata, traceability, importance scores.

#### `api/memory/cloud_memory.py`
```python
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

class CloudMemoryStore:
    """PostgreSQL for metadata + Qdrant for embeddings."""

    def __init__(self, db: CloudDatabase, qdrant: AsyncQdrantClient, user_id: str):
        self.db = db
        self.qdrant = qdrant
        self.user_id = user_id
        self.collection = "pat_memories"

    async def add_memory(self, content, metadata, memory_type, importance, ...):
        # 1. Generate embedding
        # 2. Store vector in Qdrant with user_id in payload
        # 3. Store metadata row in PostgreSQL memories table
        #    (embedding_id = Qdrant point ID)
        ...

    async def search(self, query, top_k=5):
        # 1. Embed query
        # 2. Search Qdrant with user_id filter
        # 3. Enrich with PostgreSQL metadata (importance, source_type, etc.)
        ...
```

Existing `FaissMemoryStore` remains for terminal mode.

### Validation
- Post-processing skipped for "Hi" / "Hello" conversations
- Memories below importance threshold discarded
- Failure analysis only runs when failures exist
- Memories stored in vector DB + PostgreSQL

---

## File Creation Order (All Phases)

```
Phase 1:
  api/__init__.py
  api/db/__init__.py
  api/db/models.py
  api/db/postgres.py
  api/auth/__init__.py
  api/auth/models.py
  api/auth/service.py
  api/auth/dependencies.py
  api/pat_service.py
  api/routes/__init__.py
  api/routes/users.py
  api/routes/chat.py
  api/app.py (overwrite)

Phase 2:
  (extend api/auth/service.py)
  (extend api/routes/users.py)

Phase 3:
  api/mcp/__init__.py
  api/mcp/cloud_mcp_service.py
  api/routes/mcp.py

Phase 4:
  api/events/__init__.py
  api/events/event_bus.py
  api/events/subscribers.py

Phase 5:
  api/prompts/memory_extractor.py
  api/prompts/failure_analyzer.py
  api/prompts/task_summarizer.py
  api/memory/__init__.py
  api/memory/cloud_memory.py
```

---

## New Dependencies

```
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.30.0
PyJWT>=2.8.0
fastapi>=0.115.0
uvicorn>=0.30.0
cryptography>=43.0.0
qdrant-client>=1.12.0   # Phase 5
```

---

## Environment Variables

```
DATABASE_URL=postgresql://user:pass@host:5432/pat
JWT_SECRET=your-secret-key
OPENAI_API_KEY=sk-...
DEV_MODE=true
MCP_ENCRYPTION_KEY=your-fernet-key
```

---

## What Is NOT Modified

| Component | Status |
|-----------|--------|
| `agent/agent.py` | **Untouched** |
| `agent/events.py` | **Untouched** |
| `tools/registry.py` | **Untouched** |
| `tools/base.py` | **Untouched** |
| `context/manager.py` | **Untouched** |
| `context/compaction.py` | **Untouched** |
| `safety/approval.py` | **Untouched** |
| `tools/mcp/*` | **Untouched** |
| `config/config.py` | **Untouched** |
| `db/database.py` | **Untouched** |
| `vector_store/*` | **Untouched** |
| `main.py` | **Untouched** |
| `prompts/system.py` | **Untouched** |
| All builtin tools | **Untouched** |
