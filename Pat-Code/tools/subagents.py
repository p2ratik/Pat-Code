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

        {self.definition.goal_prompt}

        YOUR TASK:
        {params.goal}

        IMPORTANT:
        - Focus only on completing the specified task
        - Do not engage in unrelated actions
        - Once you have completed the task or have the answer, provide your final response
        - Be concise and direct in your output
        - After performing tool calls and everything do mention what you found 
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
Use read_file, grep, glob, and list_dir to investigate.
Do NOT modify any files. After performing the tool calls do report what you find """,
    allowed_tools=["read_file", "grep", "glob", "list_dir"],
    max_turns=30
)

CODE_REVIEWER = SubagentDefinition(
    name="code_reviewer",
    description="Reviews code changes and provides feedback on quality, bugs, and improvements",
    goal_prompt="""You are a code review specialist.
Your job is to review code and provide constructive feedback.
Look for bugs, code smells, security issues, and improvement opportunities.
Use read_file, list_dir and grep to examine the code.
You have only 35 turns to perform your tool calls .
Do NOT modify any files.After performing the tool calls do report what you find """,
    allowed_tools=["read_file", "grep", "list_dir"],
    max_turns=36,
    timeout_seconds=300,
)

DEPENDENCY_TRACER = SubagentDefinition(
    name="dependency_tracer",
    description="Traces dependencies, call chains, and module relationships to map impacts",
    goal_prompt="""You are a dependency tracing specialist.
Your job is to map dependencies and call chains related to the requested area.
Use read_file, grep, glob, and list_dir to investigate.
Do NOT modify any files. After performing the tool calls do report what you find """,
    allowed_tools=["read_file", "grep", "glob", "list_dir"],
    max_turns=30,
    timeout_seconds=300,
)

ROOT_CAUSE_INVESTIGATOR = SubagentDefinition(
    name="root_cause_investigator",
    description="Investigates symptoms to identify likely root causes and evidence",
    goal_prompt="""You are a root cause investigation specialist.
Your job is to trace symptoms to their most likely causes with evidence.
Use read_file, grep, glob, and list_dir to investigate.
Do NOT modify any files. After performing the tool calls do report what you find """,
    allowed_tools=["read_file", "grep", "glob", "list_dir"],
    max_turns=30,
    timeout_seconds=300,
)

REGRESSION_HUNTER = SubagentDefinition(
    name="regression_hunter",
    description="Looks for behavioral regressions by comparing patterns, tests, and recent changes",
    goal_prompt="""You are a regression investigation specialist.
Your job is to identify likely regressions and where they were introduced.
Use read_file, grep, glob, and list_dir to investigate.
Do NOT modify any files. After performing the tool calls do report what you find """,
    allowed_tools=["read_file", "grep", "glob", "list_dir"],
    max_turns=30,
    timeout_seconds=300,
)

ARCHITECTURE_MAPPER = SubagentDefinition(
    name="architecture_mapper",
    description="Reconstructs system architecture, subsystem boundaries, and ownership flow",
    goal_prompt="""You are an architecture mapping specialist.
Your job is to infer system structure, subsystem boundaries, and ownership flow.
Use read_file, grep, glob, and list_dir to investigate.
Do NOT modify any files. After performing the tool calls do report what you find """,
    allowed_tools=["read_file", "grep", "glob", "list_dir"],
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