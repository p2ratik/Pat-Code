import { apiClient } from './client';

export interface AgentProfile {
  id: string;
  name: string;
  description: string | null;
  model_name: string;
  temperature: number;
  max_turns: number;
  version: number;
  is_active: boolean;
  prompt_id: string | null;
}

export interface ProfileCreate {
  name: string;
  model_name?: string;
  temperature?: number;
  max_turns?: number;
  description?: string | null;
  prompt_id?: string | null;
}

export const profilesApi = {
  // List all profiles
  getProfiles: async (): Promise<AgentProfile[]> => {
    const response = await apiClient.get<AgentProfile[]>('/profiles');
    return response.data;
  },

  // Create a new profile
  createProfile: async (data: ProfileCreate): Promise<AgentProfile> => {
    const response = await apiClient.post<AgentProfile>('/profiles', data);
    return response.data;
  },
};
