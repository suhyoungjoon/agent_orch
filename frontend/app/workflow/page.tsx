"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import AppHeader from "@/components/AppHeader";
import WorkflowBuilder from "@/components/WorkflowBuilder";
import { api, Workflow } from "@/lib/api";
import { Plus, GitMerge, Trash2, Clock, AlertCircle, AlertTriangle } from "lucide-react";

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

// ── 스켈레톤 카드 ─────────────────────────────────────────────────────
function WorkflowCardSkeleton() {
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 animate-pulse space-y-3">
      <div className="flex items-center gap-2">
        <div className="w-4 h-4 rounded bg-gray-200" />
        <div className="h-4 w-32 rounded bg-gray-200" />
      </div>
      <div className="h-3 w-full rounded bg-gray-100" />
      <div className="flex gap-3">
        <div className="h-3 w-16 rounded bg-gray-100" />
        <div className="h-3 w-16 rounded bg-gray-100" />
      </div>
    </div>
  );
}

// ── 삭제 확인 모달 ────────────────────────────────────────────────────
function DeleteModal({
  name,
  onConfirm,
  onCancel,
}: {
  name: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onCancel()}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-5 space-y-4">
        <div className="flex items-start gap-3">
          <div className="rounded-full bg-red-100 p-2 shrink-0">
            <AlertTriangle size={16} className="text-red-600" />
          </div>
          <div>
            <p className="font-semibold text-gray-900 text-sm">워크플로 삭제</p>
            <p className="text-xs text-gray-500 mt-1">
              <span className="font-medium text-gray-700">&ldquo;{name}&rdquo;</span>을 삭제합니다.
              이 작업은 되돌릴 수 없습니다.
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            취소
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
          >
            삭제
          </button>
        </div>
      </div>
    </div>
  );
}

export default function WorkflowPage() {
  const { data: session } = useSession();
  const token = session?.user?.accessToken;

  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null | "new">(null);
  const [deleteTarget, setDeleteTarget] = useState<Workflow | null>(null);

  async function loadWorkflows() {
    setError(null);
    try {
      setWorkflows(await api.getWorkflows(token));
    } catch {
      setError("워크플로 목록을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.");
      setWorkflows([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { if (token !== undefined) loadWorkflows(); }, [token]);

  async function handleDelete(id: string) {
    try {
      await api.deleteWorkflow(id, token);
      setWorkflows((prev) => prev.filter((w) => w.id !== id));
    } catch {
      setError("삭제 중 오류가 발생했습니다. 다시 시도해주세요.");
    } finally {
      setDeleteTarget(null);
    }
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

        {error && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 flex items-center gap-2.5">
            <AlertCircle size={15} className="text-red-500 shrink-0" />
            <p className="text-sm text-red-700 flex-1">{error}</p>
            <button onClick={loadWorkflows} className="text-xs text-red-600 hover:text-red-700 underline shrink-0">
              다시 시도
            </button>
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => <WorkflowCardSkeleton key={i} />)}
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
                onDelete={() => setDeleteTarget(wf)}
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

      {deleteTarget && (
        <DeleteModal
          name={deleteTarget.name}
          onConfirm={() => handleDelete(deleteTarget.id)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
