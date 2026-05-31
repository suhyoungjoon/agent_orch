"use client";

import { useState, useEffect, useRef } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Agent, Run, api } from "@/lib/api";
import { Loader2, Play, ChevronDown, ChevronUp, Tag, Users, Pencil, Trash2, GitFork, Globe, Lock } from "lucide-react";
import AgentFormModal from "./AgentFormModal";

const ROLE_COLORS: Record<Agent["role"], string> = {
  researcher: "bg-blue-100 text-blue-700",
  writer: "bg-purple-100 text-purple-700",
  analyst: "bg-amber-100 text-amber-700",
  coder: "bg-green-100 text-green-700",
};

const ROLE_LABELS: Record<Agent["role"], string> = {
  researcher: "Researcher",
  writer: "Writer",
  analyst: "Analyst",
  coder: "Coder",
};

interface Props {
  agent: Agent;
}

export default function AgentCard({ agent }: Props) {
  const { data: session } = useSession();
  const router = useRouter();
  const [task, setTask] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [requireApproval, setRequireApproval] = useState(false);

  const isAdmin = session?.user?.role === "admin";
  const isOwnTeam = session?.user?.teamId === agent.team_id;
  const canFork = !isOwnTeam && agent.visibility === "public";
  const [forking, setForking] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => () => wsRef.current?.close(), []);

  async function handleFork() {
    setForking(true);
    try {
      await api.forkAgent(agent.id, session?.user?.accessToken);
      router.refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Fork에 실패했습니다.");
    } finally {
      setForking(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`"${agent.name}" 에이전트를 삭제할까요?`)) return;
    setDeleting(true);
    try {
      await api.deleteAgent(agent.id, session?.user?.accessToken);
      router.refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "삭제에 실패했습니다.");
      setDeleting(false);
    }
  }

  async function handleRun() {
    if (!task.trim()) return;
    setLoading(true);
    setError(null);
    setRun(null);

    // Close any previous WebSocket
    wsRef.current?.close();

    try {
      const token = session?.user?.accessToken;
      const initial = await api.runAgent(agent.id, task.trim(), undefined, token, requireApproval);
      setRun(initial);

      // If approval is pending, stop showing spinner — user waits for admin action
      if (initial.status === "pending_approval") {
        setLoading(false);
        return;
      }

      const base = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
        .replace(/^https/, "wss")
        .replace(/^http/, "ws");
      const ws = new WebSocket(`${base}/api/v1/runs/${initial.run_id}/ws`);
      wsRef.current = ws;

      ws.onmessage = (e) => {
        const data = JSON.parse(e.data) as Run & { type?: string };
        if (data.type === "ping") return;
        setRun(data);
        if (data.status === "completed" || data.status === "failed") {
          ws.close();
        }
        // If approval was required and status moves to running, keep WS open to track execution
      };

      ws.onclose = () => setLoading(false);
      ws.onerror = () => setError("실시간 연결 오류");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm flex flex-col gap-3">
      {/* 헤더 */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-gray-900 text-lg leading-tight">{agent.name}</h3>
            <span className="text-xs text-gray-400 font-mono">v{agent.version}</span>
            <VisibilityBadge visibility={agent.visibility} />
            {agent.forked_from && (
              <span className="flex items-center gap-1 text-xs text-gray-400">
                <GitFork size={10} />
                fork
              </span>
            )}
            {agent.team_id && (
              <span className="flex items-center gap-1 text-xs text-indigo-600 bg-indigo-50 rounded-full px-2 py-0.5">
                <Users size={11} />
                {agent.team_id.slice(0, 8)}
              </span>
            )}
          </div>
          {agent.description && (
            <p className="text-sm text-gray-500 mt-0.5">{agent.description}</p>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${ROLE_COLORS[agent.role]}`}>
            {ROLE_LABELS[agent.role]}
          </span>
          {canFork && (
            <button
              onClick={handleFork}
              disabled={forking}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-violet-50 text-violet-600 hover:bg-violet-100 transition-colors disabled:opacity-50"
              title="내 팀으로 Fork"
            >
              {forking ? <Loader2 size={11} className="animate-spin" /> : <GitFork size={11} />}
              Fork
            </button>
          )}
          {isAdmin && isOwnTeam && (
            <>
              <button
                onClick={() => setEditOpen(true)}
                className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
                title="편집"
              >
                <Pencil size={13} />
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
                title="삭제"
              >
                {deleting ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
              </button>
            </>
          )}
        </div>
      </div>
      {editOpen && (
        <AgentFormModal agent={agent} onClose={() => setEditOpen(false)} />
      )}

      {/* 태그 */}
      {(agent.tags ?? []).length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <Tag size={12} className="text-gray-400 shrink-0" />
          {(agent.tags ?? []).map((tag) => (
            <span key={tag} className="rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* 통계 (usage_count > 0일 때만 표시) */}
      {agent.usage_count > 0 && (
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 flex-1">
            <span className="text-xs text-gray-500 shrink-0">성공률</span>
            <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
              <div
                className="h-full rounded-full bg-green-400 transition-all"
                style={{ width: `${agent.success_rate * 100}%` }}
              />
            </div>
            <span className="text-xs font-medium text-gray-700 shrink-0">
              {(agent.success_rate * 100).toFixed(0)}%
            </span>
          </div>
          <span className="text-xs text-gray-400 shrink-0">{agent.usage_count}회 실행</span>
        </div>
      )}

      {/* 상세 정보 토글 */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 self-start"
      >
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        {expanded ? "접기" : "상세 보기"}
      </button>

      {expanded && (
        <div className="text-sm text-gray-600 space-y-3 bg-gray-50 rounded-lg p-3">
          <div>
            <span className="font-medium text-gray-700">Goal: </span>
            {agent.goal}
          </div>
          <div>
            <span className="font-medium text-gray-700">Backstory: </span>
            {agent.backstory}
          </div>
          {agent.input_schema && (
            <div>
              <p className="font-medium text-gray-700 mb-1">Input Schema</p>
              <SchemaView schema={agent.input_schema} />
            </div>
          )}
          {agent.output_schema && (
            <div>
              <p className="font-medium text-gray-700 mb-1">Output Schema</p>
              <SchemaView schema={agent.output_schema} />
            </div>
          )}
        </div>
      )}

      {/* 태스크 입력 */}
      <div className="flex flex-col gap-2">
        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="에이전트에게 맡길 작업을 입력하세요..."
          rows={2}
          className="resize-none rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <div className="flex items-center justify-between gap-2">
          <label className="flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={requireApproval}
              onChange={(e) => setRequireApproval(e.target.checked)}
              className="rounded border-gray-300 text-amber-500 focus:ring-amber-400"
            />
            <span className="text-xs text-gray-500">승인 후 실행</span>
          </label>
          <button
            onClick={handleRun}
            disabled={loading || !task.trim()}
            className="flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
            {loading ? (requireApproval ? "대기 중..." : "실행 중...") : (requireApproval ? "승인 요청" : "실행")}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>
      )}

      {run && (
        <div className="rounded-lg border border-gray-100 bg-gray-50 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <StatusBadge status={run.status} />
            <span className="text-xs text-gray-400">{run.run_id.slice(0, 8)}…</span>
          </div>
          {run.result && (
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{run.result}</p>
          )}
          {run.error && (
            <p className="text-sm text-red-600 whitespace-pre-wrap">{run.error}</p>
          )}
        </div>
      )}
    </div>
  );
}

function SchemaView({ schema }: { schema: Record<string, unknown> }) {
  const props = schema.properties as Record<string, { type?: string }> | undefined;
  const required = schema.required as string[] | undefined;

  if (!props) {
    return (
      <pre className="rounded bg-white border border-gray-200 p-2 text-xs text-gray-600 overflow-x-auto">
        {JSON.stringify(schema, null, 2)}
      </pre>
    );
  }

  return (
    <div className="rounded bg-white border border-gray-200 p-2 space-y-1">
      {Object.entries(props).map(([key, def]) => (
        <div key={key} className="flex items-center gap-2 text-xs">
          <span className="font-mono text-gray-800">{key}</span>
          {def.type && (
            <span className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-500">{def.type}</span>
          )}
          {required?.includes(key) && (
            <span className="text-red-400 text-[10px]">required</span>
          )}
        </div>
      ))}
    </div>
  );
}

function VisibilityBadge({ visibility }: { visibility: Agent["visibility"] }) {
  if (visibility === "public") {
    return (
      <span className="flex items-center gap-0.5 text-xs text-emerald-600 bg-emerald-50 rounded-full px-1.5 py-0.5">
        <Globe size={10} />
        공개
      </span>
    );
  }
  if (visibility === "private") {
    return (
      <span className="flex items-center gap-0.5 text-xs text-gray-500 bg-gray-100 rounded-full px-1.5 py-0.5">
        <Lock size={10} />
        비공개
      </span>
    );
  }
  return null; // "team" is the default — no badge needed
}

function StatusBadge({ status }: { status: Run["status"] }) {
  const styles: Record<Run["status"], string> = {
    pending: "bg-gray-100 text-gray-600",
    pending_approval: "bg-amber-100 text-amber-700",
    running: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-600",
  };
  const labels: Record<Run["status"], string> = {
    pending: "대기 중",
    pending_approval: "승인 대기",
    running: "실행 중",
    completed: "완료",
    failed: "실패",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${styles[status]}`}>
      {labels[status]}
    </span>
  );
}
