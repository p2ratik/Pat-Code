"""
CloudAgentRuntime
-----------------
The cloud implementation of AgentRuntime.

Assembled by dependency injection in pat_service.py:
  - LLMClient       -> reads API key from env
  - ContextManager  -> plain in-memory, no local config file
  - ToolRegistry    -> create_default_registry (same tool logic as CLI)
  - ChatCompactor   -> same
  - ApprovalManager -> AUTO policy (no interactive prompts)
  - NoOpDBManager   -> pat_service.py handles persistence to PostgreSQL

MCP servers: MCPManager is instantiated per-request because each user has
different connected servers and different OAuth tokens. initialize() connects
them all concurrently and then rebuilds the system prompt so the LLM knows
which MCP tools it has access to. shutdown() tears everything down.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from pathlib import Path

from agent.execution_engine import ExecutionEngine
from agent.hooks import VerificationHook, RetryHook, SemanticVerificationHook, OutputProcessingHook
from client.llm_client import LLMClient
from context.compaction import ChatCompactor
from context.manager import ContextManager
from safety.approval import ApprovalManager, ApprovalPolicy
from tools.registry import create_default_registry
from tools.base import Tool, ToolInvocation, ToolResult
from tools.mcp.mcp_manager import MCPManager
from tools.mcp.client import MCPServerStatus
from tools.mcp.mcp_tool import MCPTool
from prompts.system import get_system_prompt
from config.config import Config


class NoOpDBManager:
    """Satisfies the db_manager interface; does nothing.

    In API mode, pat_service.py persists messages to PostgreSQL directly.
    """
    def add_msg_to_db(self, columns) -> None:
        pass


class ToolRegistryView:
    """A read-only, per-request view over a shared ToolRegistry.

    Wraps the singleton base_registry without mutating it.
    Applies per-request allowed_tools filtering for builtin tools only.
    MCP tools bypass the allowlist: the user's OAuth connection is the
    authorization signal — they explicitly chose to connect that server.
    """

    def __init__(self, base_registry, config: Config):
        self._base = base_registry
        self.config = config
        # Populated by CloudAgentRuntime.initialize() after MCP connects.
        self._mcp_tools: dict[str, Tool] = {}

    def get_tools(self) -> list[Tool]:
        # Builtins filtered by the profile's allowed_tools list.
        builtins = list(self._base._tools.values())
        if self.config.allowed_tools is not None:
            allowed = set(self.config.allowed_tools)
            builtins = [t for t in builtins if t.name in allowed]
        # MCP tools always exposed — explicit connection is authorization.
        return builtins + list(self._mcp_tools.values())

    def get_schemas(self):
        return [t.to_openai_schema() for t in self.get_tools()]

    def get(self, name: str) -> Tool | None:
        # MCP tools take precedence and bypass the allowlist.
        if name in self._mcp_tools:
            return self._mcp_tools[name]
        if self.config.allowed_tools is not None and name not in set(self.config.allowed_tools):
            return None
        return self._base.get(name)

    async def invoke(self, name: str, params: dict, cwd: Path, session, approval_manager=None) -> ToolResult:
        # MCP tools: dispatch directly — they live in self._mcp_tools,
        # NOT in self._base._mcp_tools (which is always empty in cloud mode).
        if name in self._mcp_tools:
            tool = self._mcp_tools[name]
            invocation = ToolInvocation(params=params, cwd=cwd, session=session)
            try:
                return await tool.execute(invocation)
            except Exception as exc:
                return ToolResult.error_result(
                    error=f"MCP tool '{name}' raised an error: {exc}",
                    metadata={"tool_name": name},
                )

        # Builtin tools: enforce allowlist then delegate to base registry.
        if self.config.allowed_tools is not None and name not in set(self.config.allowed_tools):
            return ToolResult.error_result(
                error=f"Tool '{name}' is not authorized for this user profile.",
                metadata={"tool_name": name},
            )
        return await self._base.invoke(name, params, cwd, session, approval_manager)


class CloudAgentRuntime:
    """
    Dependency-injected runtime for the cloud API.

    Instantiate via CloudAgentRuntime.build(config) or supply each
    dependency directly for testing.
    """

    def __init__(
        self,
        config: Config,
        client: LLMClient,
        context_manager: ContextManager,
        tool_registry: ToolRegistryView,
        chat_compactor: ChatCompactor,
        approval_manager: ApprovalManager,
        db_manager=None,
        mcp_manager: MCPManager | None = None,
    ):
        self.config = config
        self.client = client
        self.context_manager = context_manager
        self.tool_registry = tool_registry
        self.chat_compactor = chat_compactor
        self.approval_manager = approval_manager
        self.db_manager = db_manager or NoOpDBManager()
        self._mcp_manager = mcp_manager

        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.now()
        self._turn_count = 0

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------
    @classmethod
    def build(cls, config: Config, base_registry=None) -> "CloudAgentRuntime":
        """Build a CloudAgentRuntime from a Config.

        base_registry: the application-wide ToolRegistry singleton built at
          startup. Reused via ToolRegistryView — no builtin re-scan per request.
          MCP tools are added per-request inside initialize().
        """
        client = LLMClient(config)

        if base_registry is not None:
            tool_registry = ToolRegistryView(base_registry, config)
        else:
            tool_registry = create_default_registry(config)

        # MCPManager is per-request: each user has different servers and tokens.
        mcp_manager = MCPManager(config) if config.mcp_servers else None

        chat_compactor = ChatCompactor(client)
        approval_manager = ApprovalManager(ApprovalPolicy.AUTO, config.cwd)

        # Build ContextManager with builtins only for now.
        # initialize() will reconnect MCP and rebuild the system prompt.
        context_manager = ContextManager(
            config=config,
            user_memory=None,
            tools=tool_registry.get_tools(),
        )

        if config.system_prompt_override:
            context_manager._system_prompt = config.system_prompt_override

        runtime = cls(
            config=config,
            client=client,
            context_manager=context_manager,
            tool_registry=tool_registry,
            chat_compactor=chat_compactor,
            approval_manager=approval_manager,
            mcp_manager=mcp_manager,
        )
        runtime.execution_engine = ExecutionEngine(
            runtime=runtime,
            hooks=[
                VerificationHook(),
                SemanticVerificationHook(client),
                RetryHook(),
                OutputProcessingHook(),
            ],
        )
        return runtime

    # ------------------------------------------------------------------
    # AgentRuntime protocol
    # ------------------------------------------------------------------
    def increment_turn(self) -> int:
        self._turn_count += 1
        return self._turn_count

    async def initialize(self) -> None:
        """Connect MCP servers, register their tools, and rebuild the system prompt.

        Called by Agent.__aenter__() before the agentic loop starts.
        The system prompt must be rebuilt here because ContextManager.__init__
        bakes it from the tool list — MCP tools aren't available yet at build time.
        """
        if not self._mcp_manager:
            return

        await self._mcp_manager.initialize()

        # Inject connected MCP tools into the per-request view.
        if isinstance(self.tool_registry, ToolRegistryView):
            for client in self._mcp_manager._clients.values():
                if client.status != MCPServerStatus.CONNECTED:
                    continue
                for tool_info in client.tools:
                    mcp_tool = MCPTool(
                        tool_info=tool_info,
                        client=client,
                        config=self.config,
                        name=f"{client.name}__{tool_info.name}",
                    )
                    self.tool_registry._mcp_tools[mcp_tool.name] = mcp_tool

        # Rebuild the system prompt so the LLM sees MCP tool names.
        # Skip this if a profile override was set — it takes precedence.
        if not self.config.system_prompt_override:
            self.context_manager._system_prompt = get_system_prompt(
                config=self.config,
                user_memory=None,
                tools=self.tool_registry.get_tools(),
            )

    async def shutdown(self) -> None:
        """Disconnect MCP servers and close the LLM HTTP client."""
        if self._mcp_manager:
            await self._mcp_manager.shutdown()
        await self.client.close()
