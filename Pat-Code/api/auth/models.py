from pydantic import BaseModel, field_validator


class UserCreate(BaseModel):
    email: str
    display_name: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    roles: list[str]
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RoleAssign(BaseModel):
    role_name: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None

    @field_validator("conversation_id", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v


class ChatResponse(BaseModel):
    conversation_id: str
    response: str


# ------------------------------------------------------------------
# Phase 2: Agent Profiles + Tool Authorization
# ------------------------------------------------------------------

class ProfileCreate(BaseModel):
    name: str
    model_name: str = "gpt-4.1-mini"
    temperature: float = 0.7
    max_turns: int = 100
    description: str | None = None


class ProfileResponse(BaseModel):
    id: str
    name: str
    description: str | None
    model_name: str
    temperature: float
    max_turns: int
    version: int

    model_config = {"from_attributes": True}


class ProfileAssign(BaseModel):
    profile_id: str


class ToolResponse(BaseModel):
    id: str
    name: str
    description: str | None

    model_config = {"from_attributes": True}


class ProfileToolsAssign(BaseModel):
    tool_names: list[str]
