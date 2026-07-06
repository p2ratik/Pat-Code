import { apiClient } from "./client";
import { AgentProfile } from "./profiles";

export interface Tool {
  id: string;
  name: string;
  description: string | null;
}

export const toolsApi = {
  // List all registered tools
  getTools: async (): Promise<Tool[]> => {
    const response = await apiClient.get<Tool[]>("/tools");
    return response.data;
  },

  // Get profile tools
  getProfileTools: async (profileId: string): Promise<Tool[]> => {
    const response = await apiClient.get<Tool[]>(
      `/profiles/${profileId}/tools`,
    );
    return response.data;
  },

  // Assign tools to profile
  assignToolsToProfile: async (
    profileId: string,
    toolNames: string[],
  ): Promise<{ detail: string }> => {
    const response = await apiClient.put<{ detail: string }>(
      `/profiles/${profileId}/tools`,
      {
        tool_names: toolNames,
      },
    );
    return response.data;
  },
};
