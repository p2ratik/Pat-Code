import { apiClient } from "./client";

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

export interface ProfileUpdate {
  name?: string | null;
  model_name?: string | null;
  temperature?: number | null;
  max_turns?: number | null;
  description?: string | null;
  prompt_id?: string | null;
  is_active?: boolean | null;
}

export const profilesApi = {
  // List all profiles
  getProfiles: async (): Promise<AgentProfile[]> => {
    const response = await apiClient.get<AgentProfile[]>("/profiles");
    return response.data;
  },

  // Get a single profile (fetches full list, finds by id - backend has no single-get)
  getProfile: async (profileId: string): Promise<AgentProfile | null> => {
    const response = await apiClient.get<AgentProfile[]>("/profiles");
    return response.data.find((p) => p.id === profileId) ?? null;
  },

  // Create a new profile
  createProfile: async (data: ProfileCreate): Promise<AgentProfile> => {
    const response = await apiClient.post<AgentProfile>("/profiles", data);
    return response.data;
  },

  // Partially update a profile
  updateProfile: async (
    profileId: string,
    data: ProfileUpdate,
  ): Promise<AgentProfile> => {
    const response = await apiClient.patch<AgentProfile>(
      `/profiles/${profileId}`,
      data,
    );
    return response.data;
  },
};
