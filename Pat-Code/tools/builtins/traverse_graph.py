from typing import Literal

from pydantic import BaseModel, Field

from repo_intel.renderer import render_traversal
from repo_intel.typed_graph import EDGE_CONTAIN, EDGE_INVOKE, EDGE_IMPORT, EDGE_INHERIT
from tools.base import Tool, ToolInvocation, Toolkind, ToolResult
from tools.builtins.search_entity import _get_repo_intel


_VALID_EDGE_TYPES = f"'{EDGE_CONTAIN}', '{EDGE_INVOKE}', '{EDGE_IMPORT}', '{EDGE_INHERIT}'"
_VALID_NODE_TYPES = "'class', 'function', 'method', 'constant', 'module'"


class TraverseGraphParams(BaseModel):
    start_ids: list[str] = Field(
        ...,
        description=(
            "One or more entity IDs to start the traversal from. Entity IDs follow the "
            "format 'rel/path/to/file.py:QualifiedName', for example: "
            "'agent/agent.py:Agent._agentic_loop' or 'tools/base.py:ToolResult'. "
            "Use search_entity first to discover valid IDs."
        ),
        min_length=1,
    )
    direction: Literal["out", "in", "both"] = Field(
        "out",
        description=(
            "'out' follows edges away from the start nodes (e.g. what does this call / "
            "contain / import). 'in' follows edges toward the start nodes (e.g. what "
            "calls or imports this). 'both' explores in both directions simultaneously."
        ),
    )
    hops: int = Field(
        2,
        ge=1,
        le=5,
        description=(
            "Maximum number of graph hops from the start nodes (default: 2, max: 5). "
            "Larger values return wider context but may include loosely related nodes."
        ),
    )
    edge_types: list[str] | None = Field(
        None,
        description=(
            f"Restrict traversal to specific relationship types. Valid values: {_VALID_EDGE_TYPES}. "
            f"'contain' = parent/child scope nesting. 'invoke' = function call references. "
            f"'import' = module-level import statements. 'inherit' = class inheritance. "
            f"Omit to traverse all edge types."
        ),
    )
    node_types: list[str] | None = Field(
        None,
        description=(
            f"Only include nodes of these kinds in the result. Valid values: {_VALID_NODE_TYPES}. "
            f"Omit to include all node types."
        ),
    )


class TraverseGraphTool(Tool):
    name = "traverse_graph"
    description = (
        "Explore the repository's typed code graph starting from one or more entity IDs. "
        "The graph has four relationship types: 'contain' (scope nesting, e.g. a class "
        "contains its methods), 'invoke' (call references within a function body), "
        "'import' (module-level imports), and 'inherit' (class inheritance). "
        "Use direction='out' to find what an entity depends on, direction='in' to find "
        "what depends on it, and direction='both' for full neighbourhood context. "
        "Always call search_entity first to get valid entity IDs."
    )
    kind = Toolkind.READ
    schema = TraverseGraphParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = TraverseGraphParams(**invocation.params)
        ri = _get_repo_intel(invocation)

        try:
            result = ri.traverse_graph(
                start_ids=params.start_ids,
                direction=params.direction,
                hops=params.hops,
                edge_types=params.edge_types,
                node_types=params.node_types,
            )
        except Exception as exc:
            return ToolResult.error_result(f"traverse_graph failed: {exc}")

        if not result.distances:
            return ToolResult.success_result(
                f"No nodes found reachable from {params.start_ids} with the given filters.",
                metadata={"start_ids": params.start_ids, "nodes_found": 0},
            )

        output = render_traversal(result, params.start_ids)

        return ToolResult.success_result(
            output,
            metadata={
                "start_ids": params.start_ids,
                "direction": params.direction,
                "hops": params.hops,
                "nodes_found": len(result.distances),
                "edges_found": result.subgraph.number_of_edges(),
            },
        )
