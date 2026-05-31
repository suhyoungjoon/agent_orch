"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import {
  api, EnterpriseReportData, TeamReportStat, AgentRankEntry,
  SynergyPair, ModelCostStat, DailyRunStat,
} from "@/lib/api";
import {
  Building2, Bot, Play, TrendingUp, Zap, DollarSign,
  GitMerge, RefreshCw, Loader2, Medal, ArrowRight,
} from "lucide-react";

// ── 포매터 ────────────────────────────────────────────────────────────────────
function fmt(n: number) { return n.toLocaleString("ko-KR"); }
function fmtCost(usd: number) {
  if (usd === 0) return "$0.00";
  if (usd < 0.000001) return "<$0.000001";
  if (usd < 0.01) return `$${usd.toFixed(6)}`;
  return `$${usd.toFixed(4)}`;
}
function fmtTok(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

const ROLE_COLOR: Record<string, string> = {
  researcher: "bg-blue-100 text-blue-700",
  writer:     "bg-purple-100 text-purple-700",
  analyst:    "bg-amber-100 text-amber-700",
  coder:      "bg-green-100 text-green-700",
};

// ── 개요 카드 ─────────────────────────────────────────────────────────────────
function OverviewCard({ icon: Icon, label, value, sub, color }: {
  icon: React.ElementType; label: string; value: string; sub?: string; color: string;
}) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 flex items-center gap-4">
      <div className={`rounded-xl p-2.5 ${color}`}><Icon size={20} /></div>
      <div className="min-w-0">
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-xl font-bold text-gray-900 leading-tight">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ── 성공률 바 ─────────────────────────────────────────────────────────────────
function RateBar({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div
          className={`h-full rounded-full ${pct >= 80 ? "bg-green-400" : pct >= 50 ? "bg-amber-400" : "bg-red-400"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-medium text-gray-600 w-8 text-right">{pct}%</span>
    </div>
  );
}

// ── 스파크라인 SVG ────────────────────────────────────────────────────────────
function Sparkline({ data, color = "#3b82f6" }: { data: number[]; color?: string }) {
  if (data.length < 2) return null;
  const max = Math.max(...data, 1);
  const W = 120; const H = 32;
  const pts = data
    .map((v, i) => `${(i / (data.length - 1)) * W},${H - (v / max) * (H - 4) - 2}`)
    .join(" ");
  return (
    <svg width={W} height={H} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

// ── 팀별 비교 ─────────────────────────────────────────────────────────────────
function TeamBreakdown({ teams }: { teams: TeamReportStat[] }) {
  const maxRuns = Math.max(...teams.map((t) => t.run_count), 1);
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-gray-800 mb-4 flex items-center gap-2">
        <Building2 size={15} className="text-gray-500" />팀별 비교
      </h2>
      {teams.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">팀 데이터가 없습니다.</p>
      ) : (
        <div className="space-y-3">
          {teams.map((t) => (
            <div key={t.team_id} className="grid grid-cols-[1fr_auto] gap-3 items-center">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-gray-800 truncate">{t.team_name}</span>
                  <div className="flex items-center gap-3 text-xs text-gray-500 shrink-0 ml-2">
                    <span>{t.agent_count}개 에이전트</span>
                    <span>{fmt(t.run_count)}회</span>
                  </div>
                </div>
                <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-400"
                    style={{ width: `${(t.run_count / maxRuns) * 100}%` }}
                  />
                </div>
              </div>
              <div className="text-right text-xs shrink-0 space-y-0.5">
                <div className="text-emerald-600 font-medium">{fmtCost(t.estimated_cost_usd)}</div>
                <div className={`font-medium ${t.success_rate >= 0.8 ? "text-green-600" : t.success_rate >= 0.5 ? "text-amber-600" : "text-red-500"}`}>
                  {(t.success_rate * 100).toFixed(0)}%
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 에이전트 성능 TOP 10 ──────────────────────────────────────────────────────
const MEDAL = ["🥇", "🥈", "🥉"];

function TopAgents({ agents }: { agents: AgentRankEntry[] }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-gray-800 mb-4 flex items-center gap-2">
        <Medal size={15} className="text-gray-500" />에이전트 성능 TOP {agents.length}
      </h2>
      {agents.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">데이터가 없습니다.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-100 text-gray-400">
                <th className="py-1.5 text-left font-medium w-6">#</th>
                <th className="py-1.5 text-left font-medium">에이전트</th>
                <th className="py-1.5 text-left font-medium">팀</th>
                <th className="py-1.5 text-right font-medium">실행</th>
                <th className="py-1.5 text-right font-medium min-w-[80px]">성공률</th>
                <th className="py-1.5 text-right font-medium">비용</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {agents.map((a, i) => (
                <tr key={a.agent_id} className="hover:bg-gray-50 transition-colors">
                  <td className="py-2 text-gray-400">{MEDAL[i] ?? i + 1}</td>
                  <td className="py-2">
                    <div className="flex items-center gap-1.5">
                      <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${ROLE_COLOR[a.role] ?? "bg-gray-100 text-gray-600"}`}>
                        {a.role}
                      </span>
                      <span className="font-medium text-gray-800 truncate max-w-[120px]">{a.name}</span>
                    </div>
                  </td>
                  <td className="py-2 text-gray-500 truncate max-w-[80px]">{a.team_name}</td>
                  <td className="py-2 text-right text-gray-600">{fmt(a.usage_count)}</td>
                  <td className="py-2"><RateBar rate={a.success_rate} /></td>
                  <td className="py-2 text-right text-emerald-600 font-medium">{fmtCost(a.estimated_cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── 시너지 페어링 ─────────────────────────────────────────────────────────────
function SynergyPairs({ pairs }: { pairs: SynergyPair[] }) {
  const maxCount = Math.max(...pairs.map((p) => p.workflow_count), 1);
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-gray-800 mb-1 flex items-center gap-2">
        <GitMerge size={15} className="text-gray-500" />시너지 페어링
      </h2>
      <p className="text-xs text-gray-400 mb-4">워크플로에서 함께 연결된 에이전트 쌍</p>
      {pairs.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">워크플로 데이터가 없습니다.</p>
      ) : (
        <div className="space-y-2.5">
          {pairs.map((p, i) => (
            <div key={i} className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${ROLE_COLOR[p.agent_a_role] ?? "bg-gray-100 text-gray-600"}`}>
                  {p.agent_a_name}
                </span>
                <ArrowRight size={11} className="text-gray-400 shrink-0" />
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${ROLE_COLOR[p.agent_b_role] ?? "bg-gray-100 text-gray-600"}`}>
                  {p.agent_b_name}
                </span>
                <span className="ml-auto text-xs text-gray-500 shrink-0">{p.workflow_count}개 워크플로</span>
              </div>
              <div className="h-1 rounded-full bg-gray-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-violet-400"
                  style={{ width: `${(p.workflow_count / maxCount) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 모델별 비용 분포 ──────────────────────────────────────────────────────────
function ModelCosts({ stats }: { stats: ModelCostStat[] }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-gray-800 mb-4 flex items-center gap-2">
        <Zap size={15} className="text-gray-500" />모델별 비용 분포
      </h2>
      {stats.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">실행 데이터가 없습니다.</p>
      ) : (
        <div className="space-y-2.5">
          {stats.map((m) => (
            <div key={m.model}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-gray-700 font-mono">{m.model}</span>
                <div className="flex items-center gap-3 text-xs text-gray-500 shrink-0">
                  <span>{fmt(m.run_count)}회</span>
                  <span className="text-emerald-600 font-medium">{fmtCost(m.estimated_cost_usd)}</span>
                  <span className="text-gray-400 w-8 text-right">{(m.cost_share * 100).toFixed(0)}%</span>
                </div>
              </div>
              <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-emerald-400"
                  style={{ width: `${m.cost_share * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 14일 실행 추이 ────────────────────────────────────────────────────────────
function DailyTrend({ stats }: { stats: DailyRunStat[] }) {
  const runData = stats.map((s) => s.run_count);
  const costData = stats.map((s) => s.estimated_cost_usd);
  const totalRuns = stats.reduce((s, d) => s + d.run_count, 0);
  const totalCost = stats.reduce((s, d) => s + d.estimated_cost_usd, 0);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
          <TrendingUp size={15} className="text-gray-500" />14일 실행 추이
        </h2>
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span>총 {fmt(totalRuns)}회</span>
          <span className="text-emerald-600">{fmtCost(totalCost)}</span>
        </div>
      </div>

      {/* 스파크라인 + 표 */}
      <div className="flex items-end gap-4 mb-4">
        <div>
          <p className="text-[10px] text-gray-400 mb-1">실행 수</p>
          <Sparkline data={runData} color="#3b82f6" />
        </div>
        <div>
          <p className="text-[10px] text-gray-400 mb-1">비용</p>
          <Sparkline data={costData} color="#10b981" />
        </div>
      </div>

      {/* 최근 7일 일별 표 */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-100 text-gray-400">
              <th className="py-1 text-left font-medium">날짜</th>
              <th className="py-1 text-right font-medium">실행</th>
              <th className="py-1 text-right font-medium">성공</th>
              <th className="py-1 text-right font-medium">토큰</th>
              <th className="py-1 text-right font-medium">비용</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {[...stats].reverse().slice(0, 7).map((d) => (
              <tr key={d.date} className="text-gray-600">
                <td className="py-1.5 font-mono">{d.date.slice(5)}</td>
                <td className="py-1.5 text-right">{d.run_count}</td>
                <td className="py-1.5 text-right text-green-600">{d.success_count}</td>
                <td className="py-1.5 text-right">{fmtTok(d.total_tokens)}</td>
                <td className="py-1.5 text-right text-emerald-600">{fmtCost(d.estimated_cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────────
export default function EnterpriseReport() {
  const { data: session } = useSession();
  const [data, setData] = useState<EnterpriseReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await api.getEnterpriseReport(session?.user?.accessToken);
      setData(d);
      setLastUpdated(new Date());
    } catch {
      // 인증 전이거나 권한 없음 — 무시
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-400">
        <Loader2 size={22} className="animate-spin mr-2" />
        <span className="text-sm">리포트 생성 중...</span>
      </div>
    );
  }
  if (!data) return null;

  const { overview } = data;

  return (
    <div className="space-y-8">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">전사 리포트</h1>
          <p className="text-sm text-gray-500 mt-0.5">전체 조직의 에이전트 운영 현황</p>
        </div>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-xs text-gray-400">
              {lastUpdated.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })} 기준
            </span>
          )}
          <button
            onClick={() => { setLoading(true); load(); }}
            className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
            title="새로고침"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* 전사 개요 카드 6개 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <OverviewCard icon={Building2} label="전체 팀"      value={fmt(overview.total_teams)}     color="bg-slate-50 text-slate-600" />
        <OverviewCard icon={Bot}       label="전체 에이전트" value={fmt(overview.total_agents)}    color="bg-blue-50 text-blue-600" />
        <OverviewCard icon={GitMerge}  label="워크플로"     value={fmt(overview.total_workflows)}  color="bg-violet-50 text-violet-600" />
        <OverviewCard icon={Play}      label="전체 실행"    value={fmt(overview.total_runs)}
          sub={`실행 중 ${overview.running_runs}건`}                                               color="bg-indigo-50 text-indigo-600" />
        <OverviewCard icon={TrendingUp} label="전체 성공률"
          value={`${(overview.success_rate * 100).toFixed(1)}%`}
          sub={`완료 ${fmt(overview.completed_runs)} / 실패 ${fmt(overview.failed_runs)}`}
          color={overview.success_rate >= 0.8 ? "bg-green-50 text-green-600" : overview.success_rate >= 0.5 ? "bg-amber-50 text-amber-600" : "bg-red-50 text-red-600"}
        />
        <OverviewCard icon={DollarSign} label="예상 총 비용" value={fmtCost(overview.estimated_cost_usd)}
          sub={`${fmtTok(overview.total_tokens)} 토큰`}                                            color="bg-emerald-50 text-emerald-600" />
      </div>

      {/* 팀별 비교 + 시너지 페어링 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <TeamBreakdown teams={data.team_stats} />
        <SynergyPairs pairs={data.synergy_pairs} />
      </div>

      {/* 에이전트 TOP 10 */}
      <TopAgents agents={data.top_agents} />

      {/* 모델별 비용 + 14일 추이 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ModelCosts stats={data.model_cost_stats} />
        <DailyTrend stats={data.daily_run_stats} />
      </div>
    </div>
  );
}
