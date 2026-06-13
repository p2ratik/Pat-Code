USERS

Purpose:

Identity layer.

CREATE TABLE users (
    id UUID PRIMARY KEY,

    email VARCHAR(255) UNIQUE,

    display_name VARCHAR(255),

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL,

    updated_at TIMESTAMP NOT NULL,

    deleted_at TIMESTAMP
);
ROLES

Purpose:

Authorization.

CREATE TABLE roles (
    id UUID PRIMARY KEY,

    name VARCHAR(50) UNIQUE NOT NULL,

    description TEXT,

    created_at TIMESTAMP NOT NULL
);

Seed:

super_admin
admin
user
premium
USER_ROLES

Purpose:

Many-to-many role mapping.

CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id),

    role_id UUID REFERENCES roles(id),

    created_at TIMESTAMP NOT NULL,

    PRIMARY KEY(user_id, role_id)
);
USER_CHANNELS

Purpose:

Future WhatsApp/Discord identities.

CREATE TABLE user_channels (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    channel_type VARCHAR(50),

    external_id TEXT,

    verified BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP NOT NULL
);

Examples:

whatsapp
discord
telegram
web
CONVERSATIONS

Purpose:

Conversation container.

CREATE TABLE conversations (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    title TEXT,

    channel VARCHAR(50),

    summary TEXT,

    created_at TIMESTAMP NOT NULL,

    updated_at TIMESTAMP NOT NULL
);
MESSAGES

Purpose:

Chat history.

CREATE TABLE messages (
    id UUID PRIMARY KEY,

    conversation_id UUID REFERENCES conversations(id),

    role VARCHAR(20),

    content TEXT,

    token_count INTEGER,

    tool_call_id TEXT,

    tool_calls JSONB,

    created_at TIMESTAMP NOT NULL
);

Roles:

system
user
assistant
tool
MEMORIES

Purpose:

Long-term memory.

CREATE TABLE memories (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    memory_type VARCHAR(50),

    source_type VARCHAR(50),

    content TEXT,

    embedding_id UUID,

    importance FLOAT,

    confidence FLOAT,

    source_message_id UUID REFERENCES messages(id),

    created_by VARCHAR(50),

    created_at TIMESTAMP NOT NULL,

    updated_at TIMESTAMP NOT NULL,

    deleted_at TIMESTAMP
);

Memory types:

fact
preference
goal
project
workflow

Source types:

conversation
task_summary
failure_analysis
manual

Created by:

user
memory_extractor
task_summarizer
failure_analyzer
AGENT_PROFILES

Purpose:

Runtime configuration.

CREATE TABLE agent_profiles (
    id UUID PRIMARY KEY,

    name VARCHAR(100),

    description TEXT,

    model_name VARCHAR(100),

    temperature FLOAT,

    max_turns INTEGER,

    version INTEGER,

    is_active BOOLEAN DEFAULT TRUE,

    prompt_id UUID,

    created_at TIMESTAMP NOT NULL
);

Examples:

Admin Agent
Default User Agent
USER_AGENT_PROFILES

Purpose:

Assign profile to user.

CREATE TABLE user_agent_profiles (
    user_id UUID REFERENCES users(id),

    profile_id UUID REFERENCES agent_profiles(id),

    PRIMARY KEY(user_id, profile_id)
);
PROMPTS

Purpose:

Prompt versioning.

CREATE TABLE prompts (
    id UUID PRIMARY KEY,

    name VARCHAR(100),

    version INTEGER,

    content TEXT,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL
);

Examples:

agent_v1
summarizer_v1
memory_extractor_v1
failure_analyzer_v1
task_summarizer_v1
TOOLS

Purpose:

Tool registry metadata.

CREATE TABLE tools (
    id UUID PRIMARY KEY,

    name VARCHAR(100) UNIQUE,

    description TEXT,

    created_at TIMESTAMP NOT NULL
);

Examples:

read_file
write_file
gmail_send
calendar_read
memory_edit
PROFILE_TOOLS

Purpose:

Tool authorization.

CREATE TABLE profile_tools (
    profile_id UUID REFERENCES agent_profiles(id),

    tool_id UUID REFERENCES tools(id),

    PRIMARY KEY(profile_id, tool_id)
);
AGENT_RUNS

Purpose:

Track every agent execution.

CREATE TABLE agent_runs (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    conversation_id UUID REFERENCES conversations(id),

    profile_id UUID REFERENCES agent_profiles(id),

    status VARCHAR(50),

    current_step INTEGER,

    total_steps INTEGER,

    input_message TEXT,

    final_response TEXT,

    failure_reason VARCHAR(100),

    error_message TEXT,

    started_at TIMESTAMP,

    completed_at TIMESTAMP
);

Status:

running
completed
failed
AGENT_STEPS

Purpose:

Observability.

CREATE TABLE agent_steps (
    id UUID PRIMARY KEY,

    agent_run_id UUID REFERENCES agent_runs(id),

    step_number INTEGER,

    step_type VARCHAR(50),

    tool_name VARCHAR(100),

    duration_ms INTEGER,

    input TEXT,

    output TEXT,

    created_at TIMESTAMP NOT NULL
);

Step types:

reasoning
tool_call
tool_result
error
completion
AGENT_CHECKPOINTS

Future use.

CREATE TABLE agent_checkpoints (
    id UUID PRIMARY KEY,

    agent_run_id UUID REFERENCES agent_runs(id),

    step_number INTEGER,

    checkpoint_data JSONB,

    created_at TIMESTAMP NOT NULL
);
MCP_SERVERS

Purpose:

Replacement for config.toml.

CREATE TABLE mcp_servers (
    id UUID PRIMARY KEY,

    name VARCHAR(100) UNIQUE,

    display_name VARCHAR(255),

    server_url TEXT,

    transport VARCHAR(50),

    startup_timeout_sec INTEGER,

    supports_oauth BOOLEAN,

    enabled BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL
);
MCP_SERVER_SCOPES

Purpose:

OAuth scope templates.

CREATE TABLE mcp_server_scopes (
    id UUID PRIMARY KEY,

    mcp_server_id UUID REFERENCES mcp_servers(id),

    scope TEXT
);
MCP_USER_CONNECTIONS

Purpose:

User MCP relationships.

CREATE TABLE mcp_user_connections (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    mcp_server_id UUID REFERENCES mcp_servers(id),

    status VARCHAR(50),

    connected_at TIMESTAMP,

    last_used_at TIMESTAMP,

    UNIQUE(user_id, mcp_server_id)
);

Status:

connected
expired
disconnected
error
refresh_required
disabled
MCP_CREDENTIALS

Purpose:

Encrypted OAuth credentials.

CREATE TABLE mcp_credentials (
    id UUID PRIMARY KEY,

    connection_id UUID REFERENCES mcp_user_connections(id),

    provider_user_id TEXT,

    encrypted_access_token TEXT,

    encrypted_refresh_token TEXT,

    token_type VARCHAR(50),

    expires_at TIMESTAMP,

    last_refresh_at TIMESTAMP,

    created_at TIMESTAMP,

    updated_at TIMESTAMP
);
MCP_SERVER_CONFIGS

Purpose:

Per-user MCP overrides.

CREATE TABLE mcp_server_configs (
    id UUID PRIMARY KEY,

    connection_id UUID REFERENCES mcp_user_connections(id),

    config JSONB,

    created_at TIMESTAMP
);

Example:

{
  "enabled": true,
  "startup_timeout_sec": 120
}
FILES (Future)
CREATE TABLE files (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    conversation_id UUID REFERENCES conversations(id),

    original_name TEXT,

    mime_type TEXT,

    size_bytes BIGINT,

    sha256_hash TEXT,

    s3_key TEXT,

    upload_source VARCHAR(50),

    created_at TIMESTAMP NOT NULL,

    deleted_at TIMESTAMP
);
ARTIFACTS (Future)

Generated files.

CREATE TABLE artifacts (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    conversation_id UUID REFERENCES conversations(id),

    artifact_type VARCHAR(50),

    name TEXT,

    s3_key TEXT,

    created_at TIMESTAMP NOT NULL,

    deleted_at TIMESTAMP
);
AUDIT_LOGS

Purpose:

Security and debugging.

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    action VARCHAR(255),

    metadata JSONB,

    ip_address TEXT,

    created_at TIMESTAMP NOT NULL
);

Examples:

ROLE_ASSIGNED
MCP_CONNECTED
MCP_DISCONNECTED
MEMORY_DELETED
PROFILE_UPDATED
For V1 (what I would actually build now)

Implement immediately:

users
roles
user_roles

conversations
messages

memories

agent_profiles
user_agent_profiles

prompts

tools
profile_tools

agent_runs
agent_steps

mcp_servers
mcp_server_scopes
mcp_user_connections
mcp_credentials
mcp_server_configs

audit_logs

Postpone until WhatsApp/dashboard:

user_channels
files
artifacts
agent_checkpoints