import { apiClient } from './client';

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

export const authApi = {
  // Create a new user
  createUser: async (email: string, display_name: string): Promise<User> => {
    const response = await apiClient.post<User>('/users', { email, display_name });
    return response.data;
  },

  // Get user details
  getUser: async (userId: string): Promise<User> => {
    const response = await apiClient.get<User>(`/users/${userId}`);
    return response.data;
  },

  // Generate JWT token
  generateToken: async (userId: string): Promise<AuthToken> => {
    const response = await apiClient.post<AuthToken>(`/users/${userId}/token`);
    return response.data;
  },
};
