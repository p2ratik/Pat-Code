import json
import uuid
from config.config import Config
from config.loader import get_data_dir
from tools.base import Tool, ToolInvocation, Toolkind, ToolResult
from pydantic import BaseModel, Field

class MemoryParams(BaseModel):
    action: str = Field(
        ..., description="Action: 'set', 'query', 'delete', 'list'"
    )
    query: str | None = Field(
        None, description="Query to get relevant search result using the semantic search technique `query (action). Do not use this while setting value . Its just for searching ."
    )
    value: str | None = Field(None, description="Value to store (required for `set`). Set the value in such way that it can be searched when required through similarity search technique")

    importance : int | None = Field(None, description="How important the memory is on a scale of 0-1 .")


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


        elif params.action.lower() == "query":
            if not params.query:
                return ToolResult.error_result("`query` required for 'query' action")

            try:
                results = invocation.session.memory_manager.search(query = params.query)
            except Exception as e:
                return ToolResult.error_result(f"Failed to Fetch relevant data  ! DB error {e}")       
            
            if not results:
                return ToolResult.success_result(
                    f"Memory not found for query {params.query}",
                    metadata={
                        "found": False,
                    },
                )
            context =  "\n".join([content['content'] for content in results])
            session_ids = set([md['metadata']['session_id'] for md in results])

            return ToolResult.success_result(
                f"Memory found for query: {params.query}: {context}",
                metadata={
                    "found": True,
                    "session_ids" :  session_ids,
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
            try:
                memory = invocation.session.memory_manager.list_data()
            except Exception as e:
                return ToolResult.error_result(f"Failed to Fetch relevant data  ! DB error {e}")    
                               
            if not memory:
                return ToolResult.success_result(
                    f"No memories stored",
                    metadata={
                        "found": False,
                    },
                )

            content = '\n'.join([content[0] for content in memory])

            return ToolResult.success_result(
                content,
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