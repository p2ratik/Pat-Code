'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { chatApi } from '@/lib/api/chat';
import { Send, Bot, User as UserIcon } from 'lucide-react';
import clsx from 'clsx';

export default function ChatPage() {
  const [messages, setMessages] = useState<{role: 'user' | 'agent', content: string}[]>([]);
  const [input, setInput] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);

  const chatMutation = useMutation({
    mutationFn: chatApi.sendMessage,
    onSuccess: (data) => {
      setConversationId(data.conversation_id);
      setMessages((prev) => [...prev, { role: 'agent', content: data.response }]);
    },
  });

  const handleSend = () => {
    if (!input.trim()) return;
    
    setMessages((prev) => [...prev, { role: 'user', content: input }]);
    chatMutation.mutate({ message: input, conversation_id: conversationId });
    setInput('');
  };

  return (
    <div className="flex h-[calc(100vh-56px)] bg-[#0A0A0A]">
      {/* Left Sidebar - History */}
      <div className="w-64 border-r border-zinc-800 flex flex-col hidden md:flex bg-zinc-900/20">
        <div className="p-4 border-b border-zinc-800 font-medium text-sm text-zinc-300">
          History
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {/* Placeholder for history */}
          <div className="text-xs text-zinc-500 px-2 py-2 font-medium">Today</div>
          <div className="px-2 py-2 text-sm text-zinc-300 hover:bg-zinc-800 rounded-md cursor-pointer truncate">
            Fixing Netlify deploy
          </div>
          <div className="px-2 py-2 text-sm text-zinc-300 hover:bg-zinc-800 rounded-md cursor-pointer truncate">
            Schema mismatch analysis
          </div>
        </div>
      </div>

      {/* Center - Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex items-center justify-center text-zinc-500 flex-col gap-4">
              <Bot size={48} className="opacity-20" />
              <p>How can I help you today?</p>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div key={i} className={clsx("flex gap-4 max-w-3xl mx-auto w-full", msg.role === 'user' ? "flex-row-reverse" : "flex-row")}>
                <div className="w-8 h-8 rounded-md bg-zinc-800 flex items-center justify-center shrink-0">
                  {msg.role === 'user' ? <UserIcon size={16} /> : <Bot size={16} />}
                </div>
                <div className={clsx("px-4 py-3 rounded-lg text-sm leading-relaxed", 
                  msg.role === 'user' ? "bg-zinc-100 text-zinc-900 rounded-tr-none" : "bg-zinc-900/80 border border-zinc-800 rounded-tl-none")}>
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
               <div className="px-4 py-3 rounded-lg text-sm bg-zinc-900/80 border border-zinc-800 flex items-center gap-2 text-zinc-400">
                 <span className="animate-pulse">●</span>
                 <span className="animate-pulse animation-delay-200">●</span>
                 <span className="animate-pulse animation-delay-400">●</span>
               </div>
             </div>
          )}
        </div>
        
        <div className="p-4 border-t border-zinc-800 bg-[#0A0A0A]">
          <div className="max-w-3xl mx-auto relative">
            <input 
              type="text" 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Send a message to PAT..."
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg pl-4 pr-12 py-3 text-sm focus:outline-none focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500"
            />
            <button 
              onClick={handleSend}
              disabled={chatMutation.isPending || !input.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800 disabled:opacity-50"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Right Sidebar - Context Panel */}
      <div className="w-72 border-l border-zinc-800 hidden xl:block bg-[#0A0A0A] p-5 overflow-y-auto">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-4">Runtime Context</h3>
        
        <div className="space-y-6">
          <div>
            <div className="text-xs text-zinc-500 mb-1">Agent Profile</div>
            <div className="text-sm font-medium text-zinc-200">Research Agent</div>
          </div>
          
          <div>
            <div className="text-xs text-zinc-500 mb-1">Model</div>
            <div className="text-sm font-medium text-zinc-200 bg-zinc-900 px-2 py-1 rounded inline-block border border-zinc-800">GPT-4.1-mini</div>
          </div>
          
          <div>
            <div className="text-xs text-zinc-500 mb-1">Temperature</div>
            <div className="text-sm font-medium text-zinc-200">0.7</div>
          </div>
          
          <div>
            <div className="text-xs text-zinc-500 mb-2">Enabled Tools</div>
            <div className="flex flex-col gap-1.5">
              {['read_file', 'search_web', 'calculator'].map(tool => (
                <div key={tool} className="text-xs text-zinc-300 flex items-center gap-2">
                   <div className="w-1 h-1 rounded-full bg-zinc-600"></div>
                   {tool}
                </div>
              ))}
            </div>
          </div>

          {conversationId && (
            <div className="pt-4 border-t border-zinc-800">
              <div className="text-xs text-zinc-500 mb-1">Conversation ID</div>
              <div className="text-xs font-mono text-zinc-400 truncate" title={conversationId}>{conversationId}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
