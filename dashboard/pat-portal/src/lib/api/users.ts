import { apiClient } from './client';
import { AgentProfile } from './profiles';

export const usersApi = {
  // Assign role to user
  assignRole: async (userId: string, roleName: string): Promise<{ detail: string }> => {
    const response = await apiClient.post<{ detail: string }>(`/users/${userId}/roles`, {
      role_name: roleName
    });
    return response.data;
  },

  // Get active agent profile for user
  getUserProfile: async (userId: string): Promise<AgentProfile | null> => {
    const response = await apiClient.get<AgentProfile | null>(`/users/${userId}/profile`);
    return response.data;
  },

  // Assign profile to user
  assignProfile: async (userId: string, profileId: string): Promise<{ detail: string }> => {
    const response = await apiClient.post<{ detail: string }>(`/users/${userId}/profile`, {
      profile_id: profileId
    });
    return response.data;
  },
};
