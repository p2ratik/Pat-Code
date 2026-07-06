import {
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  type Edge,
  type Node,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import "@xyflow/react/dist/style.css";
import {
  Maximize,
  Plus,
  RotateCcw,
  Search,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { AgentNode } from "./AgentNode";
import { ToolNode } from "./ToolNode";

const nodeTypes = {
  agent: AgentNode,
  tool: ToolNode,
};

interface AgentCanvasProps {
  agent: any;
  tools: any[];
  onNodeClick?: (event: React.MouseEvent, node: Node) => void;
  onPaneClick?: () => void;
}

export function AgentCanvas({
  agent,
  tools,
  onNodeClick,
  onPaneClick,
}: AgentCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null);

  // Initialize nodes and edges when agent/tools change
  useEffect(() => {
    if (!agent) {
      setNodes([]);
      setEdges([]);
      return;
    }

    // Try to load persisted positions from localStorage
    const savedPositions = localStorage.getItem(`canvas_positions_${agent.id}`);
    const parsedPositions = savedPositions ? JSON.parse(savedPositions) : {};

    const initialNodes: Node[] = [
      {
        id: "agent",
        type: "agent",
        position: parsedPositions["agent"] || { x: 400, y: 100 },
        data: agent,
      },
    ];

    const initialEdges: Edge[] = [];

    // Layout tools in a semi-circle or grid if no saved positions
    tools.forEach((tool, index) => {
      const nodeId = `tool_${tool.name}`;

      let position = parsedPositions[nodeId];
      if (!position) {
        // Simple default layout: stack them below the agent
        const cols = 3;
        const col = index % cols;
        const row = Math.floor(index / cols);
        position = { x: 200 + col * 250, y: 350 + row * 150 };
      }

      initialNodes.push({
        id: nodeId,
        type: "tool",
        position,
        data: {
          name: tool.name,
          status: tool.status || "connected",
          selected: false,
        },
      });

      initialEdges.push({
        id: `edge_agent_${nodeId}`,
        source: "agent",
        target: nodeId,
        type: "default",
        animated: false,
        style: { stroke: "#3f3f46", strokeWidth: 2 },
      });
    });

    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [agent, tools]);

  // Persist positions when nodes change
  useEffect(() => {
    if (!agent || nodes.length === 0) return;

    // Throttle save to avoid too many writes
    const timeout = setTimeout(() => {
      const positions = nodes.reduce(
        (acc, node) => {
          acc[node.id] = node.position;
          return acc;
        },
        {} as Record<string, { x: number; y: number }>,
      );

      localStorage.setItem(
        `canvas_positions_${agent.id}`,
        JSON.stringify(positions),
      );
    }, 1000);

    return () => clearTimeout(timeout);
  }, [nodes, agent]);

  return (
    <div className="w-full h-full relative bg-[#0A0A0A]">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        onInit={setReactFlowInstance}
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        elementsSelectable={true}
        nodesDraggable={true}
        nodesConnectable={false} // Disable edge creation
        zoomOnScroll={true}
        panOnScroll={true}
        panOnDrag={true}
        proOptions={{ hideAttribution: true }}
        fitView
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={2}
          color="#27272a"
        />
      </ReactFlow>

      {/* Floating Toolbar */}
      <div className="absolute top-4 right-4 flex flex-col gap-2 z-10">
        <div className="bg-zinc-900/80 backdrop-blur border border-zinc-800 rounded-lg shadow-lg overflow-hidden flex flex-col">
          <button 
            className="p-2.5 text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors" 
            title="Add Tool"
            onClick={() => {
              import('@/lib/store/useUIStore').then(m => m.useUIStore.getState().setAddToolOpen(true));
            }}
          >
            <Plus size={18} />
          </button>
          <div className="h-px bg-zinc-800 w-full" />
          <button
            className="p-2.5 text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
            title="Search (Ctrl+K)"
          >
            <Search size={18} />
          </button>
          <div className="h-px bg-zinc-800 w-full" />
          <button
            className="p-2.5 text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
            title="Zoom In"
            onClick={() => reactFlowInstance?.zoomIn()}
          >
            <ZoomIn size={18} />
          </button>
          <button
            className="p-2.5 text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
            title="Zoom Out"
            onClick={() => reactFlowInstance?.zoomOut()}
          >
            <ZoomOut size={18} />
          </button>
          <button
            className="p-2.5 text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
            title="Fit Canvas"
            onClick={() =>
              reactFlowInstance?.fitView({ padding: 0.2, duration: 800 })
            }
          >
            <Maximize size={18} />
          </button>
          <div className="h-px bg-zinc-800 w-full" />
          <button
            className="p-2.5 text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
            title="Reset Layout"
            onClick={() => {
              if (agent) {
                localStorage.removeItem(`canvas_positions_${agent.id}`);
                // Simple reload for now, ideally would recalculate state
                window.location.reload();
              }
            }}
          >
            <RotateCcw size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
