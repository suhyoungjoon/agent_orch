"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { AgentConfig, ParseIntentResult, api } from "@/lib/api";
import AgentFormModal from "./AgentFormModal";
import {
  Sparkles,
  Loader2,
  ChevronRight,
  Wrench,
  AlertCircle,
  Plus,
  BookOpen,
} from "lucide-react";

const ROLE_COLORS: Record<string, string> = {
  researcher: "bg-blue-100 text-blue-700",
  writer: "bg-purple-100 text-purple-700",
  analyst: "bg-amber-100 text-amber-700",
  coder: "bg-green-100 text-green-700",
};

const ROLE_BACKSTORY: Record<string, string> = {
  researcher: "정보 수집과 분석에 특화된 전문 리서처입니다.",
  writer: "수집된 정보를 명확하고 구조화된 콘텐츠로 변환하는 작가입니다.",
  analyst: "데이터를 분석하고 의미 있는 인사이트를 도출하는 분석가입니다.",
  coder: "효율적이고 명확한 코드를 작성하는 소프트웨어 엔지니어입니다.",
};

const KNOWN_TOOLS = ["web_search", "calculate", "fetch_webpage"];

export default function ParseIntent() {
  const { data: session } = useSession();
  const [text, setText] = useState("");
  const [result, setResult] = useState<ParseIntentResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creatingAgent, setCreatingAgent] = useState<AgentConfig | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await api.parseIntent(text.trim(), session?.user?.accessToken);
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "요청에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-indigo-50 p-5">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={18} className="text-blue-600" />
        <h2 className="text-base font-semibold text-gray-800">
          AI 에이전트 구성 추천
        </h2>
        <span className="text-xs text-gray-400">— 자연어로 작업을 설명하세요</span>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="예: 경쟁사 분석 보고서를 작성해줘"
          className="flex-1 rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <button
          type="submit"
          disabled={loading || !text.trim()}
          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <ChevronRight size={14} />
          )}
          {loading ? "분석 중..." : "분석"}
        </button>
      </form>

      {error && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
          <AlertCircle size={14} />
          {error}
        </div>
      )}

      {result && (
        <div className="mt-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-gray-600">
              추천 에이전트 구성 ({result.agents.length}개)
            </p>
            {result.is_mock && (
              <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">
                mock — ANTHROPIC_API_KEY 미설정
              </span>
            )}
            {result.model_used && (
              <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                {result.model_used}
              </span>
            )}
          </div>

          {result.agents.length === 0 ? (
            <div className="rounded-lg bg-yellow-50 border border-yellow-100 px-4 py-3 text-sm text-yellow-700">
              추천 에이전트를 생성하지 못했습니다. 다시 시도하거나 직접 에이전트를 등록해주세요.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {result.agents.map((agent) => (
                <AgentConfigCard
                  key={agent.execution_order}
                  agent={agent}
                  onCreateClick={() => setCreatingAgent(agent)}
                />
              ))}
            </div>
          )}

          {creatingAgent && (
            <AgentFormModal
              initialData={{
                name: creatingAgent.name,
                role: creatingAgent.role,
                goal: creatingAgent.goal,
                backstory: ROLE_BACKSTORY[creatingAgent.role] ?? `${creatingAgent.role} 전문 에이전트입니다.`,
                tools: creatingAgent.tools.filter((t) => KNOWN_TOOLS.includes(t)),
              }}
              onClose={() => setCreatingAgent(null)}
            />
          )}
        </div>
      )}
    </section>
  );
}

function AgentConfigCard({
  agent,
  onCreateClick,
}: {
  agent: AgentConfig;
  onCreateClick: () => void;
}) {
  const roleColor = ROLE_COLORS[agent.role] ?? "bg-gray-100 text-gray-600";

  return (
    <div className="rounded-xl bg-white border border-gray-100 p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-mono text-gray-400 shrink-0">
            #{agent.execution_order}
          </span>
          <span className="text-sm font-semibold text-gray-900 truncate">
            {agent.name}
          </span>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${roleColor}`}>
          {agent.role}
        </span>
      </div>

      <p className="text-xs text-gray-600 leading-relaxed">{agent.goal}</p>

      {agent.tools.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap">
          <Wrench size={11} className="text-gray-400 shrink-0" />
          {agent.tools.map((tool) => (
            <span key={tool} className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">
              {tool}
            </span>
          ))}
        </div>
      )}

      <div className="pt-1">
        {agent.existing_agent_id ? (
          <div className="flex items-center gap-1.5 text-xs text-indigo-600 font-medium">
            <BookOpen size={12} />
            레지스트리에 있는 에이전트
          </div>
        ) : (
          <button
            onClick={onCreateClick}
            className="flex items-center gap-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 px-2.5 py-1 text-xs font-medium transition-colors"
          >
            <Plus size={11} />
            에이전트 생성
          </button>
        )}
      </div>
    </div>
  );
}
