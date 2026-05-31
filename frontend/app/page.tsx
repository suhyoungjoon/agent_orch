import AppHeader from "@/components/AppHeader";
import RunHistory from "@/components/RunHistory";
import ParseIntent from "@/components/ParseIntent";
import TeamRegistry from "@/components/TeamRegistry";
import ApprovalQueue from "@/components/ApprovalQueue";

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50">
      <AppHeader />

      <main className="mx-auto max-w-5xl px-6 py-8 space-y-10">
        <ApprovalQueue />
        <ParseIntent />
        <TeamRegistry />
        <RunHistory />
      </main>
    </div>
  );
}
