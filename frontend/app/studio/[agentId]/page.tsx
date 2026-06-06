import AppHeader from "@/components/AppHeader";
import AgentStudio from "@/components/AgentStudio";

export const metadata = { title: "에이전트 편집 — 스튜디오" };

export default function StudioEditPage({ params }: { params: { agentId: string } }) {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <AppHeader />
      <div className="flex-1 flex flex-col">
        <AgentStudio agentId={params.agentId} />
      </div>
    </div>
  );
}
