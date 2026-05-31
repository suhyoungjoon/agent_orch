"use client";

import { useEffect, useState } from "react";
import { Run } from "@/lib/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function RunHistory() {
  const [runMap, setRunMap] = useState<Map<string, Run>>(new Map());

  useEffect(() => {
    const es = new EventSource(`${BASE_URL}/api/v1/runs/stream`);

    es.onmessage = (event) => {
      const run: Run = JSON.parse(event.data);
      setRunMap((prev) => new Map(prev).set(run.run_id, run));
    };

    es.onerror = () => es.close();

    return () => es.close();
  }, []);

  const runs = Array.from(runMap.values()).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  if (runs.length === 0) return null;

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 mb-3">실행 기록</h2>
      <div className="space-y-2">
        {runs.map((run) => (
          <div
            key={run.run_id}
            className="rounded-xl border border-gray-100 bg-white px-4 py-3 flex items-center justify-between gap-4"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-800 truncate">{run.task}</p>
              <p className="text-xs text-gray-400">{run.agent_id}</p>
            </div>
            <StatusChip status={run.status} />
          </div>
        ))}
      </div>
    </section>
  );
}

function StatusChip({ status }: { status: Run["status"] }) {
  const map: Record<Run["status"], [string, string]> = {
    pending: ["bg-gray-100 text-gray-600", "대기"],
    pending_approval: ["bg-amber-100 text-amber-700", "승인 대기"],
    running: ["bg-blue-100 text-blue-700", "실행 중"],
    completed: ["bg-green-100 text-green-700", "완료"],
    failed: ["bg-red-100 text-red-600", "실패"],
  };
  const [cls, label] = map[status] ?? ["bg-gray-100 text-gray-600", status];
  return (
    <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}
