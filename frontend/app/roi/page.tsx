"use client";
import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import AppHeader from "@/components/AppHeader";
import { api, ROISnapshot } from "@/lib/api";

const PRIORITY_COLOR: Record<string, string> = {
  high:   "bg-red-50 border-red-200 text-red-800",
  medium: "bg-yellow-50 border-yellow-200 text-yellow-800",
  low:    "bg-gray-50 border-gray-200 text-gray-700",
};

export default function ROIPage() {
  const { data: session } = useSession();
  const token = (session as { accessToken?: string } | null)?.accessToken;

  const [snapshot, setSnapshot] = useState<ROISnapshot | null>(null);
  const [history, setHistory] = useState<ROISnapshot[]>([]);
  const [period, setPeriod] = useState(() => new Date().toISOString().slice(0, 7));
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async (forceRefresh = false) => {
    setLoading(true);
    try {
      const [snap, hist] = await Promise.all([
        api.getROI(undefined, period, forceRefresh, token),
        api.getROIHistory(undefined, 6, token),
      ]);
      setSnapshot(snap);
      setHistory(hist);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { if (token !== undefined) load(); }, [token, period]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await load(true);
  };

  const maxRuns = Math.max(...history.map(h => h.total_runs), 1);

  return (
    <div className="min-h-screen bg-gray-50">
      <AppHeader />
      <main className="max-w-7xl mx-auto p-6 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">ROI 측정 대시보드</h1>
            <p className="text-sm text-gray-500 mt-1">검증된 비용·효율·절감 지표 · Claude 인사이트</p>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="month"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="px-3 py-2 border rounded-lg text-sm bg-white"
            />
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="px-4 py-2 bg-gray-800 text-white rounded-lg text-sm hover:bg-gray-700 disabled:opacity-50"
            >
              {refreshing ? "계산 중…" : "재계산 (Claude)"}
            </button>
          </div>
        </div>

        {loading ? (
          <p className="text-center text-gray-400 py-20">데이터 집계 중…</p>
        ) : !snapshot || snapshot.total_runs === 0 ? (
          <div className="bg-white rounded-xl p-10 text-center text-gray-400">
            <p className="text-4xl mb-2">📊</p>
            <p>{period} 기간의 실행 데이터가 없습니다.</p>
          </div>
        ) : (
          <>
            {/* KPI 카드 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                {
                  label: "총 실행",
                  value: snapshot.total_runs,
                  sub: `성공 ${snapshot.successful_runs}건 · 실패 ${snapshot.failed_runs}건`,
                  color: "text-gray-800",
                },
                {
                  label: "성공률",
                  value: `${(snapshot.success_rate * 100).toFixed(1)}%`,
                  sub: "completed / total",
                  color: snapshot.success_rate >= 0.8 ? "text-green-700" : "text-orange-600",
                },
                {
                  label: "추정 비용",
                  value: `$${snapshot.estimated_cost_usd.toFixed(4)}`,
                  sub: `작업당 $${snapshot.cost_per_successful_task_usd?.toFixed(4) ?? "—"}`,
                  color: "text-blue-700",
                },
                {
                  label: "ROI 배수",
                  value: `${snapshot.roi_multiplier?.toFixed(1) ?? "—"}x`,
                  sub: `${snapshot.estimated_hours_saved.toFixed(1)}시간 절감 추정`,
                  color: (snapshot.roi_multiplier ?? 0) > 10 ? "text-green-700" : "text-gray-700",
                },
              ].map(({ label, value, sub, color }) => (
                <div key={label} className="bg-white rounded-xl p-5 shadow-sm">
                  <p className="text-xs text-gray-500">{label}</p>
                  <p className={`text-3xl font-bold mt-1 ${color}`}>{value}</p>
                  <p className="text-xs text-gray-400 mt-1">{sub}</p>
                </div>
              ))}
            </div>

            {/* Claude 인사이트 */}
            {snapshot.claude_insights && (
              <div className="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-xl p-5">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">✨</span>
                  <span className="font-semibold text-purple-900">Claude 인사이트</span>
                  <span className="text-xs bg-purple-100 text-purple-600 px-2 py-0.5 rounded-full">AI 분석</span>
                </div>
                <p className="text-sm text-gray-700">{snapshot.claude_insights}</p>
              </div>
            )}

            {/* Claude 권고 */}
            {snapshot.claude_recommendations.length > 0 && (
              <div className="space-y-2">
                <h3 className="font-semibold text-gray-800">개선 권고 사항</h3>
                {snapshot.claude_recommendations.map((rec, i) => (
                  <div key={i} className={`border rounded-xl p-3 ${PRIORITY_COLOR[rec.priority] ?? PRIORITY_COLOR.low}`}>
                    <span className="text-xs font-bold uppercase mr-2">{rec.priority}</span>
                    {rec.action}
                  </div>
                ))}
              </div>
            )}

            {/* 월별 추이 */}
            {history.length > 1 && (
              <div className="bg-white rounded-xl p-5 shadow-sm">
                <h3 className="font-semibold text-gray-800 mb-4">월별 실행 추이</h3>
                <div className="space-y-2">
                  {history.slice().reverse().map((h) => (
                    <div key={h.period} className="flex items-center gap-3">
                      <span className="text-xs text-gray-500 w-16 shrink-0">{h.period}</span>
                      <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
                        <div
                          className={`h-full rounded-full flex items-center px-2 text-xs font-medium text-white transition-all ${
                            h.period === period ? "bg-gray-800" : "bg-gray-400"
                          }`}
                          style={{ width: `${(h.total_runs / maxRuns) * 100}%`, minWidth: "2rem" }}
                        >
                          {h.total_runs}
                        </div>
                      </div>
                      <span className="text-xs text-gray-500 w-20 text-right">
                        ${h.estimated_cost_usd.toFixed(3)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TOP 에이전트 */}
            {snapshot.top_agents.length > 0 && (
              <div className="bg-white rounded-xl p-5 shadow-sm">
                <h3 className="font-semibold text-gray-800 mb-3">TOP 에이전트 (실행 횟수)</h3>
                <div className="space-y-2">
                  {snapshot.top_agents.map((a, i) => (
                    <div key={a.agent_id} className="flex items-center gap-3">
                      <span className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center text-xs font-bold text-gray-600">
                        {i + 1}
                      </span>
                      <span className="text-xs font-mono text-gray-500 truncate flex-1">{a.agent_id.slice(-12)}</span>
                      <span className="text-sm font-medium">{a.runs}회</span>
                      <span className={`text-sm ${a.success_rate >= 0.8 ? "text-green-600" : "text-orange-500"}`}>
                        {(a.success_rate * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 스프롤 경고 */}
            {snapshot.agent_sprawl_count > 0 && (
              <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
                <p className="font-medium text-orange-800">
                  ⚠️ 섀도우 AI 감지: {snapshot.agent_sprawl_count}개 에이전트가 팀에 배정되지 않았습니다.
                </p>
                <p className="text-sm text-orange-600 mt-1">
                  보안 페이지에서 스프롤 현황을 확인하고 에이전트를 팀에 배정하거나 삭제하세요.
                </p>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
