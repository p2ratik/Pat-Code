import { Handle, Position } from "@xyflow/react";
import { motion } from "framer-motion";
import { Bot, HardDrive } from "lucide-react";
import clsx from "clsx";

export function AgentNode({ data }: { data: any }) {
  return (
    <motion.div
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.2 }}
      className={clsx(
        "bg-zinc-900 border-2 rounded-2xl p-4 shadow-xl w-[240px] flex flex-col items-center gap-3 relative transition-all duration-300",
        data.selected
          ? "border-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.4)]"
          : "border-emerald-500/50 shadow-emerald-900/20 hover:border-emerald-500/80"
      )}
    >
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
      <Handle type="target" position={Position.Top} className="!opacity-0" />

      <div className="w-12 h-12 bg-emerald-500/10 rounded-full flex items-center justify-center text-emerald-400 shrink-0">
        <Bot size={24} />
      </div>

      <div className="text-center w-full">
        <div className="text-white font-semibold truncate text-lg">
          {data.name || "Unknown Agent"}
        </div>
        <div className="text-zinc-400 text-xs mt-1 truncate">
          {data.model_name || "No Model"}
        </div>
      </div>

      <div className="w-full bg-zinc-800/50 rounded-lg p-2 flex items-center justify-between text-xs mt-2 border border-zinc-800">
        <div className="flex items-center gap-1.5 text-zinc-400">
          <HardDrive size={14} />
          <span>Memory</span>
        </div>
        <div className="text-emerald-400 font-medium">Active</div>
      </div>
    </motion.div>
  );
}
