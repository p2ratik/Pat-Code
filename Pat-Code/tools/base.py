import abc
import uuid
from pydantic import BaseModel, ValidationError
from enum import Enum
from typing import Any
from dataclasses import dataclass, field
from pathlib import Path
from pydantic.json_schema import model_json_schema
from config.config import Config
from agent.hooks.processors.base import ProcessedOutput

class Toolkind(str, Enum):
    READ = "read"
    WRITE = "write"
    SHELL = "shell"
    NETWORK = "network"
    MEMORY = "memory"
    MCP = "mcp"
    INTEGRATION = "integration"

@dataclass
class FileDiff:
    path : Path
    old_content : str
    new_content : str

    is_new_file : bool = False
    is_deletion : bool = False

    def to_diff(self)->str:
        import difflib

        old_lines = self.old_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)

        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"

        old_name = "/dev/null" if self.is_new_file else str(self.path)
        new_name = "/dev/null" if self.is_deletion else str(self.path)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=old_name,
            tofile=new_name,
        )

        return "".join(diff)       

# By LLM
@dataclass
class ToolInvocation:
    params : dict[str, Any]
    cwd : Path
    session : Any

# By LLM
@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    diff : FileDiff | None = None
    truncated : bool = False
    exit_code : int | None = None

    @classmethod
    def error_result(cls, error : str, output :str = "", **kwargs : Any):
        return cls(
            success = False,
            output = output,
            error = error,
            **kwargs
        )
    
    @classmethod
    def success_result(cls, output :str = "", **kwargs : Any):
        return cls(
            success = True,
            output = output,
            error = None,
            **kwargs
        )
    # Just beautifying the error message if exist any!
    def to_model_output(self):
        if self.success:
            return self.output
        
        return f"Error : {self.error}\n\nOutput:\n{self.output}"


@dataclass
class ExecutionResult:

    tool_result: ToolResult

    tool_name: str = ""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    duration_ms: float = 0.0
    attempts: int = 1

    verified: bool | None = None
    classification: str | None = None
    recovered: bool = False
    repair_instruction: str | None = None
    processed_output: ProcessedOutput | None = None

    @property
    def success(self) -> bool:
        return self.tool_result.success

    @property
    def output(self) -> str:
        return self.tool_result.output

    @property
    def error(self) -> str | None:
        return self.tool_result.error

    @property
    def metadata(self) -> dict[str, Any]:
        return self.tool_result.metadata

    @property
    def diff(self) -> "FileDiff | None":
        return self.tool_result.diff

    @property
    def truncated(self) -> bool:
        return self.tool_result.truncated

    @property
    def exit_code(self) -> int | None:
        return self.tool_result.exit_code

    def to_model_output(self) -> str:
        if self.repair_instruction:
            return self.repair_instruction
        if self.processed_output:
            return self.processed_output.content
        return self.tool_result.to_model_output()


@dataclass
class ToolConfirmation:
    tool_name : str
    params : dict[str, Any]
    description : str

    diff: FileDiff | None = None
    affected_paths: list[Path] = field(default_factory=list)
    command: str | None = None
    is_dangerous: bool = False

# abc 
class Tool(abc.ABC):
    name : str = "base_tool"
    description : str = "Base_Tool"
    kind : Toolkind.READ
    requires_semantic_verification: bool = False

    def __init__(self, config: Config):
        super().__init__()
        self.config = config

    @property
    def schema(self)-> dict[str, Any] | type['BaseModel']: # Pydantic for our custom schema and dict for mcp based 
        raise NotImplementedError("Tool must define schema params")
    
    @abc.abstractmethod
    async def execute(self, invocation : ToolInvocation)->ToolResult:
        pass

    def validate_params(self, params):
        schema = self.schema

        if isinstance(schema, type) and issubclass(schema,BaseModel):
            try:
                schema(**params)
            except ValidationError as e:
                errors = []
                for error in e.errors():
                    filed = ".".join(str(x) for x in error.get("loc", []))
                    errors.append(filed)

                return errors

            except Exception as e:
                return [str(e)]    

    def is_mutating(self, params)->bool:

        return self.kind in (
            Toolkind.WRITE,
            Toolkind.SHELL,
            Toolkind.MEMORY,
        )

    async def get_confirmation(self, invocation : ToolInvocation):
        if not self.is_mutating(invocation.params):
            return None
        
        return ToolConfirmation(
            tool_name = self.name,
            params = invocation.params,
            description = f"Exccute {self.name}"
        )

    def to_openai_schema(self) -> dict[str, Any]:
        schema = self.schema

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            json_schema = model_json_schema(schema, mode="serialization")
            defs = json_schema.get("$defs", {})
            properties = _deref_schema(json_schema.get("properties", {}), defs)
            return {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": json_schema.get("required", []),
                },
            }

        if isinstance(schema, dict):
            result = {
                "name": self.name,
                "description": self.description,
            }
            if "parameters" in schema:
                result["parameters"] = schema["parameters"]
            else:
                result["parameters"] = schema
            return result

        raise ValueError(f"Invalid schema type for tool {self.name}: {type(schema)}")


def _deref_schema(node: Any, defs: dict[str, Any], _seen: frozenset[str] = frozenset()) -> Any:
    """Recursively inline all $ref/$defs so the schema is self-contained.

    Providers like OpenRouter do not resolve $ref themselves, so we must
    expand them before sending the schema over the wire.
    """
    if isinstance(node, dict):
        if "$ref" in node:
            ref: str = node["$ref"]
            name = ref.split("/")[-1]
            if name in _seen:
                return {"type": "object"}
            resolved = defs.get(name, {})
            return _deref_schema(resolved, defs, _seen | {name})
        return {k: _deref_schema(v, defs, _seen) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [_deref_schema(item, defs, _seen) for item in node]
    return node