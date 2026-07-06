import { Handle, Position } from "@xyflow/react";
import clsx from "clsx";
import { motion } from "framer-motion";
import { Wrench } from "lucide-react";

export const formatToolName = (name: string) => {
  const mapping: Record<string, string> = {
    read_file: "Read File",
    grep_search: "Search Files",
    grep: "Search Files",
    list_dir: "List Directory",
    glob_search: "Glob Search",
    glob: "Glob Search",
  };
  if (mapping[name]) return mapping[name];
  return name.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
};

export function ToolNode({ data }: { data: any }) {
  const statusColors = {
    connected: "bg-emerald-500",
    oauth_required: "bg-yellow-500",
    error: "bg-red-500",
    disabled: "bg-zinc-500",
  };

  const statusColor =
    statusColors[data.status as keyof typeof statusColors] || "bg-zinc-500";

  return (
    <motion.div
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.2 }}
      className={clsx(
        "bg-zinc-900/90 border rounded-xl p-3 shadow-lg backdrop-blur-sm w-[200px] flex items-center gap-3 relative transition-all duration-300",
        data.selected
          ? "border-emerald-500/50 shadow-[0_0_15px_rgba(16,185,129,0.3)] bg-zinc-800/90"
          : "border-zinc-800 hover:border-zinc-700"
      )}
    >
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />

      <div className="w-10 h-10 bg-zinc-800 rounded-lg flex items-center justify-center shrink-0">
        {data.icon ? (
          <img
            src={data.icon}
            alt={data.name}
            className="w-6 h-6 object-contain"
          />
        ) : (
          <Wrench size={18} className="text-zinc-400" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-zinc-200 truncate">
          {formatToolName(data.name)}
        </div>
        <div className="text-xs text-zinc-500 truncate flex items-center gap-1.5 mt-0.5">
          <div className={clsx("w-2 h-2 rounded-full", statusColor)} />
          <span className="capitalize">
            {data.status?.replace("_", " ") || "Unknown"}
          </span>
        </div>
      </div>
    </motion.div>
  );
}
