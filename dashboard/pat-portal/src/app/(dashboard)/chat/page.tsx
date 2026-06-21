'use client';

import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { chatApi } from '@/lib/api/chat';
import { conversationsApi, ConversationMessage } from '@/lib/api/conversations';
import { profilesApi } from '@/lib/api/profiles';
import { useAuthStore } from '@/lib/store/useAuthStore';
import { authApi } from '@/lib/api/auth';
import { Send, Bot, User as UserIcon, Plus, MessageSquare } from 'lucide-react';
import clsx from 'clsx';

type LocalMessage = { role: 'user' | 'agent'; content: string };

function groupConversationsByDate(conversations: { id: string; title: string | null; updated_at: string }[]) {
  const now = new Date();
  const todayStr = now.toDateString();
  const yesterdayStr = new Date(now.getTime() - 86400000).toDateString();

  const groups: Record<string, typeof conversations> = {};
  for (const c of conversations) {
    const d = new Date(c.updated_at);
    let label: string;
    if (d.toDateString() === todayStr) label = 'Today';
    else if (d.toDateString() === yesterdayStr) label = 'Yesterday';
    else {
      const diff = Math.floor((now.getTime() - d.getTime()) / 86400000);
      if (diff < 7) label = 'This Week';
      else if (diff < 30) label = 'This Month';
      else label = d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
    }
    if (!groups[label]) groups[label] = [];
    groups[label].push(c);
  }
  return groups;
}

export default function ChatPage() {
  const { user } = useAuthStore();
  const qc = useQueryClient();

  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [input, setInput] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Fetch conversation history
  const { data: conversations, isLoading: historyLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => conversationsApi.getConversations(50),
    enabled: !!user,
  });

  // Fetch current user's profile for context panel
  const { data: userProfile } = useQuery({
    queryKey: ['userProfile', user?.id],
    queryFn: () => user ? authApi.getUserProfile(user.id) : null,
    enabled: !!user,
  });

  // Fetch all profiles to resolve name if needed
  const { data: profileTools } = useQuery({
    queryKey: ['profileToolsList', userProfile?.id],
    queryFn: () => userProfile ? import('@/lib/api/tools').then(m => m.toolsApi.getProfileTools(userProfile.id)) : null,
    enabled: !!userProfile,
  });

  const chatMutation = useMutation({
    mutationFn: chatApi.sendMessage,
    onSuccess: (data) => {
      setConversationId(data.conversation_id);
      setMessages(prev => [...prev, { role: 'agent', content: data.response }]);
      // Refresh conversation list so the new conversation appears
      qc.invalidateQueries({ queryKey: ['conversations'] });
    },
  });

  const handleSend = () => {
    if (!input.trim() || chatMutation.isPending) return;
    setMessages(prev => [...prev, { role: 'user', content: input }]);
    chatMutation.mutate({ message: input, conversation_id: conversationId });
    setInput('');
  };

  const handleNewChat = () => {
    setMessages([]);
    setConversationId(null);
  };

  const handleLoadConversation = async (id: string) => {
    if (id === conversationId) return;
    setLoadingHistory(true);
    try {
      const msgs = await conversationsApi.getMessages(id);
      setConversationId(id);
      setMessages(
        msgs
          .filter(m => m.role === 'user' || m.role === 'assistant')
          .map(m => ({
            role: m.role === 'user' ? 'user' : 'agent',
            content: m.content ?? '',
          }))
      );
    } catch (e) {
      console.error('Failed to load conversation', e);
    } finally {
      setLoadingHistory(false);
    }
  };

  const groupedConversations = conversations ? groupConversationsByDate(conversations) : {};

  return (
    <div className="flex h-[calc(100vh-56px)] bg-[#0A0A0A]">
      {/* Left Sidebar – History */}
      <div className="w-64 border-r border-zinc-800 flex flex-col hidden md:flex bg-zinc-900/20">
        <div className="p-3 border-b border-zinc-800 flex items-center justify-between">
          <span className="text-sm font-medium text-zinc-300">History</span>
          <button
            onClick={handleNewChat}
            title="New chat"
            className="p-1.5 rounded-md text-zinc-500 hover:text-white hover:bg-zinc-800 transition-colors"
          >
            <Plus size={15} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-4">
          {historyLoading && (
            <p className="text-xs text-zinc-600 px-2 py-2">Loading history…</p>
          )}
          {!historyLoading && !conversations?.length && (
            <p className="text-xs text-zinc-600 px-2 py-4 text-center">No conversations yet.</p>
          )}
          {Object.entries(groupedConversations).map(([label, convs]) => (
            <div key={label}>
              <div className="text-xs text-zinc-600 px-2 py-1 font-medium uppercase tracking-wider">
                {label}
              </div>
              {convs.map(c => (
                <button
                  key={c.id}
                  onClick={() => handleLoadConversation(c.id)}
                  className={clsx(
                    'w-full text-left px-2 py-2 text-sm rounded-md cursor-pointer truncate transition-colors flex items-center gap-2',
                    conversationId === c.id
                      ? 'bg-zinc-800 text-white'
                      : 'text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200'
                  )}
                >
                  <MessageSquare size={13} className="shrink-0 opacity-60" />
                  <span className="truncate">{c.title || 'Untitled conversation'}</span>
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Center – Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {loadingHistory ? (
            <div className="h-full flex items-center justify-center text-zinc-500 flex-col gap-3">
              <Bot size={40} className="opacity-20 animate-pulse" />
              <p className="text-sm">Loading conversation…</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="h-full flex items-center justify-center text-zinc-500 flex-col gap-4">
              <Bot size={48} className="opacity-20" />
              <div className="text-center">
                <p className="text-base">How can I help you today?</p>
                {userProfile && (
                  <p className="text-xs mt-1 text-zinc-600">
                    Using <span className="text-zinc-500">{userProfile.name}</span> profile
                    · <span className="text-zinc-500">{userProfile.model_name}</span>
                  </p>
                )}
              </div>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div
                key={i}
                className={clsx(
                  'flex gap-4 max-w-3xl mx-auto w-full',
                  msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'
                )}
              >
                <div className="w-8 h-8 rounded-md bg-zinc-800 flex items-center justify-center shrink-0">
                  {msg.role === 'user' ? <UserIcon size={16} /> : <Bot size={16} />}
                </div>
                <div
                  className={clsx(
                    'px-4 py-3 rounded-lg text-sm leading-relaxed max-w-[80%]',
                    msg.role === 'user'
                      ? 'bg-zinc-100 text-zinc-900 rounded-tr-none'
                      : 'bg-zinc-900/80 border border-zinc-800 rounded-tl-none text-zinc-200'
                  )}
                >
                  {msg.content}
                </div>
              </div>
            ))
          )}

          {chatMutation.isPending && (
            <div className="flex gap-4 max-w-3xl mx-auto w-full">
              <div className="w-8 h-8 rounded-md bg-zinc-800 flex items-center justify-center shrink-0">
                <Bot size={16} />
              </div>
              <div className="px-4 py-3 rounded-lg text-sm bg-zinc-900/80 border border-zinc-800 flex items-center gap-1.5 text-zinc-400">
                <span className="animate-bounce" style={{ animationDelay: '0ms' }}>●</span>
                <span className="animate-bounce" style={{ animationDelay: '150ms' }}>●</span>
                <span className="animate-bounce" style={{ animationDelay: '300ms' }}>●</span>
              </div>
            </div>
          )}

          {chatMutation.isError && (
            <div className="max-w-3xl mx-auto w-full">
              <p className="text-xs text-red-400 px-2">
                {(chatMutation.error as any)?.response?.data?.detail || 'Request failed. Please try again.'}
              </p>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div className="p-4 border-t border-zinc-800 bg-[#0A0A0A]">
          <div className="max-w-3xl mx-auto relative">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder="Send a message to PAT…"
              disabled={chatMutation.isPending || loadingHistory}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg pl-4 pr-12 py-3 text-sm focus:outline-none focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500 disabled:opacity-50 transition-colors"
            />
            <button
              onClick={handleSend}
              disabled={chatMutation.isPending || !input.trim() || loadingHistory}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800 disabled:opacity-50 transition-colors"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Right sidebar – Context panel */}
      <div className="w-72 border-l border-zinc-800 hidden xl:block bg-[#0A0A0A] p-5 overflow-y-auto">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-4">
          Runtime Context
        </h3>

        <div className="space-y-6">
          <div>
            <div className="text-xs text-zinc-500 mb-1">Agent Profile</div>
            <div className="text-sm font-medium text-zinc-200">
              {userProfile?.name ?? <span className="text-zinc-600 italic">No profile</span>}
            </div>
          </div>

          <div>
            <div className="text-xs text-zinc-500 mb-1">Model</div>
            <div className="text-sm font-medium text-zinc-200 bg-zinc-900 px-2 py-1 rounded inline-block border border-zinc-800">
              {userProfile?.model_name ?? '—'}
            </div>
          </div>

          <div>
            <div className="text-xs text-zinc-500 mb-1">Temperature</div>
            <div className="text-sm font-medium text-zinc-200">
              {userProfile?.temperature ?? '—'}
            </div>
          </div>

          <div>
            <div className="text-xs text-zinc-500 mb-2">Enabled Tools</div>
            <div className="flex flex-col gap-1.5">
              {profileTools && profileTools.length > 0 ? (
                profileTools.map(tool => (
                  <div key={tool.id} className="text-xs text-zinc-300 flex items-center gap-2">
                    <div className="w-1 h-1 rounded-full bg-emerald-500" />
                    {tool.name}
                  </div>
                ))
              ) : (
                <span className="text-xs text-zinc-600 italic">No tools configured</span>
              )}
            </div>
          </div>

          {conversationId && (
            <div className="pt-4 border-t border-zinc-800">
              <div className="text-xs text-zinc-500 mb-1">Conversation ID</div>
              <div
                className="text-xs font-mono text-zinc-400 truncate"
                title={conversationId}
              >
                {conversationId}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
