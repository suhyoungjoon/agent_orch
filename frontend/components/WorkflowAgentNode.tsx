"use client";

import { memo } from "react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import { Loader2, CheckCircle, XCircle } from "lucide-react";

const ROLE_COLOR: Record<string, string> = {
  researcher: "bg-blue-500",
  writer:     "bg-purple-500",
  analyst:    "bg-amber-500",
  coder:      "bg-green-500",
};

const ROLE_BG: Record<string, string> = {
  researcher: "bg-blue-50 border-blue-200",
  writer:     "bg-purple-50 border-purple-200",
  analyst:    "bg-amber-50 border-amber-200",
  coder:      "bg-green-50 border-green-200",
};

export type AgentNodeData = {
  agentId: string;
  label: string;
  role: string;
  tags?: string[];
  hasConflict?: boolean;
  runStatus?: "pending" | "running" | "completed" | "failed";
};

function WorkflowAgentNode({ data, selected }: NodeProps) {
  const d = data as AgentNodeData;
  const headerColor = ROLE_COLOR[d.role] ?? "bg-gray-500";
  const bgColor = ROLE_BG[d.role] ?? "bg-gray-50 border-gray-200";

  const borderClass = d.hasConflict
    ? "border-red-400 shadow-red-100"
    : d.runStatus === "running"
    ? "border-blue-400 shadow-blue-200 animate-pulse"
    : d.runStatus === "completed"
    ? "border-green-400 shadow-green-100"
    : d.runStatus === "failed"
    ? "border-red-400 shadow-red-100"
    : selected
    ? "border-blue-400 shadow-blue-100"
    : bgColor;

  return (
    <div
      className={`
        rounded-xl border-2 shadow-sm min-w-[160px] overflow-hidden transition-all
        ${borderClass}
      `}
    >
      {/* 핸들 — 입력 (상단) */}
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white"
      />

      {/* 역할 헤더 */}
      <div className={`${headerColor} px-3 py-1.5 flex items-center justify-between`}>
        <span className="text-xs font-semibold text-white uppercase tracking-wide">{d.role}</span>
        {d.runStatus === "running" && (
          <Loader2 size={12} className="text-white animate-spin" />
        )}
        {d.runStatus === "completed" && (
          <CheckCircle size={12} className="text-white" />
        )}
        {d.runStatus === "failed" && (
          <XCircle size={12} className="text-white" />
        )}
      </div>

      {/* 에이전트 이름 + 태그 */}
      <div className="px-3 py-2 space-y-1">
        <p className="text-sm font-medium text-gray-900 leading-tight">{d.label}</p>
        {(d.tags ?? []).length > 0 && (
          <div className="flex flex-wrap gap-1">
            {(d.tags ?? []).slice(0, 3).map((t) => (
              <span key={t} className="text-[9px] bg-white border border-gray-200 text-gray-500 rounded px-1">
                #{t}
              </span>
            ))}
          </div>
        )}
        {d.runStatus === "running" && (
          <p className="text-[10px] text-blue-500 font-medium">실행 중...</p>
        )}
        {d.runStatus === "completed" && (
          <p className="text-[10px] text-green-600 font-medium">완료</p>
        )}
        {d.runStatus === "failed" && (
          <p className="text-[10px] text-red-500 font-medium">실패</p>
        )}
      </div>

      {/* 핸들 — 출력 (하단) */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white"
      />
    </div>
  );
}

export default memo(WorkflowAgentNode);
