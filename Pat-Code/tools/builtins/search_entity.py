from pydantic import BaseModel, Field

from repo_intel.intelligence import RepoIntelligence
from tools.base import Tool, ToolInvocation, Toolkind, ToolResult


class SearchEntityParams(BaseModel):
    keyword: str = Field(
        ...,
        description=(
            "The name or identifier to search for. Can be a full entity ID like "
            "'agent/agent.py:Agent._agentic_loop', a partial name like 'agentic_loop', "
            "a class name like 'Agent', or any keyword. Exact substring matches on entity "
            "IDs are tried first; BM25 full-text search is used as a fallback."
        ),
    )
    top_k: int = Field(
        50,
        ge=1,
        le=200,
        description=(
            "Maximum number of results to return (default: 50). Results are returned in "
            "one of three tiers based on match count: 'full' (<5 hits, includes complete "
            "source), 'preview' (5-20 hits, includes first signature line), or 'fold' "
            "(>20 hits, entity IDs only to avoid flooding context)."
        ),
    )


class SearchEntityTool(Tool):
    name = "search_entity"
    description = (
        "Search the repository's code intelligence index for a class, function, method, "
        "or constant by name or keyword. Returns a ranked list of matching entities with "
        "their file location, kind (class/function/method/constant), and source code "
        "(amount depends on result count — fewer matches reveal more source). "
        "Use this before traverse_graph to discover the exact entity IDs you need. "
        "Prefer specific names ('AuthMiddleware') over generic keywords ('middleware')."
    )
    kind = Toolkind.READ
    schema = SearchEntityParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = SearchEntityParams(**invocation.params)
        ri = _get_repo_intel(invocation)

        try:
            result = ri.search_entity(params.keyword, params.top_k)
        except Exception as exc:
            return ToolResult.error_result(f"search_entity failed: {exc}")

        if result.total_hits == 0:
            return ToolResult.success_result(
                f"No entities found matching '{params.keyword}'.",
                metadata={"keyword": params.keyword, "hits": 0},
            )

        lines = [
            f"Found {result.total_hits} match(es) for '{params.keyword}' "
            f"[tier: {result.tier}]\n"
        ]
        for match in result.matches:
            lines.append(f"• {match.entity_id}  [{match.kind}]  — {match.rel_fname}")
            if match.preview:
                lines.append(f"  {match.preview}")
            if match.source:
                lines.append("")
                for src_line in match.source.splitlines():
                    lines.append(f"  {src_line}")
                lines.append("")

        return ToolResult.success_result(
            "\n".join(lines),
            metadata={
                "keyword": params.keyword,
                "hits": result.total_hits,
                "tier": result.tier,
            },
        )


def _get_repo_intel(invocation: ToolInvocation) -> RepoIntelligence:
    """Return the session-scoped RepoIntelligence instance."""
    return invocation.session.get_repo_intel()
