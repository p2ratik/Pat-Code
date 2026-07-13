'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Wrench, Plug } from 'lucide-react';
import { useUIStore } from '@/lib/store/useUIStore';
import { useQuery } from '@tanstack/react-query';
import { integrationsApi } from '@/lib/api/integrations';
import clsx from 'clsx';

// Tools that require an OAuth provider connection.
const OAUTH_TOOLS: Record<string, string> = {
  google_sheets_read: 'google',
  google_sheets_write: 'google',
  google_sheets_append: 'google',
  google_drive_search: 'google',
  google_drive_read: 'google',
  gmail_search: 'google',
  gmail_read: 'google',
  google_calendar_list: 'google',
  google_calendar_create: 'google',
};

interface AddToolDialogProps {
  tools: any[];
  onAddTool: (tool: any) => void;
}

export function AddToolDialog({ tools, onAddTool }: AddToolDialogProps) {
  const { isAddToolOpen, setAddToolOpen, setIntegrationsOpen } = useUIStore();
  const [query, setQuery] = useState('');

  // Know which providers are currently connected so we can show auth badges.
  const { data: connections = [] } = useQuery({
    queryKey: ['connections'],
    queryFn: integrationsApi.getConnections,
    enabled: isAddToolOpen,
    staleTime: 30_000,
  });

  const isProviderConnected = (providerName: string) =>
    connections.some((c) => c.provider === providerName && c.status === 'connected');

  const filteredTools = tools.filter(tool =>
    tool.name.toLowerCase().includes(query.toLowerCase())
  );

  const handleSelect = (tool: any) => {
    onAddTool(tool);
    setAddToolOpen(false);
    setQuery('');

    // If this tool needs OAuth and the provider isn't connected yet,
    // immediately open the Integrations modal so the user can authorize.
    const requiredProvider = OAUTH_TOOLS[tool.name];
    if (requiredProvider && !isProviderConnected(requiredProvider)) {
      // Small delay so the AddToolDialog finishes closing first.
      setTimeout(() => setIntegrationsOpen(true), 200);
    }
  };

  return (
    <AnimatePresence>
      {isAddToolOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            onClick={() => setAddToolOpen(false)}
          />
          <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] pointer-events-none">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -20 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-full max-w-xl bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl overflow-hidden pointer-events-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center px-4 py-3 border-b border-zinc-800">
                <Search className="text-zinc-500 mr-3" size={20} />
                <input
                  type="text"
                  autoFocus
                  placeholder="Search tools to add (e.g. Google Sheets, GitHub)..."
                  className="flex-1 bg-transparent border-none outline-none text-zinc-100 placeholder:text-zinc-500 text-lg"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <div className="text-xs text-zinc-500 border border-zinc-700 bg-zinc-800 px-1.5 py-0.5 rounded">
                  ESC
                </div>
              </div>

              <div className="max-h-[320px] overflow-y-auto p-2">
                {filteredTools.length > 0 ? (
                  filteredTools.map((tool) => {
                    const requiredProvider = OAUTH_TOOLS[tool.name];
                    const needsAuth = !!requiredProvider;
                    const alreadyConnected = needsAuth && isProviderConnected(requiredProvider);

                    return (
                      <button
                        key={tool.name}
                        onClick={() => handleSelect(tool)}
                        className="w-full flex items-center px-3 py-3 hover:bg-zinc-800/50 rounded-lg text-zinc-300 transition-colors gap-3 text-left group focus:outline-none focus:bg-zinc-800"
                      >
                        <div className="w-8 h-8 rounded bg-zinc-800 flex items-center justify-center text-zinc-400 group-hover:text-zinc-200 group-focus:text-zinc-200 overflow-hidden shrink-0">
                          {tool.icon ? (
                            <img src={tool.icon} alt={tool.name} className="w-5 h-5 object-contain" />
                          ) : (
                            <Wrench size={16} />
                          )}
                        </div>
                        <div className="flex flex-col flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium group-hover:text-white group-focus:text-white truncate">
                              {tool.name}
                            </span>
                            {/* OAuth badge */}
                            {needsAuth && (
                              <span
                                className={clsx(
                                  "flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-full shrink-0",
                                  alreadyConnected
                                    ? "bg-emerald-500/15 text-emerald-400"
                                    : "bg-amber-500/15 text-amber-400",
                                )}
                              >
                                <Plug size={9} />
                                {alreadyConnected ? 'Connected' : 'Needs auth'}
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-zinc-500 line-clamp-1">
                            {tool.description || 'No description available'}
                          </span>
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <div className="p-4 text-center text-sm text-zinc-500">
                    No tools found matching "{query}".
                  </div>
                )}
              </div>

              {/* Hint footer */}
              <div className="px-4 py-2.5 border-t border-zinc-800 flex items-center gap-2 text-xs text-zinc-600">
                <Plug size={11} />
                Tools marked <span className="text-amber-400 font-medium mx-0.5">Needs auth</span>
                will prompt you to connect your Google account after adding.
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
