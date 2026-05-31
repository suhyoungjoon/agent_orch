"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { api, Agent, SynergyCandidate, SynergyResponse } from "@/lib/api";
import {
  X, Zap, Loader2, GitFork, ArrowDown, ArrowUp,
  GitMerge, Sparkles, ChevronRight,
} from "lucide-react";

const ROLE_COLOR: Record<string, string> = {
  researcher: "bg-blue-100 text-blue-700",
  writer:     "bg-purple-100 text-purple-700",
  analyst:    "bg-amber-100 text-amber-700",
  coder:      "bg-green-100 text-green-700",
};

const FLOW_LABEL: Record<string, { text: string; icon: React.ElementType; color: string }> = {
  after:    { text: "이 에이전트 실행 후 연결",   icon: ArrowDown,  color: "text-blue-600"  },
  before:   { text: "이 에이전트를 먼저 실행",     icon: ArrowUp,    color: "text-violet-600" },
  parallel: { text: "병렬 실행 가능",              icon: GitMerge,   color: "text-amber-600"  },
};

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 50 ? "bg-green-400" :
    pct >= 25 ? "bg-amber-400" : "bg-gray-300";
  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-gray-600 w-7 text-right">{pct}%</span>
    </div>
  );
}

function CandidateRow({ item, rank }: { item: SynergyCandidate; rank: number }) {
  const flow = item.suggested_flow ? FLOW_LABEL[item.suggested_flow] : null;
  const FlowIcon = flow?.icon;

  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50 p-3 space-y-2">
      {/* 상단: 순위 + 이름 + 역할 + 점수 */}
      <div className="flex items-center gap-2">
        <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-[10px] font-bold flex items-center justify-center shrink-0">
          {rank}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-sm font-medium text-gray-900 truncate">{item.agent.name}</span>
            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${ROLE_COLOR[item.agent.role] ?? "bg-gray-100 text-gray-600"}`}>
              {item.agent.role}
            </span>
            <span className="text-[10px] text-gray-400 font-mono">v{item.agent.version}</span>
          </div>
        </div>
        <ScoreBar score={item.score} />
      </div>

      {/* 근거 배지 */}
      {item.reasons.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {item.reasons.map((r, i) => (
            <span key={i} className="text-[10px] bg-white border border-gray-200 text-gray-600 rounded-full px-2 py-0.5">
              {r}
            </span>
          ))}
        </div>
      )}

      {/* 실행 순서 제안 */}
      {flow && FlowIcon && (
        <div className={`flex items-center gap-1 text-[11px] font-medium ${flow.color}`}>
          <FlowIcon size={11} />
          {flow.text}
        </div>
      )}
    </div>
  );
}

export default function SynergyPanel({
  agent,
  onClose,
}: {
  agent: Agent;
  onClose: () => void;
}) {
  const { data: session } = useSession();
  const [data, setData] = useState<SynergyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [aiLoading, setAiLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const result = await api.getSynergy(
          agent.id,
          { limit: 5 },
          session?.user?.accessToken,
        );
        setData(result);
      } catch (e) {
        setError(e instanceof Error ? e.message : "불러오기 실패");
      } finally {
        setLoading(false);
      }
    })();
  }, [agent.id, session]);

  async function handleClaudeAnalysis() {
    setAiLoading(true);
    try {
      const result = await api.getSynergy(
        agent.id,
        { limit: 5, useClaude: true },
        session?.user?.accessToken,
      );
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI 분석 실패");
    } finally {
      setAiLoading(false);
    }
  }

  return (
    /* 백드롭 */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-2">
            <Zap size={16} className="text-amber-500" />
            <span className="font-semibold text-gray-900 text-sm">시너지 분석</span>
            <span className="text-sm text-gray-400">— {agent.name}</span>
            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${ROLE_COLOR[agent.role] ?? "bg-gray-100 text-gray-600"}`}>
              {agent.role}
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100 text-gray-400">
            <X size={16} />
          </button>
        </div>

        {/* 바디 */}
        <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">
          {loading && (
            <div className="flex items-center justify-center py-12 text-gray-400">
              <Loader2 size={20} className="animate-spin mr-2" />
              <span className="text-sm">분석 중...</span>
            </div>
          )}

          {error && (
            <p className="text-sm text-red-500 text-center py-8">{error}</p>
          )}

          {!loading && data && (
            <>
              {/* 점수 범례 */}
              <div className="flex items-center gap-4 text-[10px] text-gray-400 px-1">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-400 inline-block" />50%+ 높음</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />25~49% 보통</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-gray-300 inline-block" />~24% 낮음</span>
              </div>

              {/* 후보 목록 */}
              {data.candidates.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">추천 가능한 에이전트가 없습니다.</p>
              ) : (
                <div className="space-y-2">
                  {data.candidates.map((c, i) => (
                    <CandidateRow key={c.agent.id} item={c} rank={i + 1} />
                  ))}
                </div>
              )}

              {/* Claude 분석 결과 */}
              {data.claude_analysis && (
                <div className={`rounded-xl p-4 text-sm leading-relaxed whitespace-pre-wrap ${
                  data.is_mock_analysis
                    ? "bg-gray-50 text-gray-500 border border-dashed border-gray-200"
                    : "bg-amber-50 text-amber-900 border border-amber-100"
                }`}>
                  <div className="flex items-center gap-1.5 mb-2">
                    <Sparkles size={13} className={data.is_mock_analysis ? "text-gray-400" : "text-amber-600"} />
                    <span className="text-xs font-semibold">
                      {data.is_mock_analysis ? "목업 분석 (Claude API 키 미설정)" : "Claude AI 분석"}
                    </span>
                  </div>
                  {data.claude_analysis}
                </div>
              )}
            </>
          )}
        </div>

        {/* 푸터 — Claude 분석 버튼 */}
        {!loading && data && !data.claude_analysis && (
          <div className="px-5 py-3 border-t border-gray-100 shrink-0">
            <button
              onClick={handleClaudeAnalysis}
              disabled={aiLoading}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-xl text-sm font-medium bg-amber-500 text-white hover:bg-amber-600 transition-colors disabled:opacity-60"
            >
              {aiLoading
                ? <><Loader2 size={14} className="animate-spin" />분석 중...</>
                : <><Sparkles size={14} />Claude AI 심층 분석</>
              }
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
