from pydantic import BaseModel, Field

from tools.base import Tool, ToolInvocation, Toolkind, ToolResult
from tools.builtins.search_entity import _get_repo_intel


class RetrieveEntityParams(BaseModel):
    entity_id: str = Field(
        ...,
        description=(
            "The fully-qualified entity ID to retrieve source code for. Must follow the "
            "format 'rel/path/to/file.py:QualifiedName', for example: "
            "'agent/agent.py:Agent._agentic_loop' or 'tools/base.py:ToolResult.error_result'. "
            "Use search_entity first to discover valid IDs — passing an unrecognised ID "
            "returns an empty result rather than an error."
        ),
    )


class RetrieveEntityTool(Tool):
    name = "retrieve_entity"
    description = (
        "Retrieve the full source code of a single named entity (class, function, method, "
        "or constant) by its exact entity ID. Returns only the lines belonging to that "
        "entity — not the entire file — making it much more token-efficient than read_file "
        "when you only need one definition. Use search_entity first to get the exact entity "
        "ID, then call this tool to read its implementation."
    )
    kind = Toolkind.READ
    schema = RetrieveEntityParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = RetrieveEntityParams(**invocation.params)
        ri = _get_repo_intel(invocation)

        try:
            source = ri.retrieve_entity(params.entity_id)
        except Exception as exc:
            return ToolResult.error_result(f"retrieve_entity failed: {exc}")

        if not source:
            return ToolResult.success_result(
                f"Entity '{params.entity_id}' not found in the index. "
                "Run search_entity to discover valid entity IDs.",
                metadata={"entity_id": params.entity_id, "found": False},
            )

        # Annotate with line numbers (entity_id encodes rel_fname; look up start_line)
        rec = ri.get_entity_record(params.entity_id)
        start_line = (rec.start_line + 1) if rec else 1  # convert to 1-based

        numbered = "\n".join(
            f"{start_line + i:5}| {line}"
            for i, line in enumerate(source.splitlines())
        )
        header = f"# {params.entity_id}  [{rec.kind if rec else '?'}]\n\n"

        return ToolResult.success_result(
            header + numbered,
            metadata={
                "entity_id": params.entity_id,
                "found": True,
                "start_line": start_line,
                "lines": len(source.splitlines()),
            },
        )
