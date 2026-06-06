import AppHeader from "@/components/AppHeader";
import StudioListPage from "@/components/StudioListPage";

export const metadata = { title: "에이전트 스튜디오 — AgentFlow" };

export default function StudioPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <AppHeader />
      <main className="mx-auto max-w-5xl px-6 py-8">
        <StudioListPage />
      </main>
    </div>
  );
}
