import { apiClient } from "./client";

export interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string | null;
  created_at: string;
}

export const conversationsApi = {
  // List conversations for the current user (newest first)
  getConversations: async (limit = 50): Promise<Conversation[]> => {
    const response = await apiClient.get<Conversation[]>("/conversations", {
      params: { limit },
    });
    return response.data;
  },

  // Get messages for a specific conversation
  getMessages: async (
    conversationId: string,
  ): Promise<ConversationMessage[]> => {
    const response = await apiClient.get<ConversationMessage[]>(
      `/conversations/${conversationId}/messages`,
    );
    return response.data;
  },
};
