"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import AppHeader from "@/components/AppHeader";
import WorkflowBuilder from "@/components/WorkflowBuilder";
import { api, Workflow } from "@/lib/api";
import { Plus, GitMerge, Loader2, Trash2, Clock } from "lucide-react";

function WorkflowCard({
  wf,
  onOpen,
  onDelete,
}: {
  wf: Workflow;
  onOpen: () => void;
  onDelete: () => void;
}) {
  const nodeCount = wf.nodes.length;
  const edgeCount = wf.edges.length;
  const updatedAt = new Date(wf.updated_at).toLocaleDateString("ko-KR", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });

  return (
    <div
      onClick={onOpen}
      className="rounded-xl border border-gray-200 bg-white p-4 cursor-pointer hover:border-blue-300 hover:shadow-sm transition-all group"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <GitMerge size={16} className="text-blue-500 shrink-0" />
          <p className="font-semibold text-gray-900 text-sm truncate">{wf.name}</p>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition-all"
        >
          <Trash2 size={13} />
        </button>
      </div>

      {wf.description && (
        <p className="text-xs text-gray-500 mt-1 line-clamp-2">{wf.description}</p>
      )}

      <div className="flex items-center gap-3 mt-3 text-xs text-gray-400">
        <span>{nodeCount}개 에이전트</span>
        <span>·</span>
        <span>{edgeCount}개 연결</span>
        <span className="flex items-center gap-1 ml-auto">
          <Clock size={11} />
          {updatedAt}
        </span>
      </div>
    </div>
  );
}

export default function WorkflowPage() {
  const { data: session } = useSession();
  const token = session?.user?.accessToken;

  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState<string | null | "new">(null);

  async function loadWorkflows() {
    try {
      setWorkflows(await api.getWorkflows(token));
    } catch {
      setWorkflows([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { if (token !== undefined) loadWorkflows(); }, [token]);

  async function handleDelete(id: string) {
    if (!confirm("워크플로를 삭제하시겠습니까?")) return;
    await api.deleteWorkflow(id, token);
    setWorkflows((prev) => prev.filter((w) => w.id !== id));
  }

  // 빌더 열려 있을 때
  if (openId !== null) {
    return (
      <div className="h-screen flex flex-col">
        <AppHeader />
        <div className="flex-1 min-h-0">
          <WorkflowBuilder
            workflowId={openId === "new" ? null : openId}
            onBack={() => { setOpenId(null); loadWorkflows(); }}
          />
        </div>
      </div>
    );
  }

  // 워크플로 목록
  return (
    <div className="min-h-screen bg-gray-50">
      <AppHeader />
      <main className="mx-auto max-w-5xl px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">워크플로 빌더</h1>
            <p className="text-sm text-gray-500 mt-0.5">에이전트를 시각적으로 연결해 파이프라인을 구성하세요</p>
          </div>
          <button
            onClick={() => setOpenId("new")}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            <Plus size={15} />
            새 워크플로
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16 text-gray-400">
            <Loader2 size={20} className="animate-spin mr-2" />
            <span className="text-sm">불러오는 중...</span>
          </div>
        ) : workflows.length === 0 ? (
          <div
            onClick={() => setOpenId("new")}
            className="rounded-2xl border-2 border-dashed border-gray-300 py-16 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50/30 transition-colors group"
          >
            <GitMerge size={32} className="mx-auto mb-3 text-gray-300 group-hover:text-blue-400 transition-colors" />
            <p className="text-sm font-medium text-gray-500 group-hover:text-blue-600">첫 번째 워크플로를 만들어보세요</p>
            <p className="text-xs text-gray-400 mt-1">에이전트를 드래그&드롭으로 연결해 파이프라인을 구성합니다</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {workflows.map((wf) => (
              <WorkflowCard
                key={wf.id}
                wf={wf}
                onOpen={() => setOpenId(wf.id)}
                onDelete={() => handleDelete(wf.id)}
              />
            ))}
            <button
              onClick={() => setOpenId("new")}
              className="rounded-xl border-2 border-dashed border-gray-200 p-4 flex items-center justify-center gap-2 text-sm text-gray-400 hover:border-blue-300 hover:text-blue-500 transition-colors"
            >
              <Plus size={14} />새 워크플로
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
