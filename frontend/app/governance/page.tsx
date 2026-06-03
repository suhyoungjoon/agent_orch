"use client";
import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import AppHeader from "@/components/AppHeader";
import { api, AuditLog, AuditSummary } from "@/lib/api";

const RISK_COLOR: Record<string, string> = {
  low: "bg-gray-100 text-gray-700",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-orange-100 text-orange-800",
  critical: "bg-red-100 text-red-800",
};

const OUTCOME_COLOR: Record<string, string> = {
  success: "text-green-600",
  failure: "text-red-500",
  blocked: "text-orange-500",
};

export default function GovernancePage() {
  const { data: session } = useSession();
  const token = (session as { accessToken?: string } | null)?.accessToken;

  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [euOnly, setEuOnly] = useState(false);
  const [riskFilter, setRiskFilter] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [l, s] = await Promise.all([
        api.getAuditLogs({ eu_only: euOnly, risk_level: riskFilter || undefined, limit: 100 }, token),
        api.getAuditSummary(undefined, token),
      ]);
      setLogs(l);
      setSummary(s);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (token !== undefined) load(); }, [token, euOnly, riskFilter]);

  return (
    <div className="min-h-screen bg-gray-50">
      <AppHeader />
      <main className="max-w-7xl mx-auto p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">거버넌스 · 감사 추적</h1>
            <p className="text-sm text-gray-500 mt-1">EU AI Act 고위험 행동 추적 · 불변 감사 로그</p>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${
            summary?.compliance_status === "준수" ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
          }`}>
            {summary?.compliance_status ?? "로딩 중…"}
          </span>
        </div>

        {/* 요약 카드 */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[
              { label: "전체 로그", value: summary.total, color: "text-gray-800" },
              { label: "Low", value: summary.by_risk_level.low, color: "text-gray-600" },
              { label: "Medium", value: summary.by_risk_level.medium, color: "text-yellow-700" },
              { label: "High", value: summary.by_risk_level.high, color: "text-orange-700" },
              { label: "Critical", value: summary.by_risk_level.critical, color: "text-red-700" },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-white rounded-xl p-4 shadow-sm text-center">
                <p className="text-xs text-gray-500">{label}</p>
                <p className={`text-2xl font-bold ${color}`}>{value}</p>
              </div>
            ))}
          </div>
        )}

        {/* EU AI Act 배너 */}
        {summary && summary.eu_ai_act_relevant > 0 && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-center gap-3">
            <span className="text-2xl">🇪🇺</span>
            <div>
              <p className="font-medium text-blue-900">EU AI Act 관련 이벤트 {summary.eu_ai_act_relevant}건</p>
              <p className="text-sm text-blue-700">2026년 8월 2일 고위험 의무 조항 발효 예정. 이 이벤트들은 감사 의무 대상입니다.</p>
            </div>
          </div>
        )}

        {/* 필터 */}
        <div className="flex gap-3 flex-wrap">
          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="px-3 py-2 border rounded-lg text-sm bg-white"
          >
            <option value="">전체 위험 수준</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={euOnly} onChange={(e) => setEuOnly(e.target.checked)} className="w-4 h-4" />
            <span className="text-sm">EU AI Act 관련만</span>
          </label>
          <button onClick={load} className="ml-auto px-4 py-2 bg-gray-800 text-white rounded-lg text-sm hover:bg-gray-700">
            새로고침
          </button>
        </div>

        {/* 감사 로그 테이블 */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                {["시각", "행위자", "액션", "리소스", "결과", "위험", "EU"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">로딩 중…</td></tr>
              ) : logs.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">감사 로그가 없습니다.</td></tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleString("ko-KR")}
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-medium">{log.actor_name ?? log.actor_id ?? "—"}</span>
                      <span className="text-gray-400 ml-1">({log.actor_type})</span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs bg-gray-50 rounded">{log.action}</td>
                    <td className="px-4 py-3 text-gray-600">{log.resource_name ?? log.resource_id ?? "—"}</td>
                    <td className={`px-4 py-3 font-medium ${OUTCOME_COLOR[log.outcome] ?? ""}`}>{log.outcome}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${RISK_COLOR[log.risk_level]}`}>
                        {log.risk_level}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">{log.eu_ai_act_relevant ? "🇪🇺" : ""}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
