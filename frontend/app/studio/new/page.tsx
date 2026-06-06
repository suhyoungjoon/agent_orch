import AppHeader from "@/components/AppHeader";
import AgentStudio from "@/components/AgentStudio";

export const metadata = { title: "새 에이전트 — 스튜디오" };

export default function StudioNewPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <AppHeader />
      <div className="flex-1 flex flex-col">
        <AgentStudio />
      </div>
    </div>
  );
}
