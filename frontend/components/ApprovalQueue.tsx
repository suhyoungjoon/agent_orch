"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import { PendingRun, api } from "@/lib/api";
import { CheckCircle, XCircle, Clock, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";

export default function ApprovalQueue() {
  const { data: session } = useSession();
  const [runs, setRuns] = useState<PendingRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(true);

  const isAdmin = session?.user?.role === "admin";

  const fetchPending = useCallback(async () => {
    const token = session?.user?.accessToken;
    if (!token) return;
    try {
      const data = await api.getPendingRuns(token);
      setRuns(data);
    } catch {
      // silently ignore if not admin or error
    }
  }, [session?.user?.accessToken]);

  useEffect(() => {
    fetchPending();
    // Poll every 10 seconds for new approval requests
    const interval = setInterval(fetchPending, 10_000);
    return () => clearInterval(interval);
  }, [fetchPending]);

  // Also listen on SSE stream for real-time pending_approval events
  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const es = new EventSource(`${base}/api/v1/runs/stream`);
    es.onmessage = (e) => {
      try {
        const run = JSON.parse(e.data);
        if (run.status === "pending_approval") {
          setRuns((prev) => {
            const exists = prev.some((r) => r.run_id === run.run_id);
            if (exists) return prev;
            return [{ ...run, agent_name: null, requester_name: null }, ...prev];
          });
        } else {
          // If a run moved out of pending_approval (approved/rejected), remove it
          setRuns((prev) => prev.filter((r) => r.run_id !== run.run_id || run.status === "pending_approval"));
        }
      } catch {
        // ignore parse errors
      }
    };
    return () => es.close();
  }, []);

  if (!isAdmin) return null;
  if (runs.length === 0) return null;

  return (
    <section className="rounded-2xl border border-amber-200 bg-amber-50">
      <div
        className="flex items-center justify-between px-5 py-3 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <Clock size={16} className="text-amber-600" />
          <h2 className="font-semibold text-amber-900 text-sm">승인 대기 중</h2>
          <span className="rounded-full bg-amber-500 text-white text-xs px-2 py-0.5 font-medium">
            {runs.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); fetchPending(); }}
            className="p-1 rounded hover:bg-amber-100 text-amber-500 transition-colors"
            title="새로고침"
          >
            <RefreshCw size={13} />
          </button>
          {expanded ? <ChevronUp size={15} className="text-amber-500" /> : <ChevronDown size={15} className="text-amber-500" />}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-amber-200 divide-y divide-amber-100">
          {runs.map((run) => (
            <ApprovalRow
              key={run.run_id}
              run={run}
              token={session?.user?.accessToken}
              onDone={() => setRuns((prev) => prev.filter((r) => r.run_id !== run.run_id))}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function ApprovalRow({
  run,
  token,
  onDone,
}: {
  run: PendingRun;
  token?: string;
  onDone: () => void;
}) {
  const [note, setNote] = useState("");
  const [showNote, setShowNote] = useState(false);
  const [acting, setActing] = useState<"approve" | "reject" | null>(null);

  async function handleApprove() {
    setActing("approve");
    try {
      await api.approveRun(run.run_id, note || undefined, token);
      onDone();
    } catch (e) {
      alert(e instanceof Error ? e.message : "승인 처리 실패");
      setActing(null);
    }
  }

  async function handleReject() {
    setActing("reject");
    try {
      await api.rejectRun(run.run_id, note || undefined, token);
      onDone();
    } catch (e) {
      alert(e instanceof Error ? e.message : "거부 처리 실패");
      setActing(null);
    }
  }

  return (
    <div className="px-5 py-3 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            {run.agent_name && (
              <span className="text-xs font-semibold text-amber-800 bg-amber-100 rounded px-1.5 py-0.5">
                {run.agent_name}
              </span>
            )}
            {run.requester_name && (
              <span className="text-xs text-gray-500">요청자: {run.requester_name}</span>
            )}
            <span className="text-xs text-gray-400 font-mono">{run.run_id.slice(0, 8)}…</span>
          </div>
          <p className="text-sm text-gray-700 mt-1 line-clamp-2">{run.task}</p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={handleApprove}
            disabled={acting !== null}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            <CheckCircle size={12} />
            승인
          </button>
          <button
            onClick={handleReject}
            disabled={acting !== null}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 transition-colors"
          >
            <XCircle size={12} />
            거부
          </button>
          <button
            onClick={() => setShowNote(!showNote)}
            className="px-2 py-1 rounded-lg text-xs text-gray-500 hover:bg-amber-100 transition-colors"
          >
            사유
          </button>
        </div>
      </div>
      {showNote && (
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="승인/거부 사유 (선택)"
          className="rounded-lg border border-amber-200 bg-white px-3 py-1.5 text-xs text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-amber-300 w-full"
        />
      )}
    </div>
  );
}
