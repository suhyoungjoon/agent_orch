"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import {
  api,
  TeamDashboardData,
  MemberStat,
  AgentStat,
  RunLog,
} from "@/lib/api";
import {
  Bot, Users, Play, Zap,
  DollarSign, RefreshCw, Clock, TrendingUp, AlertCircle,
} from "lucide-react";

// ── 숫자 포매터 ─────────────────────────────────────────────────────
function fmt(n: number) {
  return n.toLocaleString("ko-KR");
}

function fmtCost(usd: number) {
  if (usd === 0) return "$0.00";
  if (usd < 0.000001) return "<$0.000001";
  if (usd < 0.01) return `$${usd.toFixed(6)}`;
  return `$${usd.toFixed(4)}`;
}

function fmtTokens(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function timeAgo(iso: string) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}초 전`;
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return `${Math.floor(diff / 86400)}일 전`;
}

// ── 역할 컬러 ────────────────────────────────────────────────────────
const ROLE_COLOR: Record<string, string> = {
  researcher: "bg-blue-100 text-blue-700",
  writer:     "bg-purple-100 text-purple-700",
  analyst:    "bg-amber-100 text-amber-700",
  coder:      "bg-green-100 text-green-700",
};

const STATUS_COLOR: Record<string, string> = {
  completed: "bg-green-100 text-green-700",
  failed:    "bg-red-100 text-red-600",
  running:   "bg-blue-100 text-blue-700",
  pending:   "bg-gray-100 text-gray-600",
};

// ── 요약 카드 ────────────────────────────────────────────────────────
function SummaryCard({
  icon: Icon,
  label,
  value,
  sub,
  color,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  sub?: string;
  color: string;
}) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 flex items-center gap-4">
      <div className={`rounded-xl p-2.5 ${color}`}>
        <Icon size={20} />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-xl font-bold text-gray-900 leading-tight">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ── 성공률 바 ────────────────────────────────────────────────────────
function RateBar({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            pct >= 80 ? "bg-green-400" : pct >= 50 ? "bg-amber-400" : "bg-red-400"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-medium text-gray-600 w-8 text-right">{pct}%</span>
    </div>
  );
}

// ── 유저 아바타 ──────────────────────────────────────────────────────
function Avatar({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center shrink-0 text-xs font-bold text-blue-700">
      {initials}
    </div>
  );
}

// ── 스켈레톤 ─────────────────────────────────────────────────────────
function DashboardSkeleton() {
  return (
    <div className="space-y-8 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="h-7 w-44 rounded-lg bg-gray-200" />
          <div className="h-4 w-28 rounded bg-gray-100" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-20 rounded-2xl border border-gray-100 bg-gray-50" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="h-52 rounded-2xl border border-gray-100 bg-gray-50" />
        <div className="h-52 rounded-2xl border border-gray-100 bg-gray-50" />
      </div>
      <div className="h-64 rounded-2xl border border-gray-100 bg-gray-50" />
    </div>
  );
}

// ── 에러 배너 ─────────────────────────────────────────────────────────
function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="rounded-2xl border border-red-200 bg-red-50 p-6 flex items-start gap-3">
      <AlertCircle size={18} className="text-red-500 shrink-0 mt-0.5" />
      <div>
        <p className="text-sm font-medium text-red-700">{message}</p>
        <button
          onClick={onRetry}
          className="mt-1.5 text-xs text-red-600 hover:text-red-700 underline underline-offset-2"
        >
          다시 시도
        </button>
      </div>
    </div>
  );
}

// ── 팀 없음 안내 ─────────────────────────────────────────────────────
function NoTeamState() {
  return (
    <div className="rounded-2xl border-2 border-dashed border-gray-200 py-20 text-center">
      <Users size={40} className="mx-auto mb-3 text-gray-200" />
      <p className="text-sm font-semibold text-gray-500">팀 데이터가 없습니다</p>
      <p className="text-xs text-gray-400 mt-1">팀에 가입하거나 관리자에게 초대를 요청하세요</p>
    </div>
  );
}

// ── 메인 컴포넌트 ────────────────────────────────────────────────────
export default function TeamDashboard() {
  const { data: session } = useSession();
  const [data, setData] = useState<TeamDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetch = useCallback(async () => {
    const teamId = session?.user?.teamId;
    const token  = session?.user?.accessToken;
    if (!teamId || !token) {
      setLoading(false);
      return;
    }
    setError(null);
    try {
      const d = await api.getDashboard(teamId, token);
      setData(d);
      setLastUpdated(new Date());
    } catch {
      setError("대시보드 데이터를 불러오지 못했습니다. 네트워크 상태를 확인해주세요.");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    fetch();
    const id = setInterval(fetch, 30_000);
    return () => clearInterval(id);
  }, [fetch]);

  if (loading) return <DashboardSkeleton />;
  if (error)   return <ErrorBanner message={error} onRetry={fetch} />;
  if (!data)   return <NoTeamState />;

  const { summary, member_stats, agent_stats, recent_runs } = data;

  return (
    <div className="space-y-8">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{data.team_name}</h1>
          <p className="text-sm text-gray-500 mt-0.5">팀 에이전트 사용 현황</p>
        </div>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-xs text-gray-400">
              {lastUpdated.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })} 기준
            </span>
          )}
          <button
            onClick={fetch}
            className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
            title="새로고침"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* 요약 카드 5개 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <SummaryCard
          icon={Bot}
          label="전체 에이전트"
          value={fmt(summary.total_agents)}
          color="bg-blue-50 text-blue-600"
        />
        <SummaryCard
          icon={Play}
          label="전체 실행"
          value={fmt(summary.total_runs)}
          sub={`실행 중 ${summary.running_runs}건`}
          color="bg-indigo-50 text-indigo-600"
        />
        <SummaryCard
          icon={TrendingUp}
          label="성공률"
          value={`${(summary.success_rate * 100).toFixed(1)}%`}
          sub={`완료 ${fmt(summary.completed_runs)} / 실패 ${fmt(summary.failed_runs)}`}
          color={
            summary.success_rate >= 0.8
              ? "bg-green-50 text-green-600"
              : summary.success_rate >= 0.5
              ? "bg-amber-50 text-amber-600"
              : "bg-red-50 text-red-600"
          }
        />
        <SummaryCard
          icon={Zap}
          label="총 토큰"
          value={fmtTokens(summary.total_tokens)}
          color="bg-violet-50 text-violet-600"
        />
        <SummaryCard
          icon={DollarSign}
          label="예상 비용"
          value={fmtCost(summary.estimated_cost_usd)}
          sub="OpenAI 기준"
          color="bg-emerald-50 text-emerald-600"
        />
      </div>

      {/* 팀원 통계 + 에이전트 통계 (2열) */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <MemberStatsTable members={member_stats} />
        <AgentStatsTable agents={agent_stats} />
      </div>

      {/* 최근 실행 로그 */}
      <RecentRunsTable runs={recent_runs} />
    </div>
  );
}

// ── 팀원별 사용량 ────────────────────────────────────────────────────
function MemberStatsTable({ members }: { members: MemberStat[] }) {
  const maxRuns = Math.max(...members.map((m) => m.runs_count), 1);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <div className="flex items-center gap-2 mb-4">
        <Users size={16} className="text-gray-500" />
        <h2 className="text-sm font-semibold text-gray-800">팀원별 사용량</h2>
      </div>

      {members.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">실행 기록이 없습니다.</p>
      ) : (
        <div className="space-y-3">
          {members.map((m) => (
            <div key={m.user_id} className="flex items-center gap-3">
              <Avatar name={m.name} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-gray-800 truncate">{m.name}</span>
                  <span className="text-xs text-gray-500 shrink-0 ml-2">{m.runs_count}회</span>
                </div>
                <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-400 transition-all"
                    style={{ width: `${(m.runs_count / maxRuns) * 100}%` }}
                  />
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-xs text-gray-500">{fmtTokens(m.tokens_used)} tok</div>
                <div className="text-xs text-emerald-600 font-medium">{fmtCost(m.estimated_cost_usd)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 에이전트별 성공률 ────────────────────────────────────────────────
function AgentStatsTable({ agents }: { agents: AgentStat[] }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <div className="flex items-center gap-2 mb-4">
        <Bot size={16} className="text-gray-500" />
        <h2 className="text-sm font-semibold text-gray-800">에이전트별 성공률</h2>
      </div>

      {agents.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">에이전트가 없습니다.</p>
      ) : (
        <div className="space-y-3">
          {agents.map((a) => (
            <div key={a.agent_id} className="space-y-1">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                      ROLE_COLOR[a.role] ?? "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {a.role}
                  </span>
                  <span className="text-sm font-medium text-gray-800 truncate">{a.name}</span>
                </div>
                <div className="text-right shrink-0">
                  <span className="text-xs text-gray-500">{a.usage_count}회</span>
                  <span className="text-xs text-gray-400 ml-2">{fmtTokens(a.total_tokens)}</span>
                </div>
              </div>
              <RateBar rate={a.success_rate} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 최근 실행 로그 ────────────────────────────────────────────────────
function RecentRunsTable({ runs }: { runs: RunLog[] }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <div className="flex items-center gap-2 mb-4">
        <Clock size={16} className="text-gray-500" />
        <h2 className="text-sm font-semibold text-gray-800">최근 실행 로그</h2>
        <span className="text-xs text-gray-400">최근 20건</span>
      </div>

      {runs.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">실행 기록이 없습니다.</p>
      ) : (
        <div className="divide-y divide-gray-50">
          {runs.map((r) => (
            <div key={r.run_id} className="py-2.5 flex items-start gap-3">
              {/* 유저 아바타 */}
              <Avatar name={r.user_name ?? "?"} />

              {/* 태스크 정보 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-medium text-gray-700 truncate max-w-[160px]">
                    {r.agent_name ?? r.agent_id}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                      STATUS_COLOR[r.status] ?? "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {r.status === "completed" ? "완료" : r.status === "failed" ? "실패" : r.status === "running" ? "실행 중" : r.status}
                  </span>
                </div>
                <p className="text-xs text-gray-500 truncate mt-0.5">{r.task}</p>
              </div>

              {/* 토큰 + 비용 + 시간 */}
              <div className="text-right shrink-0 space-y-0.5">
                {(r.input_tokens + r.output_tokens) > 0 && (
                  <div className="text-xs text-gray-400">
                    {fmtTokens(r.input_tokens + r.output_tokens)} tok
                    {r.estimated_cost_usd > 0 && (
                      <span className="text-emerald-600 ml-1">{fmtCost(r.estimated_cost_usd)}</span>
                    )}
                  </div>
                )}
                <div className="text-[10px] text-gray-400">{timeAgo(r.created_at)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
