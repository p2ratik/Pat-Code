import { apiClient } from './client';

export interface ChatMessage {
  message: string;
  conversation_id?: string | null;
}

export interface ChatResponse {
  conversation_id: string;
  response: string;
}

export const chatApi = {
  sendMessage: async (data: ChatMessage): Promise<ChatResponse> => {
    const response = await apiClient.post<ChatResponse>('/chat', data);
    return response.data;
  },
};
