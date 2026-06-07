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
