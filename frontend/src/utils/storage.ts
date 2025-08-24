import { Conversation } from '../types';

const CONVERSATIONS_KEY = 'scholar_conversations';
const CURRENT_CONVERSATION_KEY = 'scholar_current_conversation';
const THEME_KEY = 'scholar_theme';

export const storage = {
  // Conversations
  getConversations: (): Conversation[] => {
    try {
      const stored = localStorage.getItem(CONVERSATIONS_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  },

  saveConversations: (conversations: Conversation[]) => {
    try {
      localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations));
    } catch (error) {
      console.error('Failed to save conversations:', error);
    }
  },

  getCurrentConversationId: (): string | null => {
    return localStorage.getItem(CURRENT_CONVERSATION_KEY);
  },

  setCurrentConversationId: (id: string) => {
    localStorage.setItem(CURRENT_CONVERSATION_KEY, id);
  },

  // Theme
  getTheme: (): 'light' | 'dark' => {
    const stored = localStorage.getItem(THEME_KEY);
    return stored === 'dark' ? 'dark' : 'light';
  },

  setTheme: (theme: 'light' | 'dark') => {
    localStorage.setItem(THEME_KEY, theme);
  },
};