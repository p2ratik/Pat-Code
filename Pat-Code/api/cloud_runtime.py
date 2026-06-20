"""
CloudAgentRuntime
-----------------
The cloud implementation of AgentRuntime.

Assembled by dependency injection in pat_service.py:
  - LLMClient        → reads API key from env (already fixed in config.py)
  - ContextManager   → plain in-memory, no local config file
  - ToolRegistry     → create_default_registry (same tool logic as CLI)
  - ChatCompactor    → same
  - ApprovalManager  → AUTO policy (no interactive prompts)
  - NoOpDBManager    → pat_service.py handles persistence to PostgreSQL

No MCP discovery.  No local FAISS.  No local SQLite session log.
Tools / MCPs will eventually be loaded from PostgreSQL — just swap the
registry construction here without touching Agent or the agentic loop.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from pathlib import Path

from client.llm_client import LLMClient
from context.compaction import ChatCompactor
from context.manager import ContextManager
from safety.approval import ApprovalManager, ApprovalPolicy
from tools.registry import create_default_registry
from tools.base import Tool
from config.config import Config, ModelConfig


class NoOpDBManager:
    """Satisfies the db_manager interface; does nothing.

    In API mode, pat_service.py persists messages to PostgreSQL directly —
    we don't want a second write to local SQLite.
    """
    def add_msg_to_db(self, columns) -> None:  # noqa: ANN001
        pass


class ToolRegistryView:
    """A read-only, per-request view over a shared ToolRegistry.

    Wraps the singleton base_registry without mutating it.
    Applies per-request allowed_tools filtering from config.
    Delegates all writes (register, unregister) to the underlying registry.
    """

    def __init__(self, base_registry, config: Config):
        self._base = base_registry
        self.config = config

    def get_tools(self) -> list[Tool]:
        tools = list(self._base._tools.values()) + list(self._base._mcp_tools.values())
        if self.config.allowed_tools is not None:
            allowed = set(self.config.allowed_tools)
            tools = [t for t in tools if t.name in allowed]
        return tools

    def get_schemas(self):
        return [t.to_openai_schema() for t in self.get_tools()]

    def get(self, name: str):
        # Allow lookup only for tools this view is authorized to use
        if self.config.allowed_tools is not None and name not in set(self.config.allowed_tools):
            return None
        return self._base.get(name)

    async def invoke(self, name, params, cwd, session, approval_manager=None):
        # Defense in depth: block execution even if the LLM hallucinates
        # a tool name that wasn't in the filtered schemas.
        if self.config.allowed_tools is not None and name not in set(self.config.allowed_tools):
            from tools.base import ToolResult
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
        tool_registry,
        chat_compactor: ChatCompactor,
        approval_manager: ApprovalManager,
        db_manager=None,
    ):
        self.config = config
        self.client = client
        self.context_manager = context_manager
        self.tool_registry = tool_registry
        self.chat_compactor = chat_compactor
        self.approval_manager = approval_manager
        self.db_manager = db_manager or NoOpDBManager()

        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.now()
        self._turn_count = 0

    # ------------------------------------------------------------------
    # Factory — wires up all defaults for the API service
    # ------------------------------------------------------------------
    @classmethod
    def build(cls, config: Config, base_registry=None) -> "CloudAgentRuntime":
        """Build a CloudAgentRuntime from a Config.

        base_registry: the application-wide ToolRegistry singleton built at
          startup. If supplied, it is reused directly — no builtin re-scan.
          ToolRegistry.get_tools() already filters by config.allowed_tools
          lazily at call time, so per-user tool restrictions still apply.

          Falls back to create_default_registry(config) for tests or CLI use.
        """
        client = LLMClient(config)

        if base_registry is not None:
            # Wrap the shared singleton in a per-request view.
            # No mutation of base_registry — safe under concurrent requests.
            tool_registry = ToolRegistryView(base_registry, config)
        else:
            # Fallback for tests or when called without app.state
            tool_registry = create_default_registry(config)

        chat_compactor = ChatCompactor(client)
        approval_manager = ApprovalManager(ApprovalPolicy.AUTO, config.cwd)

        # ContextManager needs tools — call get_tools() after registry is ready
        context_manager = ContextManager(
            config=config,
            user_memory=None,       # no local user_memory.json in cloud
            tools=tool_registry.get_tools(),
        )

        # Apply per-profile system prompt override from the DB prompts table.
        # We set _system_prompt directly — ContextManager is already constructed,
        # so this is the cleanest injection point without changing its __init__.
        if config.system_prompt_override:
            context_manager._system_prompt = config.system_prompt_override

        return cls(
            config=config,
            client=client,
            context_manager=context_manager,
            tool_registry=tool_registry,
            chat_compactor=chat_compactor,
            approval_manager=approval_manager,
        )

    # ------------------------------------------------------------------
    # AgentRuntime protocol
    # ------------------------------------------------------------------
    def increment_turn(self) -> int:
        self._turn_count += 1
        return self._turn_count

    async def initialize(self) -> None:
        """No MCP discovery, no local tool scan — tools are already wired."""
        pass

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        await self.client.close()
