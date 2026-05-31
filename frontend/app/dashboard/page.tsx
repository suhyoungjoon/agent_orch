import AppHeader from "@/components/AppHeader";
import TeamDashboard from "@/components/TeamDashboard";

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <AppHeader />
      <main className="mx-auto max-w-5xl px-6 py-8">
        <TeamDashboard />
      </main>
    </div>
  );
}
