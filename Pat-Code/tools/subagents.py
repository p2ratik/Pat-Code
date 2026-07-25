import asyncio
from typing import TYPE_CHECKING, Any
from tools.base import Tool, ToolInvocation, ToolResult, Toolkind
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Callable

if TYPE_CHECKING:
    from config.config import Config


class SubagentParams(BaseModel):
    goal: str = Field(
        ..., description="The specific task or goal for the subagent to accomplish"
    )


@dataclass
class SubagentDefinition:
    name: str
    description: str
    goal_prompt: str
    allowed_tools: list[str] | None = None
    max_turns: int = 20
    timeout_seconds: float = 600


SHARED_SUBAGENT_PROMPT = """Shared operating rules:
- You cannot ask the user follow-up questions. Resolve ambiguity by investigating with the tools you have.
- Budget your turns: about 20% orienting, 60% following leads with graph traversal / grep / read_file, and 20% consolidating your report.
- If you are running low on turns before reaching a confident answer, stop exploring and report what remains unresolved under Open Questions.
- Use graph tools instead of grep when possible for named code entities, caller/callee tracing, imports, inheritance, containment, and impact analysis.
- Use grep/list_dir/glob/read_file for literal strings, non-code files, docs, configs, logs, generated files, and repository inventory.

Structure your final report exactly as:
## Findings
[what you found, in plain language]
## Evidence
[file_path:line_number for every claim; no claim without a location]
## Confidence
[high/medium/low, and why]
## Open Questions
[anything you could not resolve in your turn budget]"""


class SubagentTool(Tool):
    kind = Toolkind.MCP
    requires_semantic_verification = True

    def __init__(self, config: "Config", definition: SubagentDefinition):
        super().__init__(config)
        self.definition = definition

    @property
    def name(self) -> str:
        return f"subagent_{self.definition.name}"

    @property
    def description(self) -> str:
        return f"subagent_{self.definition.description}"

    schema = SubagentParams

    def is_mutating(self, params: dict[str, Any]) -> bool:
        return True

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        from agent.agent import Agent
        from agent.events import AgentEventType
        from config.config import Config
        

        params = SubagentParams(**invocation.params)
        if not params.goal:
            return ToolResult.error_result("No goal specified for sub-agent")

        config_dict = self.config.to_dict()
        # Reserve one extra turn so the sub-agent can synthesize findings after tool calls.
        config_dict["max_turns"] = max(self.definition.max_turns, 1) + 1
        if self.definition.allowed_tools:
            config_dict["allowed_tools"] = self.definition.allowed_tools

        subagent_config = Config(**config_dict)

        prompt = f"""You are a specialized sub-agent with a specific task to complete.

        {SHARED_SUBAGENT_PROMPT}

        {self.definition.goal_prompt}

        YOUR TASK:
        {params.goal}

        IMPORTANT:
        - Focus only on completing the specified task
        - Do not engage in unrelated actions
        - Once you have completed the task or have the answer, provide your final response
        - Be concise and direct in your output
        - Use the required report template in your final response
        """

        tool_calls = []
        final_response = None
        post_tool_response = None
        error = None
        terminate_response = "goal"
        completed_tool_calls = 0

        try:
            async with Agent(subagent_config) as agent:
                deadline = (
                    asyncio.get_running_loop().time() + self.definition.timeout_seconds
                )

                async for event in agent.run(prompt):
                    if asyncio.get_running_loop().time() > deadline:
                        terminate_response = "timeout"
                        final_response = "Sub-agent timed out"
                        break

                    if event.type == AgentEventType.TOOL_CALL_START:
                        tool_calls.append(event.data.get("name"))
                    elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                        completed_tool_calls += 1
                    elif event.type == AgentEventType.TEXT_COMPLETE:
                        content = event.data.get("content")
                        if content:
                            final_response = content
                            if completed_tool_calls > 0:
                                post_tool_response = content
                    elif event.type == AgentEventType.AGENT_END:
                        if final_response is None:
                            final_response = event.data.get("response")
                    elif event.type == AgentEventType.AGENT_ERROR:
                        terminate_response = "error"
                        error = event.data.get("error", "Unknown")
                        final_response = f"Sub-agent error: {error}"
                        break
        except Exception as e:
            terminate_response = "error"
            error = str(e)
            final_response = f"Sub-agent failed: {e}"

        final_report = post_tool_response or final_response or "No response"

        result = f"""Sub-agent '{self.definition.name}' completed. 
        Termination: {terminate_response}
        Tools called: {', '.join(tool_calls) if tool_calls else 'None'}

        Result:
        {final_report}
        """

        if error:
            return ToolResult.error_result(result)

        return ToolResult.success_result(result)


CODEBASE_INVESTIGATOR = SubagentDefinition(
    name="codebase_investigator",
    description="Investigates the codebase to answer questions about code structure, patterns, and implementations",
    goal_prompt="""You are a codebase investigation specialist.
Your job is to explore and understand code to answer questions.
Use search_entity, retrieve_entity, traverse_graph, read_file, grep, glob, and list_dir to investigate.
Prefer graph tools when the task names a symbol, class, method, or dependency path:
- search_entity -> find exact entity IDs
- retrieve_entity -> read one class/function/method without loading the full file
- traverse_graph -> inspect callers, callees, imports, inheritance, and containment
Do not use graph tools for broad text search, non-code files, generated files, or when a simple grep/list_dir answers the question faster.
<example>
Task: "Explain how ToolResult is used."
[search_entity("ToolResult") -> retrieve_entity on the exact class -> traverse_graph direction='in' for dependents]
Report: "## Findings: ToolResult is created in... ## Evidence: tools/base.py:42, agent/agent.py:318 ## Confidence: high - exact entity and inbound graph were checked"
</example>
Do NOT modify any files. After performing the tool calls do report what you find """,
    allowed_tools=["search_entity", "retrieve_entity", "traverse_graph", "read_file", "grep", "glob", "list_dir"],
    max_turns=30
)

CODE_REVIEWER = SubagentDefinition(
    name="code_reviewer",
    description="Reviews code changes and provides feedback on quality, bugs, and improvements",
    goal_prompt="""You are a code review specialist.
Your job is to review code and provide constructive feedback.
Look for bugs, code smells, security issues, and improvement opportunities.
Use search_entity, retrieve_entity, traverse_graph, read_file, list_dir and grep to examine the code.
Prefer graph tools for symbol-level review, impact analysis, caller/callee checks, inheritance, and import relationships.
Do not use graph tools for broad prose search, documentation-only review, or when the exact changed file context is already sufficient.
<example>
Task: "Review changes to AuthMiddleware."
[search_entity("AuthMiddleware") -> retrieve_entity on the class -> traverse_graph direction='in' for callers/importers]
Report: "## Findings: One bypass risk... ## Evidence: auth/middleware.py:88, api/routes.py:41 ## Confidence: medium - callers checked, tests not found"
</example>
You have only 35 turns to perform your tool calls .
Do NOT modify any files.After performing the tool calls do report what you find """,
    allowed_tools=["search_entity", "retrieve_entity", "traverse_graph", "read_file", "grep", "list_dir"],
    max_turns=36,
    timeout_seconds=300,
)

DEPENDENCY_TRACER = SubagentDefinition(
    name="dependency_tracer",
    description="Traces dependencies, call chains, and module relationships to map impacts",
    goal_prompt="""You are a dependency tracing specialist.
Your job is to map dependencies and call chains related to the requested area.
Use search_entity, retrieve_entity, traverse_graph, read_file, grep, glob, and list_dir to investigate.
Use graph tools first when tracing a named entity:
- search_entity to discover the exact entity ID
- traverse_graph direction='out' for dependencies/callees/imports
- traverse_graph direction='in' for dependents/callers/importers
- retrieve_entity to inspect important definitions found in the graph
Do not use graph tools for plain filename discovery, config lookup, or text that is not indexed as code entities.
<example>
Task: "Trace what depends on PaymentGateway.charge()."
[search_entity("PaymentGateway.charge") -> traverse_graph direction='in' edge_types=['invoke'] -> retrieve_entity on important callers]
Report: "## Findings: 3 call sites... ## Evidence: checkout.py:112, refund.py:45, webhook_handler.py:88 ## Confidence: high - call graph and caller bodies were checked"
</example>
Do NOT modify any files. After performing the tool calls do report what you find """,
    allowed_tools=["search_entity", "retrieve_entity", "traverse_graph", "read_file", "grep", "glob", "list_dir"],
    max_turns=30,
    timeout_seconds=300,
)

ROOT_CAUSE_INVESTIGATOR = SubagentDefinition(
    name="root_cause_investigator",
    description="Investigates symptoms to identify likely root causes and evidence",
    goal_prompt="""You are a root cause investigation specialist.
Your job is to trace symptoms to their most likely causes with evidence.
Use search_entity, retrieve_entity, traverse_graph, read_file, grep, glob, and list_dir to investigate.
Use graph tools when a symptom points at a class/function/method or when you need to validate caller/callee and import paths.
Do not use graph tools when the symptom is in logs, docs, config, tests not represented in the graph, or when keyword search is the better first step.
<example>
Task: "Find why checkout double-charges."
[grep("charge") for symptom terms -> search_entity("charge") for exact code entities -> traverse_graph direction='in' to find repeated callers]
Report: "## Findings: Retry path can call charge twice... ## Evidence: checkout.py:140, retry.py:57 ## Confidence: medium - static path found, runtime logs not available"
</example>
Do NOT modify any files. After performing the tool calls do report what you find """,
    allowed_tools=["search_entity", "retrieve_entity", "traverse_graph", "read_file", "grep", "glob", "list_dir"],
    max_turns=30,
    timeout_seconds=300,
)

REGRESSION_HUNTER = SubagentDefinition(
    name="regression_hunter",
    description="Looks for behavioral regressions by comparing patterns, tests, and recent changes",
    goal_prompt="""You are a regression investigation specialist.
Your job is to identify likely regressions and where they were introduced.
Use search_entity, retrieve_entity, traverse_graph, read_file, grep, glob, and list_dir to investigate.
Use graph tools to compare current symbol behavior with its callers, dependencies, and related implementations.
Do not use graph tools as a substitute for reading changed files, tests, changelogs, or config when those are the primary evidence.
<example>
Task: "Find whether the retry change regressed timeout handling."
[grep("timeout") in tests/changed files -> search_entity("retry") -> traverse_graph direction='out' for timeout-related callees]
Report: "## Findings: Timeout handling no longer reaches cancel_task... ## Evidence: retry.py:73, worker.py:204 ## Confidence: medium - no regression test covers this path"
</example>
Do NOT modify any files. After performing the tool calls do report what you find """,
    allowed_tools=["search_entity", "retrieve_entity", "traverse_graph", "read_file", "grep", "glob", "list_dir"],
    max_turns=30,
    timeout_seconds=300,
)

ARCHITECTURE_MAPPER = SubagentDefinition(
    name="architecture_mapper",
    description="Reconstructs system architecture, subsystem boundaries, and ownership flow",
    goal_prompt="""You are an architecture mapping specialist.
Your job is to infer system structure, subsystem boundaries, and ownership flow.
Use search_entity, retrieve_entity, traverse_graph, read_file, grep, glob, and list_dir to investigate.
Use graph tools for entity-level architecture: containment, imports, inheritance, call flow, and dependency direction.
Do not use graph tools for repository inventory, documentation search, package metadata, or non-code architecture notes unless tied to indexed entities.
<example>
Task: "Map the agent/tool execution architecture."
[glob/list_dir for top-level modules -> search_entity("Agent") and "Tool" -> traverse_graph direction='both' for boundaries]
Report: "## Findings: Agent orchestrates tool execution through... ## Evidence: agent/agent.py:76, tools/base.py:18 ## Confidence: high - graph and module layout agree"
</example>
Do NOT modify any files. After performing the tool calls do report what you find """,
    allowed_tools=["search_entity", "retrieve_entity", "traverse_graph", "read_file", "grep", "glob", "list_dir"],
    max_turns=30,
    timeout_seconds=300,
)


def get_default_subagent_definitions() -> list[SubagentDefinition]:
    return [
        CODEBASE_INVESTIGATOR,
        CODE_REVIEWER,
        DEPENDENCY_TRACER,
        ROOT_CAUSE_INVESTIGATOR,
        REGRESSION_HUNTER,
        ARCHITECTURE_MAPPER,
    ]


class ParallelGoal(BaseModel):
    agent: str = Field(..., description="Name of the subagent (e.g. 'codebase_investigator')")
    goal: str = Field(..., description="The specific task for this subagent")


class ParallelSubagentsParams(BaseModel):
    goals: list[ParallelGoal] = Field(
        ...,
        description="List of (agent, goal) pairs to run concurrently. All must be read-only subagents.",
    )


class ParallelSubagentsTool(Tool):
    """Scatter-gather tool: fans out multiple subagent goals in parallel, collects results."""

    name = "parallel_subagents"
    description = (
        "Run multiple read-only subagents concurrently and return all results. "
        "Use when you need independent investigations that don't depend on each other. "
        "Each entry specifies which subagent to use and what goal to give it."
    )
    kind = Toolkind.MCP
    schema = ParallelSubagentsParams
    requires_semantic_verification = False

    def __init__(self, config: "Config", subagent_factory: "Callable[[str], SubagentTool | None]"):
        super().__init__(config)
        self._factory = subagent_factory

    def is_mutating(self, params: dict[str, Any]) -> bool:
        return False

    async def _run_one(self, agent_name: str, goal: str) -> tuple[str, str]:
        tool = self._factory(agent_name)
        if tool is None:
            return agent_name, f"Error: unknown subagent '{agent_name}'"
        invocation = ToolInvocation(params={"goal": goal}, cwd=self.config.cwd, session=None)
        result = await tool.execute(invocation)
        return agent_name, result.to_model_output()

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ParallelSubagentsParams(**invocation.params)
        if not params.goals:
            return ToolResult.error_result("No goals provided to parallel_subagents")

        tasks = [self._run_one(g.agent, g.goal) for g in params.goals]
        outcomes: list[tuple[str, str]] = await asyncio.gather(*tasks, return_exceptions=False)

        sections = [
            f"### {name}\n{output}" for name, output in outcomes
        ]
        return ToolResult.success_result("\n\n".join(sections))


def make_parallel_subagents_tool(
    config: "Config",
    definitions: list[SubagentDefinition],
) -> ParallelSubagentsTool:
    registry: dict[str, SubagentTool] = {
        d.name: SubagentTool(config, d) for d in definitions
    }
    return ParallelSubagentsTool(config, registry.get)
