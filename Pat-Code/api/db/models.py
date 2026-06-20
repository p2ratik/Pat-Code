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
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MCPServerConfig(Base):
    __tablename__ = "mcp_server_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("mcp_user_connections.id", ondelete="CASCADE"))
    config = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(255), nullable=False)
    metadata_json = Column("metadata", JSONB)
    ip_address = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
