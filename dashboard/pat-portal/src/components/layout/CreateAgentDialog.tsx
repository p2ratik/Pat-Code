'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bot, Loader2, X } from 'lucide-react';
import { useUIStore } from '@/lib/store/useUIStore';
import { profilesApi } from '@/lib/api/profiles';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

export function CreateAgentDialog() {
  const { isCreateAgentOpen, setCreateAgentOpen } = useUIStore();
  const [name, setName] = useState('');
  const queryClient = useQueryClient();
  const router = useRouter();

  const createMutation = useMutation({
    mutationFn: (data: { name: string }) => profilesApi.createProfile({
      name: data.name,
      model_name: 'gpt-4o-mini', // default for now
      temperature: 0.7,
      max_turns: 10,
    }),
    onSuccess: (newAgent) => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      setCreateAgentOpen(false);
      setName('');
      // Route to the new agent's canvas
      router.push(`/?agent=${newAgent.id}`);
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    createMutation.mutate({ name: name.trim() });
  };

  return (
    <AnimatePresence>
      {isCreateAgentOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            onClick={() => setCreateAgentOpen(false)}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -20 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-full max-w-md bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl overflow-hidden pointer-events-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
                <div className="flex items-center gap-2 text-zinc-100 font-medium">
                  <Bot size={18} className="text-emerald-500" />
                  Create New Agent
                </div>
                <button 
                  onClick={() => setCreateAgentOpen(false)}
                  className="text-zinc-500 hover:text-zinc-300 transition-colors p-1 rounded-md hover:bg-zinc-800"
                >
                  <X size={16} />
                </button>
              </div>
              
              <form onSubmit={handleSubmit} className="p-5">
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                      Agent Name
                    </label>
                    <input
                      type="text"
                      autoFocus
                      required
                      placeholder="e.g. Research Assistant"
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>
                </div>

                <div className="mt-6 flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setCreateAgentOpen(false)}
                    className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending || !name.trim()}
                    className="flex items-center gap-2 px-4 py-2 bg-zinc-100 hover:bg-white text-zinc-900 text-sm font-medium rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {createMutation.isPending && <Loader2 size={14} className="animate-spin" />}
                    Create Agent
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
