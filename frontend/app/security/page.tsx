"use client";
import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import AppHeader from "@/components/AppHeader";
import { api, AnomalyEvent, SprawlReport } from "@/lib/api";

const SEV_COLOR: Record<string, string> = {
  critical: "bg-red-100 text-red-800 border-red-200",
  high:     "bg-orange-100 text-orange-800 border-orange-200",
  medium:   "bg-yellow-100 text-yellow-800 border-yellow-200",
  low:      "bg-gray-100 text-gray-700 border-gray-200",
};

const STATUS_COLOR: Record<string, string> = {
  open:          "bg-red-50 text-red-700",
  acknowledged:  "bg-yellow-50 text-yellow-700",
  resolved:      "bg-green-50 text-green-700",
  false_positive:"bg-gray-50 text-gray-500",
};

const ANOMALY_LABELS: Record<string, string> = {
  token_spike:       "토큰 급증",
  behavior_drift:    "행동 변화",
  policy_violation:  "정책 위반",
  unusual_tool:      "비정상 도구",
  rate_abuse:        "과도한 실행",
};

export default function SecurityPage() {
  const { data: session } = useSession();
  const token = (session as any)?.accessToken;

  const [anomalies, setAnomalies] = useState<AnomalyEvent[]>([]);
  const [sprawl, setSprawl] = useState<SprawlReport | null>(null);
  const [statusFilter, setStatusFilter] = useState("open");
  const [tab, setTab] = useState<"anomaly" | "sprawl" | "credentials">("anomaly");
  const [selected, setSelected] = useState<AnomalyEvent | null>(null);
  const [resolveNote, setResolveNote] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [a, s] = await Promise.all([
        api.getAnomalies({ status: statusFilter || undefined }, token),
        api.getSprawl(undefined, token),
      ]);
      setAnomalies(a);
      setSprawl(s);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (token !== undefined) load(); }, [token, statusFilter]);

  const handleResolve = async (status: string) => {
    if (!selected) return;
    try {
      await api.resolveAnomaly(selected.id, status, resolveNote || undefined, token);
      setSelected(null);
      setResolveNote("");
      load();
    } catch (e) { console.error(e); }
  };

  const criticalOpen = anomalies.filter(a => a.severity === "critical" && a.status === "open").length;
  const highOpen = anomalies.filter(a => a.severity === "high" && a.status === "open").length;

  return (
    <div className="min-h-screen bg-gray-50">
      <AppHeader />
      <main className="max-w-7xl mx-auto p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">보안 · 이상 행동 감지</h1>
            <p className="text-sm text-gray-500 mt-1">에이전트 신원 관리 · 이상 행동 탐지 · 섀도우 AI 스프롤</p>
          </div>
          <div className="flex gap-2">
            {criticalOpen > 0 && (
              <span className="px-3 py-1 bg-red-100 text-red-800 rounded-full text-sm font-bold animate-pulse">
                🚨 Critical {criticalOpen}건
              </span>
            )}
            {highOpen > 0 && (
              <span className="px-3 py-1 bg-orange-100 text-orange-800 rounded-full text-sm font-medium">
                ⚠️ High {highOpen}건
              </span>
            )}
          </div>
        </div>

        {/* 탭 */}
        <div className="flex border-b border-gray-200">
          {[
            { id: "anomaly", label: `이상 감지 (${anomalies.length})` },
            { id: "sprawl", label: `스프롤 현황 (${sprawl?.summary.total_risk ?? 0})` },
            { id: "credentials", label: "에이전트 신원" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id as any)}
              className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                tab === t.id ? "border-gray-900 text-gray-900" : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* 이상 행동 탭 */}
        {tab === "anomaly" && (
          <div className="space-y-4">
            <div className="flex gap-3">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2 border rounded-lg text-sm bg-white"
              >
                <option value="">전체 상태</option>
                <option value="open">Open</option>
                <option value="acknowledged">Acknowledged</option>
                <option value="resolved">Resolved</option>
                <option value="false_positive">False Positive</option>
              </select>
              <button onClick={load} className="ml-auto px-4 py-2 bg-gray-800 text-white rounded-lg text-sm">새로고침</button>
            </div>

            {loading ? (
              <p className="text-center text-gray-400 py-10">로딩 중…</p>
            ) : anomalies.length === 0 ? (
              <div className="bg-white rounded-xl p-10 text-center text-gray-400">
                <p className="text-4xl mb-2">✅</p>
                <p>이상 행동이 감지되지 않았습니다.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {anomalies.map((evt) => (
                  <div
                    key={evt.id}
                    className={`bg-white rounded-xl p-4 shadow-sm border ${SEV_COLOR[evt.severity]} cursor-pointer hover:shadow-md transition-shadow`}
                    onClick={() => setSelected(evt)}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${SEV_COLOR[evt.severity]}`}>
                            {evt.severity}
                          </span>
                          <span className="font-medium text-sm">{ANOMALY_LABELS[evt.anomaly_type] ?? evt.anomaly_type}</span>
                          <span className={`px-2 py-0.5 rounded text-xs ${STATUS_COLOR[evt.status]}`}>{evt.status}</span>
                        </div>
                        <p className="text-sm text-gray-700 mt-1">{evt.description}</p>
                        {evt.claude_analysis && (
                          <p className="text-xs text-gray-500 mt-1 italic">💡 {evt.claude_analysis}</p>
                        )}
                      </div>
                      <div className="text-right text-xs text-gray-400 shrink-0">
                        <p>위험 점수: {(evt.score * 100).toFixed(0)}%</p>
                        <p>{new Date(evt.detected_at).toLocaleString("ko-KR")}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 스프롤 탭 */}
        {tab === "sprawl" && sprawl && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: "섀도우 AI (팀 없음)", count: sprawl.summary.shadow_count, color: "bg-red-50 text-red-700", icon: "👻" },
                { label: "방치 에이전트 (30일+)", count: sprawl.summary.stale_count, color: "bg-yellow-50 text-yellow-700", icon: "💤" },
                { label: "고위험 에이전트", count: sprawl.summary.risky_count, color: "bg-orange-50 text-orange-700", icon: "⚠️" },
              ].map(({ label, count, color, icon }) => (
                <div key={label} className={`rounded-xl p-4 ${color} text-center`}>
                  <p className="text-3xl">{icon}</p>
                  <p className="text-2xl font-bold mt-1">{count}</p>
                  <p className="text-sm font-medium">{label}</p>
                </div>
              ))}
            </div>

            {sprawl.shadow_agents.length > 0 && (
              <div className="bg-white rounded-xl p-4 shadow-sm">
                <h3 className="font-semibold mb-3 text-red-700">👻 섀도우 AI — 팀 미배정 에이전트</h3>
                <div className="space-y-2">
                  {sprawl.shadow_agents.map((a) => (
                    <div key={a.id} className="flex items-center justify-between p-2 bg-red-50 rounded-lg">
                      <span className="font-medium text-sm">{a.name}</span>
                      <div className="flex gap-3 text-xs text-gray-500">
                        <span>{a.role}</span>
                        <span>실행 {a.usage_count}회</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {sprawl.risky_agents.length > 0 && (
              <div className="bg-white rounded-xl p-4 shadow-sm">
                <h3 className="font-semibold mb-3 text-orange-700">⚠️ 고위험 에이전트 — 성공률 50% 미만</h3>
                <div className="space-y-2">
                  {sprawl.risky_agents.map((a) => (
                    <div key={a.id} className="flex items-center justify-between p-2 bg-orange-50 rounded-lg">
                      <span className="font-medium text-sm">{a.name}</span>
                      <div className="flex gap-3 text-xs">
                        <span className="text-red-600 font-bold">성공률 {(a.success_rate * 100).toFixed(0)}%</span>
                        <span className="text-gray-500">실행 {a.usage_count}회</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 에이전트 신원 탭 */}
        {tab === "credentials" && (
          <div className="bg-white rounded-xl p-6 shadow-sm text-center text-gray-400">
            <p className="text-4xl mb-3">🔑</p>
            <p className="font-medium text-gray-600">에이전트 자격증명 관리</p>
            <p className="text-sm mt-1">에이전트 목록에서 개별 에이전트를 선택한 후 자격증명을 발급하세요.</p>
            <p className="text-xs mt-2 font-mono bg-gray-50 p-2 rounded">
              POST /api/v1/agents/{"{"id{"}"}/credentials
            </p>
            <div className="mt-4 text-left max-w-sm mx-auto">
              <p className="text-sm font-medium text-gray-700 mb-2">사용 가능한 스코프</p>
              <div className="flex flex-wrap gap-2">
                {["run:execute","run:read","data:read","data:write","tool:web_search","tool:code_exec","a2a:delegate"].map(s => (
                  <span key={s} className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded font-mono">{s}</span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 이상 해결 모달 */}
        {selected && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelected(null)}>
            <div className="bg-white rounded-2xl p-6 max-w-lg w-full mx-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
              <h3 className="font-bold text-lg mb-1">이상 이벤트 처리</h3>
              <p className="text-sm text-gray-500 mb-4">{selected.description}</p>
              {selected.claude_analysis && (
                <div className="bg-blue-50 rounded-lg p-3 mb-4">
                  <p className="text-xs font-medium text-blue-700 mb-1">Claude 분석</p>
                  <p className="text-sm text-blue-800">{selected.claude_analysis}</p>
                  {selected.claude_recommendation && (
                    <p className="text-sm text-blue-700 mt-2 font-medium">→ {selected.claude_recommendation}</p>
                  )}
                </div>
              )}
              <textarea
                placeholder="해결 메모 (선택)"
                value={resolveNote}
                onChange={(e) => setResolveNote(e.target.value)}
                className="w-full border rounded-lg p-2 text-sm mb-4 h-20 resize-none"
              />
              <div className="flex gap-2">
                <button onClick={() => handleResolve("resolved")} className="flex-1 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700">
                  해결됨
                </button>
                <button onClick={() => handleResolve("false_positive")} className="flex-1 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm hover:bg-gray-300">
                  오탐
                </button>
                <button onClick={() => setSelected(null)} className="px-4 py-2 text-gray-500 text-sm hover:text-gray-700">
                  닫기
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
