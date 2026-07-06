'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { profilesApi } from '@/lib/api/profiles';
import { toolsApi, Tool } from '@/lib/api/tools';
import { AgentCanvas } from '@/components/canvas/AgentCanvas';
import { ConfigurationPanel } from '@/components/canvas/ConfigurationPanel';
import { AddToolDialog } from '@/components/layout/AddToolDialog';
import { useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/lib/store/useAuthStore';
import { authApi } from '@/lib/api/auth';

export default function DashboardPage() {
  const searchParams = useSearchParams();
  const agentId = searchParams?.get('agent');
  const queryClient = useQueryClient();
  const { user } = useAuthStore();

  const { data: profiles, isLoading: profilesLoading } = useQuery({ 
    queryKey: ['profiles'], 
    queryFn: profilesApi.getProfiles 
  });
  
  const { data: allTools, isLoading: toolsLoading } = useQuery({ 
    queryKey: ['tools'], 
    queryFn: toolsApi.getTools 
  });

  // Determine active profile
  const activeProfile = agentId 
    ? profiles?.find(p => p.id === agentId)
    : profiles?.[0];

  const { data: attachedToolsData, isLoading: attachedToolsLoading } = useQuery({
    queryKey: ['profileTools', activeProfile?.id],
    queryFn: () => toolsApi.getProfileTools(activeProfile!.id),
    enabled: !!activeProfile?.id,
  });

  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [isConfigOpen, setIsConfigOpen] = useState(false);

  // Sync tools state
  const attachedTools = attachedToolsData || [];

  const handleNodeClick = (event: React.MouseEvent, node: any) => {
    setSelectedNode(node);
    setIsConfigOpen(true);
  };

  const assignToolsMutation = useMutation({
    mutationFn: (toolNames: string[]) => toolsApi.assignToolsToProfile(activeProfile!.id, toolNames),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profileTools', activeProfile?.id] });
    }
  });

  const assignProfileMutation = useMutation({
    mutationFn: () => authApi.assignProfile(user!.id, activeProfile!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['userProfile', user?.id] });
    }
  });

  const handleAddTool = (tool: Tool) => {
    if (!activeProfile) return;
    const currentToolNames = attachedTools.map(t => t.name);
    if (!currentToolNames.includes(tool.name)) {
      assignToolsMutation.mutate([...currentToolNames, tool.name]);
    }
  };

  const handleRemoveTool = (toolName: string) => {
    if (!activeProfile) return;
    const currentToolNames = attachedTools.map(t => t.name).filter(name => name !== toolName);
    assignToolsMutation.mutate(currentToolNames);
    if (selectedNode?.data?.name === toolName) {
      setIsConfigOpen(false);
      setSelectedNode(null);
    }
  };

  const handlePaneClick = () => {
    // setIsConfigOpen(false); 
  };

  if (profilesLoading || toolsLoading) {
    return (
      <div className="flex-1 h-full flex items-center justify-center bg-[#0A0A0A]">
        <div className="text-zinc-500 animate-pulse">Loading Workspace...</div>
      </div>
    );
  }

  if (!activeProfile) {
    return (
      <div className="flex-1 h-full flex flex-col items-center justify-center bg-[#0A0A0A] gap-4">
        <div className="text-zinc-400">No agents found. Create one to get started.</div>
        <button 
          onClick={() => {
            import('@/lib/store/useUIStore').then(m => m.useUIStore.getState().setCreateAgentOpen(true));
          }}
          className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-md text-sm font-medium transition-colors"
        >
          Create Agent
        </button>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full flex flex-col overflow-hidden bg-[#0A0A0A]">
      {/* Canvas Area */}
      <div className="flex-1 relative">
        <AgentCanvas 
          agent={activeProfile} 
          tools={attachedTools} 
          onNodeClick={handleNodeClick}
          onPaneClick={handlePaneClick}
        />
        
        {/* Slide-out Configuration Panel */}
        <ConfigurationPanel 
          isOpen={isConfigOpen} 
          onClose={() => setIsConfigOpen(false)} 
          selectedNode={selectedNode}
          onRemoveTool={handleRemoveTool}
          onSetActiveProfile={() => assignProfileMutation.mutate()}
          isAssigningProfile={assignProfileMutation.isPending}
        />
      </div>

      <AddToolDialog tools={allTools || []} onAddTool={handleAddTool} />
    </div>
  );
}


