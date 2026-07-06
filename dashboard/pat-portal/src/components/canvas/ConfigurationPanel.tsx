import { AnimatePresence, motion } from "framer-motion";
import { Activity, X, UserCheck, Loader2, Check, RefreshCcw, AlertTriangle, ShieldCheck, Clock } from "lucide-react";
import { formatToolName } from "./ToolNode";
import clsx from "clsx";

interface ConfigurationPanelProps {
  isOpen: boolean;
  onClose: () => void;
  selectedNode: any;
  onRemoveTool?: (toolName: string) => void;
  onSetActiveProfile?: () => void;
  isAssigningProfile?: boolean;
}

export function ConfigurationPanel({
  isOpen,
  onClose,
  selectedNode,
  onRemoveTool,
  onSetActiveProfile,
  isAssigningProfile
}: ConfigurationPanelProps) {
  
  const isTool = selectedNode?.type === "tool";
  const toolName = isTool ? formatToolName(selectedNode.data.name) : "";
  const toolIcon = isTool ? selectedNode.data.icon : null;
  const isConnected = isTool && selectedNode.data.status !== "error";

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ duration: 0.3, ease: "easeInOut" }}
          className="absolute top-0 right-0 h-full w-[360px] bg-zinc-900 border-l border-zinc-800 shadow-2xl z-20 flex flex-col"
        >
          {/* Header */}
          <div className="h-14 flex items-center justify-between px-5 border-b border-zinc-800 shrink-0">
            <h2 className="font-medium text-white truncate pr-4">
              {isTool ? "Integration" : (selectedNode?.data?.name || "Configuration")}
            </h2>
            <button
              onClick={onClose}
              className="text-zinc-400 hover:text-white transition-colors p-1"
            >
              <X size={18} />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto">
            {isTool && (
              <div className="flex flex-col h-full">
                {/* Tool Header Profile */}
                <div className="p-6 border-b border-zinc-800 flex flex-col items-center text-center">
                  <div className="w-16 h-16 bg-zinc-950 border border-zinc-800 rounded-2xl flex items-center justify-center mb-4 shadow-sm">
                    {toolIcon ? (
                      <img src={toolIcon} alt={toolName} className="w-8 h-8 object-contain" />
                    ) : (
                      <Activity size={24} className="text-zinc-400" />
                    )}
                  </div>
                  <h2 className="text-xl font-semibold text-white mb-1">{toolName}</h2>
                  <div className="flex items-center gap-1.5 text-sm mb-3">
                    <div className={clsx("w-2 h-2 rounded-full", isConnected ? "bg-emerald-500" : "bg-red-500")} />
                    <span className={isConnected ? "text-emerald-500" : "text-red-500"}>
                      {isConnected ? "Connected" : "Error"}
                    </span>
                  </div>
                  
                  {/* Mock Connected Account */}
                  <div className="text-xs text-zinc-400 bg-zinc-950 px-3 py-1.5 rounded-full border border-zinc-800">
                    Connected as <span className="text-zinc-200 font-medium">user@example.com</span>
                  </div>
                </div>

                <div className="p-5 space-y-6 flex-1">
                  {/* Permissions */}
                  <div className="space-y-3">
                    <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                      <ShieldCheck size={14} /> Permissions
                    </h3>
                    <div className="bg-zinc-950 rounded-lg border border-zinc-800 p-1">
                      {/* These would normally be dynamic based on the tool */}
                      <div className="px-3 py-2 text-sm text-zinc-300 flex items-start gap-2">
                        <Check size={16} className="text-emerald-500 mt-0.5 shrink-0" />
                        <span>Read resources and metadata</span>
                      </div>
                      <div className="px-3 py-2 text-sm text-zinc-300 flex items-start gap-2 border-t border-zinc-800/50">
                        <Check size={16} className="text-emerald-500 mt-0.5 shrink-0" />
                        <span>Create and modify contents</span>
                      </div>
                    </div>
                  </div>

                  {/* Recent Activity / Health */}
                  <div className="space-y-3">
                    <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                      <Clock size={14} /> Health
                    </h3>
                    <div className="bg-zinc-950 rounded-lg border border-zinc-800 divide-y divide-zinc-800 text-sm">
                      <div className="px-4 py-3 flex justify-between items-center">
                        <span className="text-zinc-400">Last Verified</span>
                        <span className="text-zinc-200 font-medium">2 min ago</span>
                      </div>
                      <div className="px-4 py-3 flex justify-between items-center">
                        <span className="text-zinc-400">Token Status</span>
                        <span className="text-emerald-500 font-medium bg-emerald-500/10 px-2 py-0.5 rounded">Valid</span>
                      </div>
                      <div className="px-4 py-3 flex justify-between items-center">
                        <span className="text-zinc-400">Expires</span>
                        <span className="text-zinc-200 font-medium">14 days</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Danger Zone */}
                <div className="p-5 border-t border-zinc-800 bg-zinc-950/50 mt-auto">
                  <h3 className="text-xs font-semibold text-red-500/80 uppercase tracking-wider flex items-center gap-2 mb-3">
                    <AlertTriangle size={14} /> Danger Zone
                  </h3>
                  <div className="space-y-2">
                    <button className="w-full text-left px-4 py-2.5 text-sm font-medium text-zinc-300 hover:bg-zinc-800 hover:text-white border border-zinc-800 hover:border-zinc-700 rounded-md transition-colors flex items-center justify-between group">
                      <span>Reconnect Account</span>
                      <RefreshCcw size={14} className="text-zinc-500 group-hover:text-zinc-300" />
                    </button>
                    <button 
                      onClick={() => onRemoveTool?.(selectedNode.data.name)}
                      className="w-full text-left px-4 py-2.5 text-sm font-medium text-red-400 hover:bg-red-500/10 hover:text-red-400 border border-red-900/30 hover:border-red-900/50 rounded-md transition-colors flex items-center justify-between group"
                    >
                      <span>Disconnect Tool</span>
                      <X size={16} className="text-red-500/50 group-hover:text-red-400" />
                    </button>
                  </div>
                </div>
              </div>
            )}

            {selectedNode?.type === "agent" && (
              <div className="p-5 space-y-4">
                <div className="text-sm text-zinc-400">
                  Manage this agent's global settings and assignment.
                </div>
                
                <div className="pt-4 border-t border-zinc-800">
                  <button
                    onClick={() => onSetActiveProfile?.()}
                    disabled={isAssigningProfile}
                    className="w-full flex justify-center items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white rounded-md text-sm font-medium transition-colors"
                  >
                    {isAssigningProfile ? <Loader2 size={16} className="animate-spin" /> : <UserCheck size={16} />}
                    Set as My Active Profile
                  </button>
                  <p className="text-xs text-zinc-500 mt-2 text-center">
                    This makes the agent active for terminal chat and execution.
                  </p>
                </div>
              </div>
            )}

            {!selectedNode && (
              <div className="p-5 text-sm text-zinc-400">
                Select a node to configure.
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
