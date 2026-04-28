import json
import uuid
from config.config import Config
from config.loader import get_data_dir
from tools.base import Tool, ToolInvocation, Toolkind, ToolResult
from pydantic import BaseModel, Field

class MemoryParams(BaseModel):
    action: str = Field(
        ..., description="Action: 'set', query, 'delete', 'list', 'clear'"
    )
    query: str | None = Field(
        None, description="Query to get relevant search result using the semantic search technique `query (action). Do not use this while setting value . Its just for searching ."
    )
    value: str | None = Field(None, description="Value to store (required for `set`). Set the value in such way that it can be searched when required through similarity search technique")

    importance : int = Field(..., description="How important the memory is on a scale of 0-1 .")


class MemoryTool(Tool):
    name = "memory"
    description = "Store and retrieve persistent memory. Use this to remember user preferences, important context or notes. The context are stored as vectors and search result are based on similary search"
    kind = Toolkind.MEMORY
    schema = MemoryParams



    def _load_memory(self) -> dict:
        data_dir = get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        path = data_dir / "user_memory.json"

        if not path.exists():
            return {"entries": {}}

        try:
            content = path.read_text(encoding="utf-8")
            return json.loads(content)
        except Exception:
            return {"entries": {}}

    def _save_memory(self, memory: dict) -> None:
        data_dir = get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        path = data_dir / "user_memory.json"

        path.write_text(json.dumps(memory, indent=2, ensure_ascii=False))

    def _build_metadatas(self, importance : int, session_id : str)->dict:

        return {
            "importance" : importance,
            "session_id" : session_id,
        }
        

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = MemoryParams(**invocation.params)

        if params.action.lower() == "set":
            if not params.importance or not params.value:
                return ToolResult.error_result(
                    "`importance` and `value` are required for 'set' action"
                )

            metadata = self._build_metadatas(params.importance, invocation.session.session_id)
            try:
                invocation.session.memory_manager.add_memory(content = params.value, metadata =metadata, memory = 'episodic' )
                return ToolResult.success_result(f"Set memory:")
            except Exception as e:
                return ToolResult.error_result(f"Error occured ! DB error {e}")


        elif params.action.lower() == "get":
            if not params.key:
                return ToolResult.error_result("`key` required for 'get' action")

            memory = self._load_memory()
            if params.key not in memory.get("entries", {}):
                return ToolResult.success_result(
                    f"Memory not found: {params.key}",
                    metadata={
                        "found": False,
                    },
                )
            return ToolResult.success_result(
                f"Memory found: {params.key}: {memory['entries'][params.key]}",
                metadata={
                    "found": True,
                },
            )
        elif params.action == "delete":
            if not params.key:
                return ToolResult.error_result("`key` required for 'get' action")
            memory = self._load_memory()
            if params.key not in memory.get("entries", {}):
                return ToolResult.success_result(f"Memory not found: {params.key}")

            del memory["entries"][params.key]
            self._save_memory(memory)

            return ToolResult.success_result(f"Deleted memory: {params.key}")
        elif params.action == "list":
            memory = self._load_memory()
            entries = memory.get("entries", {})
            if not entries:
                return ToolResult.success_result(
                    f"No memories stored",
                    metadata={
                        "found": False,
                    },
                )
            lines = [f"Stored memories:"]
            for key, value in sorted(entries.items()):
                lines.append(f"  {key}: {value}")

            return ToolResult.success_result(
                "\n".join(lines),
                metadata={
                    "found": True,
                },
            )
        elif params.action == "clear":
            memory = self._load_memory()
            count = len(memory.get("entries", {}))
            memory["entries"] = {}
            self._save_memory(memory)
            return ToolResult.success_result(f"Cleared {count} memory entries")
        else:
            return ToolResult.error_result(f"Unknown action: {params.action}") 