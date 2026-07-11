-- PAT Cloud Schema — V1
-- Run this in Neon SQL Editor to create all tables.
-- Order matters due to foreign key references.

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE,
    display_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP
);

-- ============================================================
-- ROLES
-- ============================================================
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- USER_ROLES
-- ============================================================
CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY(user_id, role_id)
);

-- ============================================================
-- CONVERSATIONS
-- ============================================================
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title TEXT,
    channel VARCHAR(50),
    summary TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- MESSAGES
-- ============================================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT,
    token_count INTEGER,
    tool_call_id TEXT,
    tool_calls JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);

-- ============================================================
-- MEMORIES
-- ============================================================
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    memory_type VARCHAR(50),
    source_type VARCHAR(50),
    content TEXT,
    embedding_id UUID,
    importance FLOAT,
    confidence FLOAT,
    source_message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    created_by VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP
);

-- ============================================================
-- AGENT_PROFILES
-- ============================================================
CREATE TABLE agent_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100),
    description TEXT,
    model_name VARCHAR(100),
    temperature FLOAT,
    max_turns INTEGER,
    version INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    prompt_id UUID REFERENCES prompts(id) ON DELETE SET NULL,
    owner_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Migration for existing databases:
-- ALTER TABLE agent_profiles ADD COLUMN IF NOT EXISTS owner_user_id UUID REFERENCES users(id) ON DELETE CASCADE;

-- ============================================================
-- USER_AGENT_PROFILES
-- ============================================================
CREATE TABLE user_agent_profiles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES agent_profiles(id) ON DELETE CASCADE,
    PRIMARY KEY(user_id, profile_id)
);

-- ============================================================
-- PROMPTS
-- ============================================================
CREATE TABLE prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100),
    version INTEGER,
    content TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- TOOLS
-- ============================================================
CREATE TABLE tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- PROFILE_TOOLS
-- ============================================================
CREATE TABLE profile_tools (
    profile_id UUID REFERENCES agent_profiles(id) ON DELETE CASCADE,
    tool_id UUID REFERENCES tools(id) ON DELETE CASCADE,
    PRIMARY KEY(profile_id, tool_id)
);

-- ============================================================
-- AGENT_RUNS
-- ============================================================
CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES agent_profiles(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    current_step INTEGER,
    total_steps INTEGER,
    input_message TEXT,
    final_response TEXT,
    failure_reason VARCHAR(100),
    error_message TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- ============================================================
-- AGENT_STEPS
-- ============================================================
CREATE TABLE agent_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_run_id UUID REFERENCES agent_runs(id) ON DELETE CASCADE,
    step_number INTEGER,
    step_type VARCHAR(50),
    tool_name VARCHAR(100),
    duration_ms INTEGER,
    input TEXT,
    output TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_steps_run ON agent_steps(agent_run_id, step_number);

-- ============================================================
-- MCP_SERVERS
-- ============================================================
CREATE TABLE mcp_servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE,
    display_name VARCHAR(255),
    server_url TEXT,
    transport VARCHAR(50),
    startup_timeout_sec INTEGER,
    supports_oauth BOOLEAN,
    oauth_client_id TEXT,
    oauth_client_secret TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Migration for existing databases:
-- ALTER TABLE mcp_servers ADD COLUMN IF NOT EXISTS oauth_client_id TEXT;
-- ALTER TABLE mcp_servers ADD COLUMN IF NOT EXISTS oauth_client_secret TEXT;

-- ============================================================
-- MCP_SERVER_SCOPES
-- ============================================================
CREATE TABLE mcp_server_scopes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mcp_server_id UUID REFERENCES mcp_servers(id) ON DELETE CASCADE,
    scope TEXT
);

-- ============================================================
-- MCP_USER_CONNECTIONS
-- ============================================================
CREATE TABLE mcp_user_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    mcp_server_id UUID REFERENCES mcp_servers(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'disconnected',
    connected_at TIMESTAMP,
    last_used_at TIMESTAMP,
    UNIQUE(user_id, mcp_server_id)
);

-- ============================================================
-- MCP_CREDENTIALS
-- ============================================================
CREATE TABLE mcp_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID REFERENCES mcp_user_connections(id) ON DELETE CASCADE,
    provider_user_id TEXT,
    encrypted_access_token TEXT,
    encrypted_refresh_token TEXT,
    token_type VARCHAR(50),
    expires_at TIMESTAMP,
    last_refresh_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- MCP_SERVER_CONFIGS
-- ============================================================
CREATE TABLE mcp_server_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID REFERENCES mcp_user_connections(id) ON DELETE CASCADE,
    config JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- For handeling network latencies 
CREATE TABLE mcp_tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mcp_server_id UUID REFERENCES mcp_servers(id),
    tool_name TEXT,
    description TEXT,
    schema JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_mcp_tools_server_id ON mcp_tools(mcp_server_id);

-- ============================================================
-- AUDIT_LOGS
-- ============================================================
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(255) NOT NULL,
    metadata JSONB,
    ip_address TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id, created_at);

-- ============================================================
-- INTEGRATION PLATFORM
-- ============================================================
CREATE TABLE integration_providers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) UNIQUE NOT NULL,
    display_name    VARCHAR(255) NOT NULL,
    auth_type       VARCHAR(50) NOT NULL DEFAULT 'oauth2',
    client_id       TEXT,
    client_secret   TEXT,
    auth_url        TEXT,
    token_url       TEXT,
    revoke_url      TEXT,
    max_scopes      JSONB,
    icon_url        TEXT,
    enabled         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE integration_user_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    provider_id     UUID REFERENCES integration_providers(id) ON DELETE CASCADE,
    status          VARCHAR(50) NOT NULL DEFAULT 'disconnected',
    connected_at    TIMESTAMP,
    last_used_at    TIMESTAMP,
    UNIQUE(user_id, provider_id)
);

CREATE TABLE integration_credentials (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id           UUID REFERENCES integration_user_connections(id) ON DELETE CASCADE,
    encrypted_access_token  TEXT,
    encrypted_refresh_token TEXT,
    token_type              VARCHAR(50) DEFAULT 'Bearer',
    scopes_granted          JSONB,
    expires_at              TIMESTAMP,
    last_refresh_at         TIMESTAMP,
    provider_user_email     TEXT,
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_intg_connections_user ON integration_user_connections(user_id);
CREATE INDEX idx_intg_credentials_conn ON integration_credentials(connection_id);

-- ============================================================
-- SEED DATA
-- ============================================================

-- Default roles
INSERT INTO roles (name, description) VALUES
    ('super_admin', 'Full system access'),
    ('admin', 'Administrative access'),
    ('user', 'Standard user access'),
    ('premium', 'Premium user access')
ON CONFLICT (name) DO NOTHING;

-- NOTE: Agent profiles and tools are seeded by the Python application
-- at startup via CloudDatabase._seed_default_profile(). Do NOT seed
-- agent_profiles here — the Python seeder is the single source of truth
-- because it also wires up the profile_tools assignments.
