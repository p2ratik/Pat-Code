# Graph Report - .  (2026-06-25)

## Corpus Check
- 74 files · ~77,892 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 691 nodes · 2110 edges · 26 communities (25 shown, 1 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 313 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Patch Application Engine|Patch Application Engine]]
- [[_COMMUNITY_API Auth & Request Models|API Auth & Request Models]]
- [[_COMMUNITY_Session & Response Utilities|Session & Response Utilities]]
- [[_COMMUNITY_Patch Tool Operations|Patch Tool Operations]]
- [[_COMMUNITY_Core Agent Loop|Core Agent Loop]]
- [[_COMMUNITY_Auth Service & Profiles|Auth Service & Profiles]]
- [[_COMMUNITY_MCP System|MCP System]]
- [[_COMMUNITY_Agent Runtime Protocol|Agent Runtime Protocol]]
- [[_COMMUNITY_DB Models & Auth Service|DB Models & Auth Service]]
- [[_COMMUNITY_LLM Client & Event Bus|LLM Client & Event Bus]]
- [[_COMMUNITY_Cloud Database & Cache|Cloud Database & Cache]]
- [[_COMMUNITY_PAT Service & Profile Cache|PAT Service & Profile Cache]]
- [[_COMMUNITY_System Prompts|System Prompts]]
- [[_COMMUNITY_Cloud Agent Runtime|Cloud Agent Runtime]]
- [[_COMMUNITY_MCP Client & Auth|MCP Client & Auth]]
- [[_COMMUNITY_CloudAgentRuntime Build|CloudAgentRuntime Build]]
- [[_COMMUNITY_Runtime Initialization|Runtime Initialization]]
- [[_COMMUNITY_AgentRuntime Protocol|AgentRuntime Protocol]]
- [[_COMMUNITY_Config & MCPServerConfig|Config & MCPServerConfig]]
- [[_COMMUNITY_FastAPI App & Lifespan|FastAPI App & Lifespan]]
- [[_COMMUNITY_Vector Store & Embeddings|Vector Store & Embeddings]]
- [[_COMMUNITY_PAT Service Chat Pipeline|PAT Service Chat Pipeline]]

## God Nodes (most connected - your core abstractions)
1. `Config` - 84 edges
2. `ToolResult` - 76 edges
3. `ToolInvocation` - 70 edges
4. `Tool` - 66 edges
5. `Toolkind` - 49 edges
6. `ToolConfirmation` - 34 edges
7. `LLMClient` - 33 edges
8. `AuthService` - 32 edges
9. `Agent` - 31 edges
10. `CloudDatabase` - 31 edges

## Surprising Connections (you probably didn't know these)
- `Agent` --uses--> `LLMClient`  [INFERRED]
  agent/agent.py → client/llm_client.py
- `Agent` --uses--> `StreamEventType`  [INFERRED]
  agent/agent.py → client/response.py
- `Agent` --uses--> `TokenUsage`  [INFERRED]
  agent/agent.py → client/response.py
- `Agent` --uses--> `ToolCall`  [INFERRED]
  agent/agent.py → client/response.py
- `Agent` --uses--> `ToolResultMessage`  [INFERRED]
  agent/agent.py → client/response.py

## Import Cycles
- None detected.

## Communities (26 total, 1 thin omitted)

### Community 0 - "Patch Application Engine"
Cohesion: 0.10
Nodes (40): ApplyPatchParams, ParsedPatch, PatchAction, EditParams, EditTool, GlobParams, GlobTool, GrepParams (+32 more)

### Community 1 - "API Auth & Request Models"
Cohesion: 0.07
Nodes (65): get_current_user(), ChatRequest, ChatResponse, ProfileAssign, ProfileCreate, ProfileResponse, ProfileToolsAssign, ProfileUpdate (+57 more)

### Community 2 - "Session & Response Utilities"
Cohesion: 0.06
Nodes (22): Any, Console, MessageItem, Rule, Table, Text, _divider(), get_console() (+14 more)

### Community 3 - "Patch Tool Operations"
Cohesion: 0.08
Nodes (21): ApplyPatchTool, PatchOperation, Parse an update operation in either SEARCH/REPLACE or @@ +/- style., Read update body until next operation directive or patch end., Parse hunks with optional @@ markers and +/- line prefixes., Read content until the next operation directive., Supports a simple patch format:      ```     *** Begin Patch     *** Update, _get_agent_md_files() (+13 more)

### Community 4 - "Core Agent Loop"
Cohesion: 0.08
Nodes (12): Agent, AgentEvent, PersistenceManager, SessionSnapshot, Columns, CLI, _default_project_config(), init_project() (+4 more)

### Community 5 - "Auth Service & Profiles"
Cohesion: 0.05
Nodes (18): AuthService, Get the active agent profile assigned to this user., Silently assign the seeded 'default_user' profile to a new user.          If the, Assign an agent profile to a user. Replaces any existing assignment., List all active agent profiles., Create a new agent profile. prompt_id is optional., Partial update of an agent profile., List conversations for a user, newest first. (+10 more)

### Community 6 - "MCP System"
Cohesion: 0.12
Nodes (16): ConfigMCPServerConfig, MCPServer, MCPUserConnection, CloudMCPService, Return all connection records for a user with their server name., Upsert a batch of tool definitions into mcp_tools.          Each dict must conta, Return cached tool definitions for a given server., Connect to the live MCP server, list its tools, persist them to mcp_tools. (+8 more)

### Community 7 - "Agent Runtime Protocol"
Cohesion: 0.16
Nodes (10): AgentRuntime Protocol --------------------- The contract that any runtime passed, ApprovalPolicy, ApprovalContext, ApprovalDecision, ApprovalManager, is_dangerous_command(), is_safe_command(), str (+2 more)

### Community 8 - "DB Models & Auth Service"
Cohesion: 0.18
Nodes (22): AgentProfile, AgentRun, AgentStep, AuditLog, Base, Conversation, MCPCredential, MCPServerConfig (+14 more)

### Community 9 - "LLM Client & Event Bus"
Cohesion: 0.19
Nodes (12): AgentEventType, AsyncOpenAI, LLMClient, This function creates and returns an async Open AI client if not existing, LLM client close er jonno, parse_tool_call_arguments(), StreamEvent, StreamEventType (+4 more)

### Community 10 - "Cloud Database & Cache"
Cohesion: 0.13
Nodes (10): AsyncEngine, AsyncSession, get_all_builtin_tools(), ModelConfig, CloudDatabase, Seed the 'default_user' agent profile with a safe read-only tool set.          T, Seed the tools table with all builtin tool names.          These names are the c, ensure_tables() (+2 more)

### Community 11 - "PAT Service & Profile Cache"
Cohesion: 0.13
Nodes (10): ProfileCache, ProfileConfig, ProfileCache ------------ Redis-backed cache for per-user agent profile configur, Return the ProfileConfig for user_id, using Redis when warm.          On a cache, Drop the profile cache for a user.          Call whenever the user's profile ass, Drop the prompt-scoped cache key.          Call whenever a Prompt row's content, Drop the tools-scoped cache key.          Call whenever profile_tools are reassi, Fetch profile config in one SQL round-trip.          The query:         - Uses a (+2 more)

### Community 12 - "System Prompts"
Cohesion: 0.13
Nodes (17): _get_agents_md_section(), _get_environment_section(), _get_identity_section(), _get_memory_section(), _get_operational_section(), _get_security_section(), _get_shell_info(), get_system_prompt() (+9 more)

### Community 13 - "Cloud Agent Runtime"
Cohesion: 0.22
Nodes (5): CloudAgentRuntime ----------------- The cloud implementation of AgentRuntime.  A, TokenUsage, ChatCompactor, ContextManager, get_compression_prompt()

### Community 14 - "MCP Client & Auth"
Cohesion: 0.16
Nodes (9): Auth, MCPClient, MCPToolInfo, Resolve the authentication handler for URL-based transports.          Priority, Pick the correct HTTP transport for a URL-based MCP server.          Resolutio, MCPServerConfig, SSETransport, StdioTransport (+1 more)

### Community 15 - "CloudAgentRuntime Build"
Cohesion: 0.14
Nodes (7): CloudAgentRuntime, Build a CloudAgentRuntime from a Config.          base_registry: the application, No MCP discovery, no local tool scan — tools are already wired., Close the HTTP client., A read-only, per-request view over a shared ToolRegistry.      Wraps the singlet, Dependency-injected runtime for the cloud API.      Instantiate via CloudAgentRu, ToolRegistryView

### Community 16 - "Runtime Initialization"
Cohesion: 0.13
Nodes (5): NoOpDBManager, Satisfies the db_manager interface; does nothing.      In API mode, pat_service., Config, Keyring takes priority; env vars are the fallback.                  Accepts bo, Keyring takes priority; env vars are the fallback.                  Accepts bo

### Community 17 - "AgentRuntime Protocol"
Cohesion: 0.14
Nodes (7): AgentRuntime, Minimum surface that the Agent agentic loop needs., Start async resources (MCP, tool discovery, context setup)., Tear down async resources (MCP connections, HTTP clients)., Satisfy AgentRuntime protocol: tear down MCP + HTTP client., Session, Protocol

### Community 18 - "Config & MCPServerConfig"
Cohesion: 0.19
Nodes (6): MCPServerConfig, ShellEnvironmentPolicy, SubagentDefinition, Enum, MCPServerStatus, MCPManager

### Community 19 - "FastAPI App & Lifespan"
Cohesion: 0.24
Nodes (3): lifespan(), ConversationContextRepository, FastAPI

### Community 21 - "PAT Service Chat Pipeline"
Cohesion: 0.27
Nodes (4): PATService, Build a per-request Config from the cached ProfileConfig.          mcp_configs i, Return a valid conversation_id owned by user_id.          - None → create a new, Write compaction summary to PostgreSQL + Redis cache.          Called after a ru

## Knowledge Gaps
- **1 isolated node(s):** `SubagentDefinition`
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `Runtime Initialization` to `Patch Application Engine`, `API Auth & Request Models`, `Session & Response Utilities`, `Patch Tool Operations`, `Core Agent Loop`, `Agent Runtime Protocol`, `LLM Client & Event Bus`, `Cloud Database & Cache`, `PAT Service & Profile Cache`, `System Prompts`, `Cloud Agent Runtime`, `MCP Client & Auth`, `CloudAgentRuntime Build`, `AgentRuntime Protocol`, `Config & MCPServerConfig`, `FastAPI App & Lifespan`, `PAT Service Chat Pipeline`?**
  _High betweenness centrality (0.357) - this node is a cross-community bridge._
- **Why does `AuthService` connect `Auth Service & Profiles` to `DB Models & Auth Service`, `Cloud Database & Cache`, `FastAPI App & Lifespan`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Why does `CloudDatabase` connect `Cloud Database & Cache` to `Patch Application Engine`, `Auth Service & Profiles`, `MCP System`, `Agent Runtime Protocol`, `DB Models & Auth Service`, `PAT Service & Profile Cache`, `Runtime Initialization`, `FastAPI App & Lifespan`, `PAT Service Chat Pipeline`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Are the 32 inferred relationships involving `Config` (e.g. with `Agent` and `AgentRuntime`) actually correct?**
  _`Config` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `ToolResult` (e.g. with `AgentEvent` and `AgentEventType`) actually correct?**
  _`ToolResult` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 33 inferred relationships involving `ToolInvocation` (e.g. with `ApplyPatchParams` and `ApplyPatchTool`) actually correct?**
  _`ToolInvocation` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 39 inferred relationships involving `Tool` (e.g. with `CloudAgentRuntime` and `NoOpDBManager`) actually correct?**
  _`Tool` has 39 INFERRED edges - model-reasoned connections that need verification._