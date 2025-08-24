import React, { useState, useEffect, useCallback } from 'react';
import { Menu, Sparkles } from 'lucide-react';
import { Chat } from './components/Chat';
import { Graph } from './components/Graph';
import { Sidebar } from './components/Sidebar';
import { useEventSource } from './hooks/useEventSource';
import { storage } from './utils/storage';
import { Conversation, Message, Source, Graph as GraphType } from './types';

function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isDark, setIsDark] = useState(false);
  
  // Streaming state
  const [currentText, setCurrentText] = useState('');
  const [currentSources, setCurrentSources] = useState<Source[]>([]);
  const [currentGraph, setCurrentGraph] = useState<GraphType>({ nodes: [], edges: [] });
  
  const { sendQuery, isStreaming, error } = useEventSource();

  // Initialize theme and conversations
  useEffect(() => {
    const theme = storage.getTheme();
    setIsDark(theme === 'dark');
    document.documentElement.classList.toggle('dark', theme === 'dark');

    const storedConversations = storage.getConversations();
    setConversations(storedConversations);

    const currentId = storage.getCurrentConversationId();
    if (currentId && storedConversations.find(c => c.id === currentId)) {
      setCurrentConversationId(currentId);
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = isDark ? 'light' : 'dark';
    setIsDark(!isDark);
    storage.setTheme(newTheme);
    document.documentElement.classList.toggle('dark', newTheme === 'dark');
  };

  const generateConversationTitle = (message: string): string => {
    const words = message.split(' ').slice(0, 6);
    return words.join(' ') + (message.split(' ').length > 6 ? '...' : '');
  };

  const createNewConversation = useCallback((): string => {
    const id = Date.now().toString();
    const newConversation: Conversation = {
      id,
      title: 'New Chat',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };

    setConversations(prev => [newConversation, ...prev]);
    setCurrentConversationId(id);
    storage.setCurrentConversationId(id);
    
    // Reset streaming state
    setCurrentText('');
    setCurrentSources([]);
    setCurrentGraph({ nodes: [], edges: [] });

    return id;
  }, []);

  const updateConversation = useCallback((
    conversationId: string, 
    updates: Partial<Conversation>
  ) => {
    setConversations(prev => {
      const updated = prev.map(conv => 
        conv.id === conversationId 
          ? { ...conv, ...updates, updatedAt: Date.now() }
          : conv
      );
      storage.saveConversations(updated);
      return updated;
    });
  }, []);

  const handleSendMessage = useCallback((messageText: string) => {
    let conversationId = currentConversationId;
    
    // Create new conversation if none exists
    if (!conversationId) {
      conversationId = createNewConversation();
    }

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: messageText,
      timestamp: Date.now(),
    };

    updateConversation(conversationId, {
      title: generateConversationTitle(messageText),
      messages: [...(conversations.find(c => c.id === conversationId)?.messages || []), userMessage],
    });

    // Reset streaming state
    setCurrentText('');
    setCurrentSources([]);
    setCurrentGraph({ nodes: [], edges: [] });

    // Send query
    sendQuery(messageText, (text, sources, graph) => {
      setCurrentText(text);
      if (sources) setCurrentSources(sources);
      if (graph) setCurrentGraph(graph);

      // If streaming is complete, add assistant message
      if (text && !isStreaming) {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: text,
          sources,
          graph,
          timestamp: Date.now(),
        };

        const currentConv = conversations.find(c => c.id === conversationId);
        if (currentConv) {
          updateConversation(conversationId, {
            messages: [...currentConv.messages, assistantMessage],
          });
        }
      }
    });
  }, [currentConversationId, conversations, createNewConversation, updateConversation, sendQuery, isStreaming]);

  const handleSelectConversation = (id: string) => {
    setCurrentConversationId(id);
    storage.setCurrentConversationId(id);
    setSidebarOpen(false);
    
    // Reset streaming state
    setCurrentText('');
    setCurrentSources([]);
    setCurrentGraph({ nodes: [], edges: [] });

    // Load graph from last assistant message
    const conversation = conversations.find(c => c.id === id);
    if (conversation) {
      const lastAssistantMessage = conversation.messages
        .slice()
        .reverse()
        .find(m => m.type === 'assistant' && m.graph);
      
      if (lastAssistantMessage && lastAssistantMessage.graph) {
        setCurrentGraph(lastAssistantMessage.graph);
      }
    }
  };

  const handleDeleteConversation = (id: string) => {
    setConversations(prev => {
      const filtered = prev.filter(c => c.id !== id);
      storage.saveConversations(filtered);
      return filtered;
    });

    if (currentConversationId === id) {
      setCurrentConversationId(null);
      storage.setCurrentConversationId('');
      setCurrentText('');
      setCurrentSources([]);
      setCurrentGraph({ nodes: [], edges: [] });
    }
  };

  const currentConversation = conversations.find(c => c.id === currentConversationId);

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        >
          <div className="absolute inset-0 bg-black opacity-50" />
          <div className="absolute left-0 top-0 h-full w-80">
            <Sidebar
              conversations={conversations}
              currentConversationId={currentConversationId}
              onSelectConversation={handleSelectConversation}
              onNewConversation={createNewConversation}
              onDeleteConversation={handleDeleteConversation}
              isDark={isDark}
              onToggleTheme={toggleTheme}
            />
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <div className="hidden lg:block w-80 h-full">
        <Sidebar
          conversations={conversations}
          currentConversationId={currentConversationId}
          onSelectConversation={handleSelectConversation}
          onNewConversation={createNewConversation}
          onDeleteConversation={handleDeleteConversation}
          isDark={isDark}
          onToggleTheme={toggleTheme}
        />
      </div>

      {/* Main content */}
      <div className="flex flex-1 min-w-0">
        {/* Chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Mobile header */}
          <div className="lg:hidden flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
            >
              <Menu size={20} />
            </button>
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <Sparkles size={12} className="text-white" />
              </div>
              <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Scholar AI
              </h1>
            </div>
            <div className="w-10" />
          </div>

          <Chat
            messages={currentConversation?.messages || []}
            onSendMessage={handleSendMessage}
            isStreaming={isStreaming}
            currentText={currentText}
            currentSources={currentSources}
            currentGraph={currentGraph}
            className="bg-white dark:bg-gray-900"
          />

          {error && (
            <div className="p-4 bg-red-50 dark:bg-red-900/20 border-t border-red-200 dark:border-red-800">
              <p className="text-sm text-red-600 dark:text-red-400">
                Error: {error}
              </p>
            </div>
          )}
        </div>

        {/* Graph panel */}
        <div className="hidden xl:block w-96 h-full border-l border-gray-200 dark:border-gray-700">
          <Graph graph={currentGraph} className="h-full" />
        </div>
      </div>
    </div>
  );
}

export default App;