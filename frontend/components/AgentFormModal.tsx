"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Agent, AgentInput, api } from "@/lib/api";
import { X, Loader2 } from "lucide-react";

const ROLES = ["researcher", "writer", "analyst", "coder"] as const;

const inputCls =
  "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent";

interface Props {
  agent?: Agent | null;
  onClose: () => void;
}

export default function AgentFormModal({ agent, onClose }: Props) {
  const { data: session } = useSession();
  const router = useRouter();

  const [form, setForm] = useState({
    name: agent?.name ?? "",
    role: agent?.role ?? "researcher",
    goal: agent?.goal ?? "",
    backstory: agent?.backstory ?? "",
    description: agent?.description ?? "",
    version: agent?.version ?? "1.0.0",
    tags: (agent?.tags ?? []).join(", "),
    visibility: (agent?.visibility ?? "team") as "public" | "team" | "private",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set =
    (k: keyof typeof form) =>
    (
      e: React.ChangeEvent<
        HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
      >
    ) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));

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
      tags: form.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      visibility: form.visibility,
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
          <h2 className="font-semibold text-gray-900">
            {agent ? "에이전트 편집" : "새 에이전트"}
          </h2>
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
              <label className="block text-xs font-medium text-gray-700 mb-1">
                이름 *
              </label>
              <input
                value={form.name}
                onChange={set("name")}
                required
                placeholder="Research Specialist"
                className={inputCls}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                역할 *
              </label>
              <select
                value={form.role}
                onChange={set("role")}
                className={inputCls}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                버전
              </label>
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
              </label>
              <textarea
                value={form.goal}
                onChange={set("goal")}
                required
                rows={2}
                placeholder="이 에이전트의 핵심 목표를 설명하세요"
                className={`${inputCls} resize-none`}
              />
            </div>

            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">
                배경 *
              </label>
              <textarea
                value={form.backstory}
                onChange={set("backstory")}
                required
                rows={3}
                placeholder="에이전트의 전문성과 배경 스토리"
                className={`${inputCls} resize-none`}
              />
            </div>

            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">
                설명 (선택)
              </label>
              <input
                value={form.description}
                onChange={set("description")}
                placeholder="한 줄 설명"
                className={inputCls}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                공개 범위
              </label>
              <select value={form.visibility} onChange={set("visibility")} className={inputCls}>
                <option value="team">팀 (팀원만)</option>
                <option value="public">공개 (전체 공개, fork 가능)</option>
                <option value="private">비공개 (나만)</option>
              </select>
            </div>

            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">
                태그 (쉼표로 구분)
              </label>
              <input
                value={form.tags}
                onChange={set("tags")}
                placeholder="검색, 분석, 요약"
                className={inputCls}
              />
            </div>
          </div>

          {error && (
            <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              {error}
            </p>
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
              {loading ? "저장 중..." : "저장"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
