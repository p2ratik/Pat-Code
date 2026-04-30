from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from pathlib import Path
import os
from config.credentials import get_credential, APIKEY_KEY, BASEURL_KEY


class ModelConfig(BaseModel):
    # All The model related stuffs
    name: str = "gpt-oss-120b"
    temperature: float = Field(default=0, ge=0.0, le=2.0)
    context_window: int = 256_000   

class ShellEnvironmentPolicy(BaseModel):
    ignore_default_excludes: bool = False
    exclude_patterns: list[str] = Field(
        default_factory=lambda: ["*KEY*", "*TOKEN*", "*SECRET*"]
    )
    set_vars: dict[str, str] = Field(default_factory=dict)

class MCPOAuthConfig(BaseModel):
    """OAuth2 configuration for URL-based MCP servers.

    Supports two modes:
    - **Client-credentials** (machine-to-machine): supply ``client_id`` +
      ``client_secret``.  fastmcp's built-in ``OAuth`` helper will perform the
      token exchange automatically.
    - **Discovery / interactive**: omit ``client_id`` / ``client_secret`` and
      fastmcp will run the OAuth discovery + browser-consent flow instead.
    """

    client_id: str | None = None
    client_secret: str | None = None
    scopes: list[str] = Field(default_factory=list)
    # Optional: override the OAuth metadata / token endpoint discovered from the
    # MCP server URL.  Usually left empty so fastmcp handles discovery.
    token_url: str | None = None


class MCPServerConfig(BaseModel):
    enabled: bool = True
    startup_timeout_sec: float = 30

    # stdio transport
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: Path | None = None

    # http/sse transport
    url: str | None = None
    # Explicit transport override — skips the URL-suffix heuristic.
    # Leave as None to let the client auto-detect from the URL path.
    transport: Literal["sse", "streamable-http"] | None = None
    # Raw HTTP headers forwarded on every request (e.g. x-api-key).
    headers: dict[str, str] = Field(default_factory=dict)
    # Shorthand: injects `Authorization: Bearer <token>` automatically.
    auth_token: str | None = None
    # Full OAuth2 config.  Mutually exclusive with auth_token.
    oauth: MCPOAuthConfig | None = None

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

        if self.auth_token and self.oauth:
            raise ValueError(
                "MCP Server cannot have both 'auth_token' and 'oauth' — choose one"
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
        """Keyring takes priority; env var is the fallback."""
        return get_credential(APIKEY_KEY) or os.environ.get("API_KEY")

    @property
    def base_url(self) -> str | None:
        """Keyring takes priority; env var is the fallback."""
        return get_credential(BASEURL_KEY) or os.environ.get("BASE_URL")

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
            errors.append(
                "No API key found. Run 'agent --configure apikey <KEY>' "
                "or set the API_KEY environment variable."
            )

        if not self.cwd.exists():
            errors.append(f"Working directory does not exist: {self.cwd}")

        return errors

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")    
