"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Agent, AgentInput, AgentVisibility, api } from "@/lib/api";
import { X, Loader2, Sparkles } from "lucide-react";

const ROLES = ["researcher", "writer", "analyst", "coder"] as const;

const TOOLS = [
  {
    id: "web_search",
    label: "웹 검색",
    desc: "DuckDuckGo로 최신 정보·사실 확인",
  },
  {
    id: "calculate",
    label: "계산기",
    desc: "수식·통계·수학 계산",
  },
  {
    id: "fetch_webpage",
    label: "웹 페이지 읽기",
    desc: "특정 URL 내용 가져오기",
  },
] as const;

// 기존 에이전트 tags → 도구 ID 매핑 (편집 시 체크박스 복원)
const TAG_TO_TOOL: Record<string, string> = {
  검색: "web_search", 수집: "web_search", 리서치: "web_search",
  web_search: "web_search", document_reader: "web_search",
  분석: "calculate", 통계: "calculate", calculate: "calculate",
  data_analyzer: "calculate", chart_generator: "calculate",
  코딩: "fetch_webpage", fetch_webpage: "fetch_webpage",
  작성: "web_search", text_editor: "web_search",
};

function tagsToTools(tags: string[]): string[] {
  const result = new Set<string>();
  for (const t of tags) {
    const tool = TAG_TO_TOOL[t.toLowerCase()];
    if (tool) result.add(tool);
  }
  return Array.from(result);
}

const inputCls =
  "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent";

export interface AgentInitialData {
  name?: string;
  role?: string;
  goal?: string;
  backstory?: string;
  tools?: string[];
}

interface Props {
  agent?: Agent | null;
  initialData?: AgentInitialData;
  onClose: () => void;
}

export default function AgentFormModal({ agent, initialData, onClose }: Props) {
  const { data: session } = useSession();
  const router = useRouter();

  const defaultTools = agent
    ? tagsToTools(agent.tags ?? [])
    : (initialData?.tools ?? []).filter((t) =>
        TOOLS.some((tool) => tool.id === t)
      );

  const [form, setForm] = useState<{
    name: string; role: string; goal: string; backstory: string;
    description: string; version: string; visibility: string;
  }>({
    name: initialData?.name ?? agent?.name ?? "",
    role: initialData?.role ?? agent?.role ?? "researcher",
    goal: initialData?.goal ?? agent?.goal ?? "",
    backstory: initialData?.backstory ?? agent?.backstory ?? "",
    description: agent?.description ?? "",
    version: agent?.version ?? "1.0.0",
    visibility: agent?.visibility ?? "team",
  });
  const [selectedTools, setSelectedTools] = useState<Set<string>>(
    new Set(defaultTools)
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set =
    (k: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));

  function toggleTool(id: string) {
    setSelectedTools((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    const data: AgentInput = {
      name: form.name,
      role: form.role,
      goal: form.goal,
      backstory: form.backstory,
      description: form.description || undefined,
      version: form.version,
      tags: Array.from(selectedTools),
      visibility: form.visibility as AgentVisibility,
    };

    try {
      const token = session?.user?.accessToken;
      if (agent) {
        await api.updateAgent(agent.id, data, token);
      } else {
        await api.createAgent(data, token);
      }
      router.refresh();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장에 실패했습니다.");
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] flex flex-col">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 shrink-0">
          <div>
            <h2 className="font-semibold text-gray-900">
              {agent ? "에이전트 편집" : "새 에이전트"}
            </h2>
            <div className="flex items-center gap-1 mt-0.5">
              <Sparkles size={11} className="text-amber-500" />
              <span className="text-xs text-gray-400">Claude AI 기반으로 실제 작업을 수행합니다</span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-gray-100 text-gray-400 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* 폼 */}
        <form onSubmit={handleSubmit} className="overflow-y-auto p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">이름 *</label>
              <input
                value={form.name}
                onChange={set("name")}
                required
                placeholder="Research Specialist"
                className={inputCls}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">역할 *</label>
              <select value={form.role} onChange={set("role")} className={inputCls}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">버전</label>
              <input
                value={form.version}
                onChange={set("version")}
                placeholder="1.0.0"
                className={inputCls}
              />
            </div>

            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">
                목표 *
                <span className="ml-1 font-normal text-gray-400">(시스템 프롬프트에 반영됩니다)</span>
              </label>
              <textarea
                value={form.goal}
                onChange={set("goal")}
                required
                rows={2}
                placeholder="이 에이전트가 달성해야 할 핵심 목표를 구체적으로 설명하세요"
                className={`${inputCls} resize-none`}
              />
            </div>

            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">
                배경 및 전문성 *
                <span className="ml-1 font-normal text-gray-400">(에이전트의 페르소나를 구성합니다)</span>
              </label>
              <textarea
                value={form.backstory}
                onChange={set("backstory")}
                required
                rows={3}
                placeholder="에이전트의 전문 분야, 경험, 접근 방식을 설명하세요"
                className={`${inputCls} resize-none`}
              />
            </div>

            {/* 도구 선택 */}
            <div className="col-span-2">
              <div className="flex items-center gap-1.5 mb-2">
                <label
                  className="text-xs font-medium text-gray-700"
                  title="선택한 도구를 Claude가 작업 중 자동으로 호출합니다. 미선택 시 모든 도구가 활성화됩니다."
                >
                  사용 도구
                </label>
              </div>
              <div className="space-y-2">
                {TOOLS.map((tool) => (
                  <label
                    key={tool.id}
                    className="flex items-start gap-3 rounded-lg border border-gray-200 px-3 py-2.5 cursor-pointer hover:bg-gray-50 transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={selectedTools.has(tool.id)}
                      onChange={() => toggleTool(tool.id)}
                      className="mt-0.5 accent-blue-600"
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-800">{tool.label}</p>
                      <p className="text-xs text-gray-400">{tool.desc}</p>
                    </div>
                  </label>
                ))}
                <p className="text-xs text-gray-400 pl-1">
                  📅 날짜/시간 도구는 항상 활성화됩니다
                </p>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">공개 범위</label>
              <select value={form.visibility} onChange={set("visibility")} className={inputCls}>
                <option value="team">팀 (팀원만)</option>
                <option value="public">공개 (전체, fork 가능)</option>
                <option value="private">비공개 (나만)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">설명 (선택)</label>
              <input
                value={form.description}
                onChange={set("description")}
                placeholder="한 줄 설명"
                className={inputCls}
              />
            </div>
          </div>

          {error && (
            <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loading && <Loader2 size={14} className="animate-spin" />}
              {loading ? "저장 중..." : agent ? "저장" : "에이전트 생성"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
