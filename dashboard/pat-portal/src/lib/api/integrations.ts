import { apiClient } from "./client";

export interface IntegrationProvider {
  name: string;
  display_name: string;
  enabled: boolean;
}

export interface UserConnection {
  provider: string;             // matches backend IntegrationConnectionResponse
  display_name: string;
  status: string;               // "connected" | "disconnected"
  email: string | null;         // Google account email used for this connection
  connected_at: string | null;
  last_used_at: string | null;
}

export interface OAuthInitiateResponse {
  authorization_url: string;
  state: string;
}

export const integrationsApi = {
  /** List all registered providers. */
  getProviders: async (): Promise<IntegrationProvider[]> => {
    const res = await apiClient.get<IntegrationProvider[]>("/integrations/providers");
    return res.data;
  },

  /** List the current user's connections. */
  getConnections: async (): Promise<UserConnection[]> => {
    const res = await apiClient.get<UserConnection[]>("/integrations/connections");
    return res.data;
  },

  /** Start OAuth for a provider + tools. Returns the authorization_url to open. */
  initiateOAuth: async (
    providerName: string,
    requestedTools: string[],
    redirectUri: string,
  ): Promise<OAuthInitiateResponse> => {
    const res = await apiClient.post<OAuthInitiateResponse>("/integrations/oauth/initiate", {
      provider_name: providerName,
      requested_tools: requestedTools,
      redirect_uri: redirectUri,
    });
    return res.data;
  },

  /** Disconnect a provider. */
  disconnect: async (providerName: string): Promise<void> => {
    await apiClient.delete(`/integrations/connections/${providerName}`);
  },
};
