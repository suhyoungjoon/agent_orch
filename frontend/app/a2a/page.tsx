"use client";
import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import AppHeader from "@/components/AppHeader";
import { api, A2AChain } from "@/lib/api";

const DEPTH_COLORS = ["bg-blue-100", "bg-purple-100", "bg-green-100", "bg-yellow-100", "bg-red-100"];

const STATUS_DOT: Record<string, string> = {
  pending:   "bg-gray-400",
  active:    "bg-blue-500 animate-pulse",
  completed: "bg-green-500",
  failed:    "bg-red-500",
};

export default function A2APage() {
  const { data: session } = useSession();
  const token = (session as { accessToken?: string } | null)?.accessToken;

  const [chains, setChains] = useState<A2AChain[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.getA2AChains({}, token);
      setChains(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (token !== undefined) load(); }, [token]);

  // root_run_id 기준으로 그룹화
  const grouped = chains.reduce<Record<string, A2AChain[]>>((acc, c) => {
    (acc[c.root_run_id] ??= []).push(c);
    return acc;
  }, {});

  const stats = {
    total: chains.length,
    active: chains.filter(c => c.status === "active").length,
    maxDepth: chains.reduce((m, c) => Math.max(m, c.depth), 0),
    failed: chains.filter(c => c.status === "failed").length,
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <AppHeader />
      <main className="max-w-7xl mx-auto p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">에이전트 간 통신 (A2A)</h1>
            <p className="text-sm text-gray-500 mt-1">위임 토큰 · 호출 체인 추적 · 권한 전파</p>
          </div>
          <button onClick={load} className="px-4 py-2 bg-gray-800 text-white rounded-lg text-sm hover:bg-gray-700">
            새로고침
          </button>
        </div>

        {/* 통계 */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: "전체 체인", value: stats.total, color: "text-gray-800" },
            { label: "활성", value: stats.active, color: "text-blue-600" },
            { label: "최대 깊이", value: `${stats.maxDepth}단계`, color: "text-purple-600" },
            { label: "실패", value: stats.failed, color: "text-red-600" },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-white rounded-xl p-4 shadow-sm text-center">
              <p className="text-xs text-gray-500">{label}</p>
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
            </div>
          ))}
        </div>

        {/* 정책 안내 */}
        <div className="bg-purple-50 border border-purple-200 rounded-xl p-4">
          <p className="text-sm font-medium text-purple-900">A2A 위임 정책</p>
          <div className="flex gap-6 mt-2 text-xs text-purple-700">
            <span>• 최대 체인 깊이: 5단계</span>
            <span>• 위임 스코프: caller 권한의 부분집합만</span>
            <span>• 모든 hop 감사 추적</span>
            <span>• 만료 토큰 자동 거부</span>
          </div>
        </div>

        {loading ? (
          <p className="text-center text-gray-400 py-10">로딩 중…</p>
        ) : Object.keys(grouped).length === 0 ? (
          <div className="bg-white rounded-xl p-10 text-center text-gray-400">
            <p className="text-4xl mb-2">🔗</p>
            <p>A2A 호출 기록이 없습니다.</p>
            <p className="text-sm mt-1">POST /api/v1/a2a/chains 로 에이전트 간 통신을 등록하세요.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {Object.entries(grouped).map(([rootRunId, rootChains]) => (
              <div key={rootRunId} className="bg-white rounded-xl shadow-sm overflow-hidden">
                <button
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
                  onClick={() => setSelected(selected === rootRunId ? null : rootRunId)}
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                      {rootRunId.slice(0, 12)}…
                    </span>
                    <span className="text-sm font-medium">
                      {rootChains.length}홉 체인
                    </span>
                    <span className="text-xs text-gray-400">
                      최대 깊이 {Math.max(...rootChains.map(c => c.depth))}단계
                    </span>
                  </div>
                  <span className="text-gray-400">{selected === rootRunId ? "▲" : "▼"}</span>
                </button>

                {selected === rootRunId && (
                  <div className="border-t px-4 py-3 space-y-2">
                    {rootChains
                      .sort((a, b) => a.depth - b.depth)
                      .map((chain) => (
                        <div
                          key={chain.id}
                          className={`flex items-start gap-3 p-3 rounded-lg ${DEPTH_COLORS[chain.depth % DEPTH_COLORS.length]}`}
                          style={{ marginLeft: `${chain.depth * 24}px` }}
                        >
                          {chain.depth > 0 && (
                            <span className="text-gray-400 mt-0.5 shrink-0">└─</span>
                          )}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className={`w-2 h-2 rounded-full shrink-0 ${STATUS_DOT[chain.status]}`} />
                              <span className="text-xs font-mono bg-white/60 px-1 rounded">
                                {chain.caller_agent_id.slice(-8)}
                              </span>
                              <span className="text-xs text-gray-400">→</span>
                              <span className="text-xs font-mono bg-white/60 px-1 rounded">
                                {chain.callee_agent_id.slice(-8)}
                              </span>
                              <span className="text-xs text-gray-500">깊이 {chain.depth}</span>
                              <span className="text-xs text-gray-400">{chain.status}</span>
                            </div>
                            {chain.delegated_scopes && chain.delegated_scopes.length > 0 && (
                              <div className="flex gap-1 mt-1 flex-wrap">
                                {chain.delegated_scopes.map(s => (
                                  <span key={s} className="text-xs bg-white/70 px-1.5 py-0.5 rounded font-mono">{s}</span>
                                ))}
                              </div>
                            )}
                            {chain.input_summary && (
                              <p className="text-xs text-gray-600 mt-1 truncate">입력: {chain.input_summary}</p>
                            )}
                          </div>
                          <span className="text-xs text-gray-400 shrink-0">
                            {chain.started_at ? new Date(chain.started_at).toLocaleTimeString("ko-KR") : "—"}
                          </span>
                        </div>
                      ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
