from datetime import datetime
import json
from typing import Any
import uuid

from agent.execution_engine import ExecutionEngine
from agent.hooks import VerificationHook, RetryHook, SemanticVerificationHook, OutputProcessingHook, RepoIntelSyncHook
from client.llm_client import LLMClient
from config.config import Config
from config.loader import get_data_dir
from context.compaction import ChatCompactor
from context.manager import ContextManager
from safety.approval import ApprovalManager
from tools.discovery import ToolDiscoveryManager
from tools.mcp.mcp_manager import MCPManager
from tools.registry import create_default_registry
from db.database import DataBaseManager
from vector_store.memory_manager import FaissMemoryStore
from repo_intel.intelligence import RepoIntelligence


# Every session will have its own context, memory, tools, mcps and all
class Session:
    def __init__(self, config=Config, enable_memory: bool = True):
        self.config = config
        self.client = LLMClient(self.config)
        self.tool_registry = create_default_registry(config)
        self.execution_engine = ExecutionEngine(
            runtime=self,
            hooks=[
                VerificationHook(),
                SemanticVerificationHook(self.client),
                RetryHook(),
                OutputProcessingHook(),
                RepoIntelSyncHook(),
            ],
        )
        self.context_manager: ContextManager | None
        self.discovery_manager = ToolDiscoveryManager(
            self.config,
            self.tool_registry,
        )
        self.mcp_manager = MCPManager(self.config)
        self.chat_compactor = ChatCompactor(self.client)
        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.approval_manager = ApprovalManager(
            self.config.approval,
            self.config.cwd,
        )
        self.turn_count = 0
        self.db_manager = DataBaseManager()
        # Only load the FAISS + HuggingFace embedding model when actually needed.
        # The API service sets enable_memory=False to skip this entirely.
        self.memory_manager = FaissMemoryStore() if enable_memory else None
        self._repo_intel: RepoIntelligence | None = None

    def get_repo_intel(self) -> RepoIntelligence:
        """Return the session-scoped RepoIntelligence, creating it on first call."""
        if self._repo_intel is None:
            db_path = get_data_dir() / "repo_intel.db"
            self._repo_intel = RepoIntelligence(
                root=self.config.cwd,
                db_path=db_path,
            )
        return self._repo_intel

    async def initialize(self) -> None:
        await self.mcp_manager.initialize()
        self.mcp_manager.register_tools(self.tool_registry)
        self.discovery_manager.discover_all()
        self.context_manager = ContextManager(
            config=self.config,
            user_memory=self._load_memory(),
            tools=self.tool_registry.get_tools(),
        )

    async def shutdown(self) -> None:
        """Satisfy AgentRuntime protocol: tear down MCP + HTTP client."""
        await self.client.close()
        await self.mcp_manager.shutdown()

    def _load_memory(self) -> str | None:
        data_dir = get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        path = data_dir / "user_memory.json"

        if not path.exists():
            return None

        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
            entries = data.get("entries")
            if not entries:
                return None

            lines = ["User preferences and notes:"]
            for key, value in entries.items():
                lines.append(f"- {key}: {value}")

            return "\n".join(lines)
        except Exception:
            return None

    def increment_turn(self) -> int:
        self.turn_count += 1
        self.updated_at = datetime.now()
        return self.turn_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "turn_count": self.turn_count,
            "message_count": self.context_manager.message_count,
            "token_usage": self.context_manager.total_usage,
            "tools_count": len(self.tool_registry.get_tools()),
            "mcp_servers": len(self.tool_registry.connected_mcp_servers),
        }
