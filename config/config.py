from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator
from pathlib import Path
import os


class ModelConfig(BaseModel):
    # All The model related stuffs
    name: str = "elephant-alpha"
    temperature: float = Field(default=1, ge=0.0, le=2.0)
    context_window: int = 256_000   

class ShellEnvironmentPolicy(BaseModel):
    ignore_default_excludes: bool = False
    exclude_patterns: list[str] = Field(
        default_factory=lambda: ["*KEY*", "*TOKEN*", "*SECRET*"]
    )
    set_vars: dict[str, str] = Field(default_factory=dict)

class MCPServerConfig(BaseModel):
    enabled: bool = True
    startup_timeout_sec: float = 10

    # stdio transport
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: Path | None = None

    # http/sse transport
    url: str | None = None
    
    @model_validator(mode="after")
    def validate_transport(self) -> MCPServerConfig:
        has_command = self.command is not None
        has_url = self.url is not None

        if not has_command and not has_url:
            raise ValueError(
                "MCP Server must have either 'command' (stdio) or 'url' (http/sse)"
            )

        if has_command and has_url:
            raise ValueError(
                "MCP Server cannot have both 'command' (stdio) and 'url' (http/sse)"
            )

        return self    
@dataclass
class SubagentDefinition:
    name: str
    description: str
    goal_prompt: str
    allowed_tools: list[str] | None = None
    max_turns: int = 20
    timeout_seconds: float = 600

class ApprovalPolicy(str, Enum):
    ON_REQUEST = "on-request"
    ON_FAILURE = "on-failure"
    AUTO = "auto"
    AUTO_EDIT = "auto-edit"
    NEVER = "never"
    YOLO = "yolo"

class Config(BaseModel):
    model : ModelConfig = Field(default_factory=ModelConfig)
    cwd: Path = Field(default_factory=Path.cwd)
    max_turns : int = 100
    shell_environment: ShellEnvironmentPolicy = Field(
        default_factory=ShellEnvironmentPolicy
    )    
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)

    allowed_tools: list[str] | None = Field(
        None,
        description="If set, only these tools will be available to the agent",
    )

    approval : ApprovalPolicy = ApprovalPolicy.ON_REQUEST

    user_subagents : list[SubagentDefinition] | None = None

    @property
    def api_key(self) -> str | None:
        return os.environ.get("API_KEY") 
    
    @property
    def base_url(self) -> str | None:
        return os.environ.get("BASE_URL")

    @property
    def model_name(self) -> str:
        return self.model.name

    @property
    def temperature(self) -> float:
        return self.model.temperature

    # Note that the function name of property and setter function must be same 

    @temperature.setter  # Using setters to chanwge the parametes of the private function
    def temperature(self, value: str) -> None:
        self.model.temperature = value        

    @model_name.setter
    def model_name(self, value: str) -> None:
        self.model.name = value

    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.api_key:
            errors.append("No API key found. Set API_KEY environment variable")

        if not self.cwd.exists():
            errors.append(f"Working directory does not exist: {self.cwd}")

        return errors

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")    
