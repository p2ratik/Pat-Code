import abc
from pydantic import BaseModel, ValidationError
from enum import Enum
from typing import Any
from dataclasses import dataclass, field
from pathlib import Path

class Toolkind(str, Enum):
    READ = "read"
    WRITE = "write"
    SHELL = "shell"
    NETWORK = "network"
    MEMORY = "memory"
    MCP = "mcp"

# By LLM
@dataclass
class ToolInvocation:
    params : dict[str, Any]
    cwd : Path

# By LLM
@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def error_result(cls, success:bool, error : str, output :str = "", **kwargs : Any):
        return cls(
            success = False,
            output = output,
            error = error,
            **kwargs
        )
    
    @classmethod
    def success_result(cls, success:bool, error : str, output :str = "", **kwargs : Any):
        return cls(
            success = True,
            error = None,
            output = output,
            **kwargs
        )

@dataclass
class ToolConfirmation:
    tool_name : str
    params : dict[str, Any]
    description : str

# abc 
class Tool(abc.ABC):
    name : str = "base_tool"
    description : str = "Base_Tool"
    kind : Toolkind.READ

    def __init__(self):
        super().__init__()

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

    # The tool to be performing at its best it's description must be in a format . Thats called open ai schema

    def to_openai_schema(self) -> dict[str, Any]:
        schema = self.schema

        if isinstance(schema, type) and issubclass(schema, BaseModel):

            json_schema = model_json_schema(schema, mode="serialization")

            return {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": json_schema.get("properties", {}),
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
