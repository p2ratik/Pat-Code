"""
AgentRuntime Protocol
---------------------
The contract that any runtime passed to Agent must satisfy.

Two implementations exist:
  - Session (agent/session.py)   → local CLI runtime
  - CloudAgentRuntime (api/cloud_runtime.py) → cloud API runtime, assembled by DI

The Agent loop only imports this protocol, never a concrete implementation.
"""
from __future__ import annotations
from typing import Any, Protocol, runtime_checkable

from client.llm_client import LLMClient
from context.manager import ContextManager
from context.compaction import ChatCompactor
from safety.approval import ApprovalManager
from tools.registry import ToolRegistry
from config.config import Config


@runtime_checkable
class AgentRuntime(Protocol):
    """Minimum surface that the Agent agentic loop needs."""

    # --- identity ---
    session_id: str
    config: Config          # agent needs max_turns + model_name

    # --- core components ---
    client: LLMClient
    context_manager: ContextManager
    chat_compactor: ChatCompactor
    tool_registry: ToolRegistry
    approval_manager: ApprovalManager

    # --- optional persistence (NoOpDBManager for cloud) ---
    db_manager: Any

    def increment_turn(self) -> int: ...

    async def initialize(self) -> None:
        """Start async resources (MCP, tool discovery, context setup)."""
        ...

    async def shutdown(self) -> None:
        """Tear down async resources (MCP connections, HTTP clients)."""
        ...
