import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Boolean, Float, Integer, 
    ForeignKey, DateTime, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True)
    display_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    roles = relationship("Role", secondary="user_roles", back_populates="users")
    conversations = relationship("Conversation", back_populates="user")
    agent_profiles = relationship("AgentProfile", secondary="user_agent_profiles", back_populates="users")


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    users = relationship("User", secondary="user_roles", back_populates="roles")


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    title = Column(Text)
    channel = Column(String(50))
    summary = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"))
    role = Column(String(20), nullable=False)
    content = Column(Text)
    token_count = Column(Integer)
    tool_call_id = Column(Text)
    tool_calls = Column(JSONB)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class Memory(Base):
    __tablename__ = "memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    memory_type = Column(String(50))
    source_type = Column(String(50))
    content = Column(Text)
    embedding_id = Column(UUID(as_uuid=True))
    importance = Column(Float)
    confidence = Column(Float)
    source_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"))
    created_by = Column(String(50))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)


class AgentProfile(Base):
    __tablename__ = "agent_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100))
    description = Column(Text)
    model_name = Column(String(100))
    temperature = Column(Float)
    max_turns = Column(Integer)
    version = Column(Integer)
    is_active = Column(Boolean, default=True)
    prompt_id = Column(UUID(as_uuid=True), ForeignKey("prompts.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    users = relationship("User", secondary="user_agent_profiles", back_populates="agent_profiles")
    tools = relationship("Tool", secondary="profile_tools", back_populates="profiles")
    prompt = relationship("Prompt", back_populates="profiles", foreign_keys=[prompt_id])


class UserAgentProfile(Base):
    __tablename__ = "user_agent_profiles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id", ondelete="CASCADE"), primary_key=True)


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100))
    version = Column(Integer)
    content = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    profiles = relationship("AgentProfile", back_populates="prompt")


class Tool(Base):
    __tablename__ = "tools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True)
    description = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    profiles = relationship("AgentProfile", secondary="profile_tools", back_populates="tools")


class ProfileTool(Base):
    __tablename__ = "profile_tools"

    profile_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id", ondelete="CASCADE"), primary_key=True)
    tool_id = Column(UUID(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE"), primary_key=True)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"))
    profile_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id", ondelete="SET NULL"))
    status = Column(String(50), nullable=False, default="running")
    current_step = Column(Integer)
    total_steps = Column(Integer)
    input_message = Column(Text)
    final_response = Column(Text)
    failure_reason = Column(String(100))
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    steps = relationship("AgentStep", back_populates="agent_run")


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"))
    step_number = Column(Integer)
    step_type = Column(String(50))
    tool_name = Column(String(100))
    duration_ms = Column(Integer)
    input = Column(Text)
    output = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    agent_run = relationship("AgentRun", back_populates="steps")


class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True)
    display_name = Column(String(255))
    server_url = Column(Text)
    transport = Column(String(50))
    startup_timeout_sec = Column(Integer)
    supports_oauth = Column(Boolean)
    oauth_client_id = Column(Text, nullable=True)
    oauth_client_secret = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    mcp_tools = relationship("MCPTool", back_populates="server", cascade="all, delete-orphan")


class MCPServerScope(Base):
    __tablename__ = "mcp_server_scopes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mcp_server_id = Column(UUID(as_uuid=True), ForeignKey("mcp_servers.id", ondelete="CASCADE"))
    scope = Column(Text)


class MCPUserConnection(Base):
    __tablename__ = "mcp_user_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    mcp_server_id = Column(UUID(as_uuid=True), ForeignKey("mcp_servers.id", ondelete="CASCADE"))
    status = Column(String(50), nullable=False, default="disconnected")
    connected_at = Column(DateTime)
    last_used_at = Column(DateTime)

    __table_args__ = (UniqueConstraint("user_id", "mcp_server_id"),)

    server = relationship("MCPServer")
    credentials = relationship("MCPCredential", back_populates="connection", uselist=False, cascade="all, delete-orphan")
    config = relationship("MCPServerConfig", back_populates="connection", uselist=False, cascade="all, delete-orphan")


class MCPCredential(Base):
    __tablename__ = "mcp_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("mcp_user_connections.id", ondelete="CASCADE"))
    provider_user_id = Column(Text)
    encrypted_access_token = Column(Text)
    encrypted_refresh_token = Column(Text)
    token_type = Column(String(50))
    expires_at = Column(DateTime)
    last_refresh_at = Column(DateTime)
    # Stores the Dynamic Client Registration (DCR) output: client_id, client_secret,
    # token_endpoint_auth_method, and token_endpoint URL.  Required for providers
    # like Notion where the refresh_token grant must use the same DCR-issued
    # client_id/secret that was used during the authorization_code exchange.
    # Null for servers that use a static oauth_client_id from mcp_servers instead.
    dcr_client_info = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    connection = relationship("MCPUserConnection", back_populates="credentials")


class MCPServerConfig(Base):
    __tablename__ = "mcp_server_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("mcp_user_connections.id", ondelete="CASCADE"))
    config = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

    connection = relationship("MCPUserConnection", back_populates="config")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(255), nullable=False)
    metadata_json = Column("metadata", JSONB)
    ip_address = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MCPTool(Base):
    """Cached snapshot of tools discovered from an MCP server.

    Written by the sync endpoint so runtime never needs a live network call
    to know what tools a server exposes.
    """
    __tablename__ = "mcp_tools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Which server this tool belongs to
    mcp_server_id = Column(UUID(as_uuid=True), ForeignKey("mcp_servers.id"), nullable=False)
    # Name as reported by the MCP server (e.g. "search_github")
    tool_name = Column(Text, nullable=False)
    # Human-readable description forwarded from the server
    description = Column(Text)
    # Full JSON schema for the tool's input parameters (passed to the model verbatim)
    schema = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    server = relationship("MCPServer", back_populates="mcp_tools")


# ============================================================
# INTEGRATION PLATFORM
# ============================================================

class IntegrationProvider(Base):
    __tablename__ = "integration_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    auth_type = Column(String(50), nullable=False, default="oauth2")
    client_id = Column(Text, nullable=True)
    client_secret = Column(Text, nullable=True)
    auth_url = Column(Text, nullable=True)
    token_url = Column(Text, nullable=True)
    revoke_url = Column(Text, nullable=True)
    max_scopes = Column(JSONB, nullable=True)
    icon_url = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    connections = relationship("IntegrationUserConnection", back_populates="provider", cascade="all, delete-orphan")


class IntegrationUserConnection(Base):
    __tablename__ = "integration_user_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    provider_id = Column(UUID(as_uuid=True), ForeignKey("integration_providers.id", ondelete="CASCADE"))
    status = Column(String(50), nullable=False, default="disconnected")
    connected_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "provider_id"),)

    provider = relationship("IntegrationProvider", back_populates="connections")
    credentials = relationship("IntegrationCredential", back_populates="connection", uselist=False, cascade="all, delete-orphan")


class IntegrationCredential(Base):
    __tablename__ = "integration_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("integration_user_connections.id", ondelete="CASCADE"))
    encrypted_access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    token_type = Column(String(50), default="Bearer")
    scopes_granted = Column(JSONB, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    last_refresh_at = Column(DateTime, nullable=True)
    provider_user_email = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    connection = relationship("IntegrationUserConnection", back_populates="credentials")
