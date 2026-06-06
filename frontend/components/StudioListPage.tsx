"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { Plus, Cpu, Loader2, Pencil, Trash2, Play } from "lucide-react";
import { api, Agent } from "@/lib/api";

const ROLE_COLORS: Record<string, string> = {
  researcher: "bg-blue-100 text-blue-700",
  writer:     "bg-purple-100 text-purple-700",
  analyst:    "bg-amber-100 text-amber-700",
  coder:      "bg-green-100 text-green-700",
};

const PROVIDER_BADGE: Record<string, string> = {
  claude: "bg-orange-50 text-orange-600 border-orange-200",
  openai: "bg-emerald-50 text-emerald-600 border-emerald-200",
  gemini: "bg-blue-50 text-blue-600 border-blue-200",
  local:  "bg-gray-50 text-gray-600 border-gray-200",
};

export default function StudioListPage() {
  const { data: session } = useSession();
  const token = session?.user?.accessToken;

  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    fetchAgents();
  }, [token]);

  async function fetchAgents() {
    setLoading(true);
    try {
      const all = await api.getAgents(token);
      setAgents(all.filter((a) => a.is_studio_agent));
    } catch {
      setAgents([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`"${name}" 에이전트를 삭제할까요?`)) return;
    setDeleting(id);
    try {
      await api.deleteAgent(id, token);
      setAgents((prev) => prev.filter((a) => a.id !== id));
    } catch (e) {
      alert(e instanceof Error ? e.message : "삭제 실패");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div>
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Cpu size={22} className="text-violet-600" />
          <div>
            <h1 className="text-xl font-bold text-gray-900">에이전트 스튜디오</h1>
            <p className="text-sm text-gray-500 mt-0.5">개발자용 고급 에이전트 설정</p>
          </div>
        </div>
        <Link
          href="/studio/new"
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 transition-colors"
        >
          <Plus size={15} />
          새 에이전트
        </Link>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-gray-400">
          <Loader2 size={20} className="animate-spin mr-2" />
          불러오는 중...
        </div>
      ) : agents.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-gray-300 py-20 text-center">
          <Cpu size={36} className="mx-auto mb-3 text-gray-300" />
          <p className="text-gray-500 font-medium">스튜디오 에이전트가 없습니다.</p>
          <p className="text-sm text-gray-400 mt-1">새 에이전트를 만들어 모델·프롬프트·툴을 세밀하게 설정하세요.</p>
          <Link
            href="/studio/new"
            className="inline-flex items-center gap-1.5 mt-4 px-4 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 transition-colors"
          >
            <Plus size={14} />
            첫 에이전트 만들기
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {agents.map((agent) => (
            <div key={agent.id} className="rounded-xl border border-gray-200 bg-white p-5 flex flex-col gap-3 hover:shadow-sm transition-shadow">
              {/* 상단 */}
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-gray-900">{agent.name}</span>
                    <span className="text-xs text-gray-400 font-mono">v{agent.version}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ROLE_COLORS[agent.role] ?? "bg-gray-100 text-gray-600"}`}>
                      {agent.role}
                    </span>
                  </div>
                  {agent.description && (
                    <p className="text-xs text-gray-500 mt-1 line-clamp-1">{agent.description}</p>
                  )}
                </div>
                <span className={`shrink-0 rounded border px-2 py-0.5 text-xs font-medium ${PROVIDER_BADGE[agent.llm_provider] ?? PROVIDER_BADGE.local}`}>
                  {agent.llm_provider}
                </span>
              </div>

              {/* 모델 정보 */}
              <div className="rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-600 space-y-0.5">
                <p><span className="text-gray-400">모델</span> {agent.model_name ?? "(기본값)"}</p>
                {agent.temperature != null && <p><span className="text-gray-400">Temperature</span> {agent.temperature}</p>}
                {agent.max_tokens != null && <p><span className="text-gray-400">Max Tokens</span> {agent.max_tokens.toLocaleString()}</p>}
                <p><span className="text-gray-400">메모리</span> {agent.memory_type}</p>
                <p><span className="text-gray-400">프롬프트</span> {agent.system_prompt ? "직접 지정" : "자동 생성"}</p>
              </div>

              {/* 태그 */}
              {(agent.tags ?? []).length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {agent.tags.map((tag) => (
                    <span key={tag} className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">#{tag}</span>
                  ))}
                </div>
              )}

              {/* 액션 */}
              <div className="flex items-center gap-2 pt-1 border-t border-gray-100">
                <Link
                  href={`/studio/${agent.id}`}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-violet-50 text-violet-700 border border-violet-200 hover:bg-violet-100 transition-colors"
                >
                  <Pencil size={11} />
                  편집
                </Link>
                <Link
                  href={`/studio/${agent.id}?test=1`}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-green-50 text-green-700 border border-green-200 hover:bg-green-100 transition-colors"
                >
                  <Play size={11} />
                  테스트
                </Link>
                <button
                  onClick={() => handleDelete(agent.id, agent.name)}
                  disabled={deleting === agent.id}
                  className="ml-auto flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-red-500 hover:bg-red-50 border border-transparent hover:border-red-200 transition-colors disabled:opacity-50"
                >
                  {deleting === agent.id ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
                  삭제
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
