import { apiClient } from './client';

export interface MCPServer {
  id: string;
  name: string;
  display_name: string;
  server_url: string;
  transport: string;
  startup_timeout_sec: number | null;
  supports_oauth: boolean | null;
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

export const mcpApi = {
  listServers: async (): Promise<MCPServer[]> => {
    const res = await apiClient.get<MCPServer[]>('/mcp/servers');
    return res.data;
  },

  registerServer: async (data: MCPServerCreate): Promise<MCPServer> => {
    const res = await apiClient.post<MCPServer>('/mcp/servers', data);
    return res.data;
  },

  connect: async (serverName: string): Promise<MCPConnection> => {
    const res = await apiClient.post<MCPConnection>('/mcp/connect', { server_name: serverName });
    return res.data;
  },

  disconnect: async (serverName: string): Promise<MCPConnection> => {
    const res = await apiClient.post<MCPConnection>('/mcp/disconnect', { server_name: serverName });
    return res.data;
  },

  getStatus: async (): Promise<MCPConnection[]> => {
    const res = await apiClient.get<MCPConnection[]>('/mcp/status');
    return res.data;
  },

  // Admin: connect to the live server, discover tools, and cache them in DB
  discoverTools: async (serverName: string): Promise<{ detail: string }> => {
    const res = await apiClient.post<{ detail: string }>(`/mcp/servers/${serverName}/discover`);
    return res.data;
  },

  // Admin: push tool discovery results into the DB cache
  syncTools: async (serverName: string, tools: object[]): Promise<{ detail: string }> => {
    const res = await apiClient.post<{ detail: string }>(`/mcp/servers/${serverName}/sync`, tools);
    return res.data;
  },

  getServerTools: async (serverName: string): Promise<MCPTool[]> => {
    const res = await apiClient.get<MCPTool[]>(`/mcp/servers/${serverName}/tools`);
    return res.data;
  },
};
