import { CommandPalette } from "@/components/layout/CommandPalette";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { CreateAgentDialog } from "@/components/layout/CreateAgentDialog";
import { IntegrationsModal } from "@/components/layout/IntegrationsModal";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen overflow-hidden bg-[#0A0A0A] text-zinc-100">
      <Sidebar />
      <div className="flex-1 flex flex-col ml-[260px]">
        <Topbar />
        <main className="flex-1 overflow-y-auto bg-[#0A0A0A] relative">
          {children}
        </main>
      </div>
      <CommandPalette />
      <CreateAgentDialog />
      <IntegrationsModal />
    </div>
  );
}
