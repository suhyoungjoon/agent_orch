import AppHeader from "@/components/AppHeader";
import EnterpriseReport from "@/components/EnterpriseReport";

export default function ReportPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <AppHeader />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <EnterpriseReport />
      </main>
    </div>
  );
}
