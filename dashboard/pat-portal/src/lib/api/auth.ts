import { apiClient } from "./client";
import type { AgentProfile } from "./profiles";

export interface User {
  id: string;
  email: string;
  display_name: string;
  roles: string[];
  is_active: boolean;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
  is_new_user: boolean;
}

export const authApi = {
  /** Self-service: find-or-create by email, returns JWT + user in one call. */
  loginOrRegister: async (email: string, displayName?: string): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>("/users/login", {
      email,
      display_name: displayName,
    });
    return response.data;
  },

  createUser: async (email: string, display_name: string): Promise<User> => {
    const response = await apiClient.post<User>("/users", {
      email,
      display_name,
    });
    return response.data;
  },

  listUsers: async (): Promise<User[]> => {
    const response = await apiClient.get<User[]>("/users");
    return response.data;
  },

  getUser: async (userId: string): Promise<User> => {
    const response = await apiClient.get<User>(`/users/${userId}`);
    return response.data;
  },

  generateToken: async (userId: string): Promise<AuthToken> => {
    const response = await apiClient.post<AuthToken>(`/users/${userId}/token`);
    return response.data;
  },

  getUserProfile: async (userId: string): Promise<AgentProfile | null> => {
    const response = await apiClient.get<AgentProfile | null>(
      `/users/${userId}/profile`,
    );
    return response.data;
  },

  assignProfile: async (
    userId: string,
    profileId: string,
  ): Promise<{ detail: string }> => {
    const response = await apiClient.post<{ detail: string }>(
      `/users/${userId}/profile`,
      {
        profile_id: profileId,
      },
    );
    return response.data;
  },

  assignRole: async (
    userId: string,
    roleName: string,
  ): Promise<{ detail: string }> => {
    const response = await apiClient.post<{ detail: string }>(
      `/users/${userId}/roles`,
      {
        role_name: roleName,
      },
    );
    return response.data;
  },
};
