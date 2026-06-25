'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { mcpApi, MCPServer, MCPServerCreate } from '@/lib/api/mcp';
import {
  Plus, X, Loader2, Plug, PlugZap, Link2Off, ChevronDown, ChevronRight, RefreshCw, KeyRound,
} from 'lucide-react';
import clsx from 'clsx';

// ------------------------------------------------------------------
// Register server modal (admin)
// ------------------------------------------------------------------
function RegisterServerModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<MCPServerCreate>({
    name: '',
    display_name: '',
    server_url: '',
    transport: 'stdio',
    startup_timeout_sec: 30,
    supports_oauth: false,
    enabled: true,
  });

  const mutation = useMutation({
    mutationFn: () => mcpApi.registerServer(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mcpServers'] });
      onClose();
    },
  });

  const set = (k: keyof MCPServerCreate, v: unknown) => setForm(f => ({ ...f, [k]: v }));

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-lg p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-base font-semibold text-white">Register MCP Server</h2>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-200"><X size={18} /></button>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">Slug (name) *</label>
              <input value={form.name} onChange={e => set('name', e.target.value)}
                placeholder="github"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500 placeholder-zinc-600" />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">Display Name *</label>
              <input value={form.display_name} onChange={e => set('display_name', e.target.value)}
                placeholder="GitHub MCP"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500 placeholder-zinc-600" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Server URL / Command *</label>
            <input value={form.server_url} onChange={e => set('server_url', e.target.value)}
              placeholder="npx @modelcontextprotocol/server-github"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500 placeholder-zinc-600" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">Transport</label>
              <select value={form.transport} onChange={e => set('transport', e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500">
                <option value="stdio">stdio</option>
                <option value="sse">sse</option>
                <option value="http">http</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">Startup Timeout (s)</label>
              <input type="number" value={form.startup_timeout_sec ?? 30}
                onChange={e => set('startup_timeout_sec', e.target.value === '' ? 30 : Number(e.target.value))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500" />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <input type="checkbox" id="oauth" checked={!!form.supports_oauth}
              onChange={e => set('supports_oauth', e.target.checked)}
              className="rounded border-zinc-600 bg-zinc-800" />
            <label htmlFor="oauth" className="text-sm text-zinc-300">Supports OAuth</label>
          </div>
        </div>

        {mutation.isError && (
          <p className="mt-4 text-xs text-red-400">
            {(mutation.error as any)?.response?.data?.detail || 'Registration failed.'}
          </p>
        )}

        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200">Cancel</button>
          <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !form.name || !form.display_name || !form.server_url}
            className="flex items-center gap-2 px-4 py-2 bg-zinc-100 text-zinc-900 text-sm font-medium rounded-md hover:bg-white disabled:opacity-50">
            {mutation.isPending && <Loader2 size={14} className="animate-spin" />}
            Register
          </button>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------
// Server row — shows connection status + connect/disconnect + tools drawer
// ------------------------------------------------------------------
function ServerRow({ server, connection }: { server: MCPServer; connection: { status: string } | undefined }) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);

  const { data: tools, isFetching: loadingTools } = useQuery({
    queryKey: ['mcpTools', server.name],
    queryFn: () => mcpApi.getServerTools(server.name),
    enabled: expanded,
    staleTime: 30_000,
  });

  const connectMutation = useMutation({
    mutationFn: () => mcpApi.connect(server.name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mcpStatus'] }),
  });

  const disconnectMutation = useMutation({
    mutationFn: () => mcpApi.disconnect(server.name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mcpStatus'] }),
  });

  const discoverMutation = useMutation({
    mutationFn: () => mcpApi.discoverTools(server.name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mcpTools', server.name] });
      setExpanded(true);
    },
  });

  const oauthMutation = useMutation({
    mutationFn: () => mcpApi.startOAuth({
      server_name: server.name,
      frontend_redirect_url: window.location.origin + window.location.pathname,
    }),
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
    },
  });

  const status = connection?.status ?? 'not connected';
  const isConnected = status === 'connected';

  const statusColor: Record<string, string> = {
    connected: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20',
    disconnected: 'text-zinc-400 bg-zinc-800 border-zinc-700',
    error: 'text-red-400 bg-red-500/10 border-red-500/20',
    expired: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    disabled: 'text-zinc-500 bg-zinc-900 border-zinc-800',
    'not connected': 'text-zinc-600 bg-zinc-900 border-zinc-800',
  };

  return (
    <>
      <tr className="hover:bg-zinc-900/20 transition-colors">
        {/* Server info */}
        <td className="px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-zinc-900 border border-zinc-800 flex items-center justify-center">
              <Plug size={14} className="text-zinc-400" />
            </div>
            <div>
              <div className="text-sm font-medium text-zinc-200">{server.display_name}</div>
              <div className="text-xs text-zinc-500 font-mono">{server.name}</div>
            </div>
          </div>
        </td>

        {/* Transport */}
        <td className="px-6 py-4 text-xs font-mono text-zinc-400">{server.transport}</td>

        {/* Status */}
        <td className="px-6 py-4">
          <div className="flex items-center gap-2">
            <span className={clsx(
              'inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border',
              statusColor[status] ?? statusColor.disconnected
            )}>
              {status}
            </span>
            {server.supports_oauth && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border border-violet-500/30 bg-violet-500/10 text-violet-400">
                OAuth
              </span>
            )}
          </div>
        </td>

        {/* Actions */}
        <td className="px-6 py-4">
          <div className="flex items-center gap-2">
            {!isConnected ? (
              <button
                onClick={() => server.supports_oauth ? oauthMutation.mutate() : connectMutation.mutate()}
                disabled={connectMutation.isPending || oauthMutation.isPending}
                className="flex items-center gap-1.5 text-xs border border-zinc-700 text-zinc-300 hover:border-emerald-500 hover:text-emerald-400 px-2.5 py-1 rounded transition-colors disabled:opacity-50"
              >
                {connectMutation.isPending || oauthMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <PlugZap size={12} />}
                Connect
              </button>
            ) : (
              <button
                onClick={() => disconnectMutation.mutate()}
                disabled={disconnectMutation.isPending}
                className="flex items-center gap-1.5 text-xs border border-zinc-700 text-zinc-300 hover:border-red-500 hover:text-red-400 px-2.5 py-1 rounded transition-colors disabled:opacity-50"
              >
                {disconnectMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <Link2Off size={12} />}
                Disconnect
              </button>
            )}

            {/* OAuth token button — shown only for OAuth servers */}
            {server.supports_oauth && (
              <button
                onClick={() => oauthMutation.mutate()}
                disabled={oauthMutation.isPending}
                className="flex items-center gap-1.5 text-xs border border-violet-700 text-violet-400 hover:border-violet-400 hover:text-violet-300 px-2.5 py-1 rounded transition-colors ml-2"
                title="Authorize OAuth"
              >
                {oauthMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <KeyRound size={12} />}
                Authorize
              </button>
            )}

            {/* Sync Tools — hidden for OAuth servers: live discovery requires a valid token */}
            {!server.supports_oauth && (
              <button
                onClick={() => discoverMutation.mutate()}
                disabled={discoverMutation.isPending}
                className="flex items-center gap-1.5 text-xs border border-zinc-700 text-zinc-300 hover:border-blue-500 hover:text-blue-400 px-2.5 py-1 rounded transition-colors disabled:opacity-50 ml-2"
                title="Discover & Sync Tools"
              >
                {discoverMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                Sync Tools
              </button>
            )}

            {/* Toggle tool drawer */}
            <button
              onClick={() => setExpanded(e => !e)}
              className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300 px-2 py-1 rounded transition-colors ml-2"
            >
              {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              Tools
            </button>
          </div>
        </td>
      </tr>

      {/* Collapsible tool cache drawer */}
      {expanded && (
        <tr>
          <td colSpan={4} className="px-6 pb-4 bg-zinc-950/40">
            <div className="pt-3">
              <div className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
                Cached Tools ({tools?.length ?? 0})
              </div>

              {loadingTools && (
                <Loader2 size={14} className="animate-spin text-zinc-500" />
              )}

              {tools && tools.length === 0 && (
                <p className="text-xs text-zinc-600">
                  No tools synced yet. Click the <strong>Sync Tools</strong> button above to discover and cache tools from this server.
                </p>
              )}

              {tools && tools.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {tools.map(tool => (
                    <div key={tool.id} className="bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2">
                      <div className="text-xs font-medium text-zinc-200 font-mono">{tool.tool_name}</div>
                      {tool.description && (
                        <div className="text-xs text-zinc-500 mt-0.5 line-clamp-2">{tool.description}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ------------------------------------------------------------------
// Reads ?connected=1&server=X or ?error=... after the OAuth redirect.
// Must be a separate component because useSearchParams() requires Suspense.
// ------------------------------------------------------------------
function OAuthCallbackHandler({
  onMessage,
}: {
  onMessage: (msg: string | null) => void;
}) {
  const params = useSearchParams();
  const router = useRouter();
  const qc = useQueryClient();

  useEffect(() => {
    const connected = params.get('connected');
    const server = params.get('server');
    const error = params.get('error');

    if (connected && server) {
      onMessage(`✓ ${server} authorized and connected.`);
      // Force-refetch so the status chip updates immediately, not after next poll.
      qc.refetchQueries({ queryKey: ['mcpStatus'] });
      router.replace('/mcp');
    } else if (error) {
      onMessage(`OAuth failed: ${decodeURIComponent(error)}`);
      router.replace('/mcp');
    }
  }, [params, qc, router, onMessage]);

  return null;
}

// ------------------------------------------------------------------
// Page
// ------------------------------------------------------------------
export default function MCPPage() {
  const [showRegister, setShowRegister] = useState(false);
  const [oauthMessage, setOauthMessage] = useState<string | null>(null);

  const { data: servers, isLoading: loadingServers } = useQuery({
    queryKey: ['mcpServers'],
    queryFn: mcpApi.listServers,
  });

  const { data: connections } = useQuery({
    queryKey: ['mcpStatus'],
    queryFn: mcpApi.getStatus,
    refetchInterval: 30_000,
  });

  const connectionMap = Object.fromEntries(
    (connections ?? []).map(c => [c.server_name, c])
  );

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      {/* Suspense required by Next.js App Router for useSearchParams() */}
      <Suspense fallback={null}>
        <OAuthCallbackHandler onMessage={setOauthMessage} />
      </Suspense>

      {showRegister && <RegisterServerModal onClose={() => setShowRegister(false)} />}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">MCP Servers</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Connect your agent to external tools via the Model Context Protocol.
          </p>
        </div>
        <button
          onClick={() => setShowRegister(true)}
          className="flex items-center gap-2 bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 rounded-md text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Register Server
        </button>
      </div>

      {oauthMessage && (
        <div className={clsx(
          'flex items-center justify-between rounded-md px-4 py-3 text-sm border',
          oauthMessage.startsWith('✓')
            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
            : 'border-red-500/30 bg-red-500/10 text-red-300'
        )}>
          <span>{oauthMessage}</span>
          <button onClick={() => setOauthMessage(null)} className="text-zinc-500 hover:text-zinc-300 ml-4">
            <X size={14} />
          </button>
        </div>
      )}

      <div className="border border-zinc-800 rounded-xl overflow-hidden bg-[#0A0A0A]">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900/50 text-zinc-400 border-b border-zinc-800">
            <tr>
              <th className="px-6 py-4 font-medium">Server</th>
              <th className="px-6 py-4 font-medium">Transport</th>
              <th className="px-6 py-4 font-medium">Your Status</th>
              <th className="px-6 py-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {loadingServers && (
              <tr>
                <td colSpan={4} className="px-6 py-10 text-center">
                  <Loader2 size={20} className="animate-spin mx-auto text-zinc-500" />
                </td>
              </tr>
            )}
            {!loadingServers && servers?.length === 0 && (
              <tr>
                <td colSpan={4} className="px-6 py-10 text-center text-sm text-zinc-600">
                  No MCP servers registered yet.
                </td>
              </tr>
            )}
            {servers?.map(server => (
              <ServerRow
                key={server.id}
                server={server}
                connection={connectionMap[server.name]}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Status legend */}
      <div className="flex flex-wrap gap-4 text-xs text-zinc-500">
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500" />connected — active, agent will use this server</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-500" />expired — token needs refresh</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-500" />error — connection failed</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-zinc-600" />disconnected — manually disconnected</span>
      </div>
    </div>
  );
}
