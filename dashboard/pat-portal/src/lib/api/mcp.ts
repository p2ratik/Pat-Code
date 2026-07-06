import { apiClient } from "./client";

export interface MCPServer {
  id: string;
  name: string;
  display_name: string;
  server_url: string;
  transport: string;
  startup_timeout_sec: number | null;
  supports_oauth: boolean | null;
  oauth_client_id: string | null;
  enabled: boolean;
  created_at: string;
}

export interface MCPServerCreate {
  name: string;
  display_name: string;
  server_url: string;
  transport: string;
  startup_timeout_sec?: number;
  supports_oauth?: boolean;
  oauth_client_id?: string;
  oauth_client_secret?: string;
  enabled?: boolean;
}

export interface MCPConnection {
  id: string;
  user_id: string;
  mcp_server_id: string;
  server_name: string;
  status: string;
  connected_at: string | null;
  last_used_at: string | null;
}

export interface MCPTool {
  id: string;
  mcp_server_id: string;
  tool_name: string;
  description: string | null;
  schema: Record<string, unknown> | null;
  updated_at: string;
}

export interface OAuthSubmission {
  server_name: string;
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number; // seconds
  provider_user_id?: string;
}

export interface OAuthStart {
  server_name: string;
  frontend_redirect_url?: string;
}

export interface OAuthStartResponse {
  server_name: string;
  authorization_url: string;
}

export interface OAuthTokenStatus {
  server_name: string;
  has_token: boolean;
  expires_at: string | null;
  is_expired: boolean;
  last_refresh_at: string | null;
}

export const mcpApi = {
  listServers: async (): Promise<MCPServer[]> => {
    const res = await apiClient.get<MCPServer[]>("/mcp/servers");
    return res.data;
  },

  registerServer: async (data: MCPServerCreate): Promise<MCPServer> => {
    const res = await apiClient.post<MCPServer>("/mcp/servers", data);
    return res.data;
  },

  connect: async (serverName: string): Promise<MCPConnection> => {
    const res = await apiClient.post<MCPConnection>("/mcp/connect", {
      server_name: serverName,
    });
    return res.data;
  },

  disconnect: async (serverName: string): Promise<MCPConnection> => {
    const res = await apiClient.post<MCPConnection>("/mcp/disconnect", {
      server_name: serverName,
    });
    return res.data;
  },

  getStatus: async (): Promise<MCPConnection[]> => {
    const res = await apiClient.get<MCPConnection[]>("/mcp/status");
    return res.data;
  },

  // Admin: connect to the live server, discover tools, and cache them in DB
  discoverTools: async (serverName: string): Promise<{ detail: string }> => {
    const res = await apiClient.post<{ detail: string }>(
      `/mcp/servers/${serverName}/discover`,
    );
    return res.data;
  },

  // Admin: push tool discovery results into the DB cache
  syncTools: async (
    serverName: string,
    tools: object[],
  ): Promise<{ detail: string }> => {
    const res = await apiClient.post<{ detail: string }>(
      `/mcp/servers/${serverName}/sync`,
      tools,
    );
    return res.data;
  },

  getServerTools: async (serverName: string): Promise<MCPTool[]> => {
    const res = await apiClient.get<MCPTool[]>(
      `/mcp/servers/${serverName}/tools`,
    );
    return res.data;
  },

  // Submit an OAuth access token after the user completes the OAuth browser flow.
  submitOAuthToken: async (data: OAuthSubmission): Promise<MCPConnection> => {
    const res = await apiClient.post<MCPConnection>(
      "/mcp/oauth/callback",
      data,
    );
    return res.data;
  },

  startOAuth: async (data: OAuthStart): Promise<OAuthStartResponse> => {
    const res = await apiClient.post<OAuthStartResponse>(
      "/mcp/oauth/start",
      data,
    );
    return res.data;
  },

  getOAuthTokenStatus: async (
    serverName: string,
  ): Promise<OAuthTokenStatus> => {
    const res = await apiClient.get<OAuthTokenStatus>(
      `/mcp/oauth/token-status/${serverName}`,
    );
    return res.data;
  },

  reconnectOAuth: async (data: OAuthStart): Promise<OAuthStartResponse> => {
    const res = await apiClient.post<OAuthStartResponse>(
      "/mcp/oauth/reconnect",
      data,
    );
    return res.data;
  },
};
