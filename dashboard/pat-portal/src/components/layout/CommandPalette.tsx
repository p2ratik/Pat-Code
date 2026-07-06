"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Bot, MessageSquare, Search, Settings, Wrench } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  const commands = [
    {
      id: "create-agent",
      name: "Create Agent",
      icon: Bot,
      href: "/profiles/new",
    },
    {
      id: "open-chat",
      name: "Open Terminal Chat",
      icon: MessageSquare,
      href: "/chat",
    },
    {
      id: "configure-tools",
      name: "Configure Tools",
      icon: Wrench,
      href: "/tools",
    },
    { id: "settings", name: "Settings", icon: Settings, href: "/settings" },
  ];

  const filteredCommands = commands.filter((cmd) =>
    cmd.name.toLowerCase().includes(query.toLowerCase()),
  );

  const handleSelect = (cmdId: string, href: string) => {
    setIsOpen(false);
    setQuery('');
    
    if (cmdId === 'create-agent') {
      import('@/lib/store/useUIStore').then(m => m.useUIStore.getState().setCreateAgentOpen(true));
      return;
    }
    
    router.push(href);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            onClick={() => setIsOpen(false)}
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
                  placeholder="Type a command or search..."
                  className="flex-1 bg-transparent border-none outline-none text-zinc-100 placeholder:text-zinc-500 text-lg"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <div className="text-xs text-zinc-500 border border-zinc-700 bg-zinc-800 px-1.5 py-0.5 rounded">
                  ESC
                </div>
              </div>

              <div className="max-h-[300px] overflow-y-auto p-2">
                {filteredCommands.length > 0 ? (
                  filteredCommands.map((cmd) => (
                    <button
                      key={cmd.id}
                      onClick={() => handleSelect(cmd.id, cmd.href)}
                      className="w-full flex items-center px-3 py-3 hover:bg-zinc-800/50 rounded-lg text-zinc-300 transition-colors gap-3 text-left group focus:outline-none focus:bg-zinc-800"
                    >
                      <div className="w-8 h-8 rounded bg-zinc-800 flex items-center justify-center text-zinc-400 group-hover:text-zinc-200 group-focus:text-zinc-200">
                        <cmd.icon size={16} />
                      </div>
                      <span className="font-medium group-hover:text-white group-focus:text-white">
                        {cmd.name}
                      </span>
                    </button>
                  ))
                ) : (
                  <div className="p-4 text-center text-sm text-zinc-500">
                    No results found.
                  </div>
                )}
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
