import { apiClient } from './client';

export interface Prompt {
  id: string;
  name: string;
  version: number;
  content: string;
  is_active: boolean;
  created_at: string;
}

export interface PromptCreate {
  name: string;
  content: string;
  version?: number;
}

export interface PromptUpdate {
  name?: string | null;
  content?: string | null;
  is_active?: boolean | null;
}

export const promptsApi = {
  // List all prompts
  getPrompts: async (): Promise<Prompt[]> => {
    const response = await apiClient.get<Prompt[]>('/prompts');
    return response.data;
  },

  // Create a new prompt
  createPrompt: async (data: PromptCreate): Promise<Prompt> => {
    const response = await apiClient.post<Prompt>('/prompts', data);
    return response.data;
  },

  // Get a single prompt
  getPrompt: async (promptId: string): Promise<Prompt> => {
    const response = await apiClient.get<Prompt>(`/prompts/${promptId}`);
    return response.data;
  },

  // Partially update a prompt
  updatePrompt: async (promptId: string, data: PromptUpdate): Promise<Prompt> => {
    const response = await apiClient.patch<Prompt>(`/prompts/${promptId}`, data);
    return response.data;
  },
};
