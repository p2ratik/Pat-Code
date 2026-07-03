from datetime import datetime
from pydantic import BaseModel, HttpUrl

class IntegrationProviderCreate(BaseModel):
    name: str
    display_name: str
    auth_type: str = "oauth2"
    client_id: str | None = None
    client_secret: str | None = None
    auth_url: str | None = None
    token_url: str | None = None
    revoke_url: str | None = None
    max_scopes: list[str] | None = None
    icon_url: str | None = None

class IntegrationProviderUpdate(BaseModel):
    display_name: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    max_scopes: list[str] | None = None
    icon_url: str | None = None
    enabled: bool | None = None

class IntegrationProviderResponse(BaseModel):
    id: str
    name: str
    display_name: str
    auth_type: str
    max_scopes: list[str] | None
    icon_url: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime

class IntegrationConnectionResponse(BaseModel):
    provider: str
    display_name: str
    status: str
    connected_at: datetime | None
    last_used_at: datetime | None

class OAuthInitiateRequest(BaseModel):
    provider_name: str
    redirect_uri: str

class OAuthInitiateResponse(BaseModel):
    authorization_url: str
    state: str

class OAuthCallbackRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str

class OAuthCallbackResponse(BaseModel):
    provider: str
    status: str
    email: str | None
    scopes: list[str] | None
