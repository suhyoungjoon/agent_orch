"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow, Background, Controls, MiniMap,
  useNodesState, useEdgesState, addEdge,
  Node, Edge, Connection, ReactFlowInstance,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useSession } from "next-auth/react";
import { api, Agent, Workflow, WorkflowNode, WorkflowEdge, EdgeMapping, WorkflowRun, NodeRunResult } from "@/lib/api";
import WorkflowAgentNode, { AgentNodeData } from "./WorkflowAgentNode";
import {
  Save, ArrowLeft, AlertTriangle, CheckCircle,
  XCircle, Loader2, GripVertical, Play, ChevronDown, ChevronUp,
  Plus, Trash2, ArrowRight, GitMerge, CircleCheck, CircleX,
} from "lucide-react";

// ── 충돌 감지 ─────────────────────────────────────────────────────────────────

type Conflict = {
  id: string;
  type: "duplicate" | "schema_mismatch" | "cycle";
  severity: "error" | "warning";
  message: string;
};

function detectDuplicates(nodes: Node[]): Conflict[] {
  const counts = new Map<string, number>();
  nodes.forEach((n) => {
    const id = (n.data as AgentNodeData).agentId;
    counts.set(id, (counts.get(id) ?? 0) + 1);
  });
  return Array.from(counts.entries())
    .filter(([, c]) => c > 1)
    .map(([agentId]) => ({
      id: `dup-${agentId}`,
      type: "duplicate" as const,
      severity: "warning" as const,
      message: `에이전트 중복: 같은 에이전트가 ${counts.get(agentId)}번 사용됩니다.`,
    }));
}

function detectSchemaMismatches(
  edges: Edge[],
  nodes: Node[],
  agentMap: Map<string, Agent>,
): Conflict[] {
  const conflicts: Conflict[] = [];
  const nodeById = new Map(nodes.map((n) => [n.id, n]));

  for (const edge of edges) {
    const src = nodeById.get(edge.source);
    const tgt = nodeById.get(edge.target);
    if (!src || !tgt) continue;

    const srcAgent = agentMap.get((src.data as AgentNodeData).agentId);
    const tgtAgent = agentMap.get((tgt.data as AgentNodeData).agentId);
    if (!srcAgent?.output_schema || !tgtAgent?.input_schema) continue;

    const outProps = Object.keys(
      (srcAgent.output_schema as Record<string, unknown> & { properties?: Record<string, unknown> }).properties ?? {}
    );
    const inProps = Object.keys(
      (tgtAgent.input_schema as Record<string, unknown> & { properties?: Record<string, unknown> }).properties ?? {}
    );
    if (outProps.length === 0 || inProps.length === 0) continue;

    const hasMatch = outProps.some((p) => inProps.includes(p));
    if (!hasMatch) {
      conflicts.push({
        id: `schema-${edge.id}`,
        type: "schema_mismatch",
        severity: "warning",
        message: `스키마 불일치: ${srcAgent.name} → ${tgtAgent.name} (공통 필드 없음)`,
      });
    }
  }
  return conflicts;
}

function detectCycles(nodes: Node[], edges: Edge[]): Conflict[] {
  const adj = new Map<string, string[]>();
  nodes.forEach((n) => adj.set(n.id, []));
  edges.forEach((e) => adj.get(e.source)?.push(e.target));

  const visited = new Set<string>();
  const stack = new Set<string>();
  let cycleFound = false;

  function dfs(id: string): boolean {
    visited.add(id);
    stack.add(id);
    for (const nb of adj.get(id) ?? []) {
      if (!visited.has(nb) && dfs(nb)) return true;
      if (stack.has(nb)) { cycleFound = true; return true; }
    }
    stack.delete(id);
    return false;
  }

  nodes.forEach((n) => { if (!visited.has(n.id)) dfs(n.id); });

  return cycleFound
    ? [{ id: "cycle", type: "cycle", severity: "error", message: "순환 참조 감지: 무한 루프가 발생할 수 있습니다." }]
    : [];
}

// ── 에이전트 팔레트 ───────────────────────────────────────────────────────────

const ROLE_COLORS: Record<string, string> = {
  researcher: "bg-blue-100 text-blue-700 border-blue-200",
  writer:     "bg-purple-100 text-purple-700 border-purple-200",
  analyst:    "bg-amber-100 text-amber-700 border-amber-200",
  coder:      "bg-green-100 text-green-700 border-green-200",
};

function AgentPalette({ agents, loading }: { agents: Agent[]; loading: boolean }) {
  function onDragStart(e: React.DragEvent, agent: Agent) {
    e.dataTransfer.setData("application/agentflow-agent", JSON.stringify(agent));
    e.dataTransfer.effectAllowed = "move";
  }

  return (
    <aside className="w-52 shrink-0 flex flex-col border-r border-gray-200 bg-white overflow-y-auto">
      <div className="px-3 py-2.5 border-b border-gray-100">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">에이전트</p>
        <p className="text-[10px] text-gray-400 mt-0.5">캔버스로 드래그하세요</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8 text-gray-400">
          <Loader2 size={16} className="animate-spin" />
        </div>
      ) : agents.length === 0 ? (
        <div className="p-3 text-[11px] text-gray-400 text-center py-8">
          등록된 에이전트가 없습니다.<br />먼저 에이전트를 생성하세요.
        </div>
      ) : (
        <div className="p-2 space-y-1.5">
          {agents.map((agent) => (
            <div
              key={agent.id}
              draggable
              onDragStart={(e) => onDragStart(e, agent)}
              className={`flex items-center gap-2 px-2.5 py-2 rounded-lg border cursor-grab active:cursor-grabbing select-none ${
                ROLE_COLORS[agent.role] ?? "bg-gray-50 text-gray-700 border-gray-200"
              }`}
            >
              <GripVertical size={12} className="shrink-0 opacity-50" />
              <div className="min-w-0">
                <p className="text-xs font-medium truncate">{agent.name}</p>
                <p className="text-[10px] opacity-60 capitalize">{agent.role}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}

// ── 충돌 패널 ─────────────────────────────────────────────────────────────────

function ConflictPanel({ conflicts }: { conflicts: Conflict[] }) {
  const errors = conflicts.filter((c) => c.severity === "error");
  const warnings = conflicts.filter((c) => c.severity === "warning");

  return (
    <aside className="w-56 shrink-0 flex flex-col border-l border-gray-200 bg-white overflow-y-auto">
      <div className="px-3 py-2.5 border-b border-gray-100">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">충돌 감지</p>
      </div>

      <div className="p-3 space-y-2 flex-1">
        {conflicts.length === 0 ? (
          <div className="flex items-center gap-2 text-green-600 text-xs py-2">
            <CheckCircle size={14} />
            <span>문제가 없습니다.</span>
          </div>
        ) : (
          <>
            {errors.map((c) => (
              <div key={c.id} className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 p-2">
                <XCircle size={13} className="text-red-500 shrink-0 mt-0.5" />
                <p className="text-[11px] text-red-700 leading-snug">{c.message}</p>
              </div>
            ))}
            {warnings.map((c) => (
              <div key={c.id} className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 p-2">
                <AlertTriangle size={13} className="text-amber-500 shrink-0 mt-0.5" />
                <p className="text-[11px] text-amber-700 leading-snug">{c.message}</p>
              </div>
            ))}
          </>
        )}
      </div>

      <div className="px-3 py-2 border-t border-gray-100 text-[10px] text-gray-400">
        {errors.length > 0
          ? `${errors.length}개 오류 · ${warnings.length}개 경고`
          : warnings.length > 0
          ? `${warnings.length}개 경고`
          : ""}
      </div>
    </aside>
  );
}

// ── 실행 결과 패널 ────────────────────────────────────────────────────────────

function RunResultPanel({ run, nodes }: { run: WorkflowRun; nodes: Node[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  const completedCount = Object.values(run.node_results).filter((r) => r.status === "completed").length;
  const failedCount    = Object.values(run.node_results).filter((r) => r.status === "failed").length;

  const statusMeta: Record<string, { label: string; cls: string; icon: React.ReactNode }> = {
    pending:   { label: "대기 중", cls: "bg-gray-100 text-gray-600",   icon: null },
    running:   { label: "실행 중", cls: "bg-blue-100 text-blue-700",   icon: <Loader2 size={10} className="animate-spin" /> },
    completed: { label: "완료",    cls: "bg-green-100 text-green-700", icon: <CircleCheck size={10} /> },
    failed:    { label: "실패",    cls: "bg-red-100 text-red-700",     icon: <CircleX size={10} /> },
  };
  const sm = statusMeta[run.status] ?? statusMeta.pending;

  return (
    <div className="border-t border-gray-200 bg-white max-h-64 overflow-y-auto">
      {/* 헤더 */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-gray-100 sticky top-0 bg-white/95 backdrop-blur-sm">
        <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${sm.cls}`}>
          {sm.icon}{sm.label}
        </span>
        <span className="text-xs text-gray-500 flex-1 truncate">{run.task}</span>
        {run.status !== "pending" && run.status !== "running" && (
          <span className="text-xs text-gray-400 shrink-0">
            {completedCount}/{nodes.length} 완료
            {failedCount > 0 && <span className="text-red-500 ml-1">· {failedCount} 실패</span>}
          </span>
        )}
      </div>

      {/* 전체 오류 메시지 */}
      {run.error && (
        <div className="mx-3 mt-2 flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2">
          <XCircle size={13} className="text-red-500 shrink-0 mt-0.5" />
          <p className="text-[11px] text-red-700">{run.error}</p>
        </div>
      )}

      {/* 노드별 결과 */}
      <div className="divide-y divide-gray-50 pb-1">
        {nodes.map((node, idx) => {
          const nr: NodeRunResult | undefined = run.node_results[node.id];
          const label = (node.data as AgentNodeData).label;
          const isOpen = expanded === node.id;
          const hasContent = !!(nr?.result || nr?.error);

          const dotCls = !nr
            ? "bg-gray-200"
            : nr.status === "running"   ? "bg-blue-400 animate-pulse"
            : nr.status === "completed" ? "bg-green-400"
            : nr.status === "failed"    ? "bg-red-400"
            : "bg-gray-300";

          return (
            <div key={node.id} className="px-4 py-2">
              <button
                onClick={() => hasContent && setExpanded(isOpen ? null : node.id)}
                className={`w-full flex items-center gap-2.5 text-left ${hasContent ? "cursor-pointer" : "cursor-default"}`}
              >
                <span className="text-[10px] text-gray-300 w-4 shrink-0 text-right">{idx + 1}</span>
                <span className={`w-2 h-2 rounded-full shrink-0 ${dotCls}`} />
                <span className="text-xs font-medium text-gray-700 flex-1 truncate">{label}</span>
                {nr?.status === "running"   && <Loader2 size={11} className="animate-spin text-blue-500 shrink-0" />}
                {nr?.status === "failed"    && <span className="text-[10px] text-red-500 shrink-0">오류</span>}
                {hasContent && (isOpen
                  ? <ChevronUp size={12} className="text-gray-400 shrink-0" />
                  : <ChevronDown size={12} className="text-gray-400 shrink-0 opacity-0 group-hover:opacity-100" />
                )}
              </button>

              {isOpen && nr?.result && (
                <div className="mt-2 ml-7 text-[11px] text-gray-600 bg-gray-50 rounded-lg p-2.5 max-h-36 overflow-y-auto whitespace-pre-wrap leading-relaxed border border-gray-100">
                  {nr.result}
                </div>
              )}
              {isOpen && nr?.error && (
                <div className="mt-2 ml-7 flex items-start gap-1.5 text-[11px] text-red-700 bg-red-50 rounded-lg p-2.5 border border-red-100">
                  <XCircle size={12} className="shrink-0 mt-0.5" />
                  <span>{nr.error}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── 실행 태스크 입력 모달 ─────────────────────────────────────────────────────

function RunModal({
  onRun,
  onClose,
  running,
}: {
  onRun: (task: string) => void;
  onClose: () => void;
  running: boolean;
}) {
  const [task, setTask] = useState("");

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-5 space-y-4">
        <h3 className="font-semibold text-gray-900">워크플로우 실행</h3>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            작업 내용 <span className="text-gray-400 font-normal">(각 에이전트에 공통으로 전달됩니다)</span>
          </label>
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="예: 경쟁사 분석 보고서를 작성해줘"
            rows={3}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
            autoFocus
          />
        </div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            취소
          </button>
          <button
            disabled={!task.trim() || running}
            onClick={() => onRun(task.trim())}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            실행 시작
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 메인 빌더 ─────────────────────────────────────────────────────────────────

const NODE_TYPES = { agentNode: WorkflowAgentNode };

// ── API 에러 파싱 ─────────────────────────────────────────────────────
function parseApiError(err: unknown): string {
  if (!(err instanceof Error)) return "알 수 없는 오류가 발생했습니다.";
  try {
    const parsed = JSON.parse(err.message);
    if (parsed.detail) return String(parsed.detail);
  } catch { /* JSON 아니면 그대로 사용 */ }
  const msg = err.message;
  if (msg.includes("401")) return "인증이 만료됐습니다. 다시 로그인해주세요.";
  if (msg.includes("403")) return "이 작업을 수행할 권한이 없습니다.";
  if (msg.includes("404")) return "대상을 찾을 수 없습니다.";
  if (msg.includes("500")) return "서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.";
  if (msg.includes("Failed to fetch") || msg.includes("NetworkError"))
    return "서버에 연결할 수 없습니다. 네트워크 상태를 확인해주세요.";
  return msg;
}

// ── 빈 캔버스 안내 ────────────────────────────────────────────────────
function EmptyCanvasHint() {
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
      <div className="text-center select-none">
        <GitMerge size={48} className="mx-auto mb-3 text-gray-200" />
        <p className="text-sm font-medium text-gray-400">왼쪽 패널에서 에이전트를 드래그해 추가하세요</p>
        <p className="text-xs text-gray-300 mt-1">에이전트를 연결해 실행 순서를 정의합니다</p>
      </div>
    </div>
  );
}

function rfToApi(nodes: Node[], edges: Edge[]): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.type ?? "agentNode",
      position: n.position,
      data: n.data as WorkflowNode["data"],
    })),
    edges: edges.map((e) => {
      const edgeData = e.data as { mapping?: EdgeMapping[] } | undefined;
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle ?? null,
        targetHandle: e.targetHandle ?? null,
        ...(edgeData?.mapping?.length ? { data: { mapping: edgeData.mapping } } : {}),
      };
    }),
  };
}

// ── 엣지 매핑 모달 ────────────────────────────────────────────────────────────

function EdgeMappingModal({
  edge,
  sourceNode,
  targetNode,
  sourceAgent,
  targetAgent,
  onSave,
  onClose,
}: {
  edge: Edge;
  sourceNode: Node | undefined;
  targetNode: Node | undefined;
  sourceAgent: Agent | undefined;
  targetAgent: Agent | undefined;
  onSave: (edgeId: string, mapping: EdgeMapping[]) => void;
  onClose: () => void;
}) {
  const existingMapping = ((edge.data as { mapping?: EdgeMapping[] } | undefined)?.mapping) ?? [];
  const [mappings, setMappings] = useState<EdgeMapping[]>(existingMapping);

  const sourceName = (sourceNode?.data as AgentNodeData | undefined)?.label ?? edge.source;
  const targetName = (targetNode?.data as AgentNodeData | undefined)?.label ?? edge.target;

  const sourceFields = Object.keys(
    (sourceAgent?.output_schema as { properties?: Record<string, unknown> } | null | undefined)?.properties ?? {}
  );
  const targetFields = Object.keys(
    (targetAgent?.input_schema as { properties?: Record<string, unknown> } | null | undefined)?.properties ?? {}
  );

  function addRow() {
    setMappings((prev) => [...prev, { from: sourceFields[0] ?? "", to: targetFields[0] ?? "" }]);
  }

  function removeRow(i: number) {
    setMappings((prev) => prev.filter((_, idx) => idx !== i));
  }

  function updateRow(i: number, field: "from" | "to", value: string) {
    setMappings((prev) => prev.map((m, idx) => idx === i ? { ...m, [field]: value } : m));
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-5 space-y-4">
        <div>
          <h3 className="font-semibold text-gray-900 text-base">데이터 매핑 설정</h3>
          <p className="text-xs text-gray-500 mt-0.5 flex items-center gap-1">
            <span className="font-medium text-blue-600">{sourceName}</span>
            <ArrowRight size={12} />
            <span className="font-medium text-purple-600">{targetName}</span>
          </p>
        </div>

        <div className="space-y-2">
          <div className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 text-[11px] font-medium text-gray-500 px-1">
            <span>{sourceName} 출력 필드</span>
            <span />
            <span>{targetName} 입력 필드</span>
            <span />
          </div>

          {mappings.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-3 bg-gray-50 rounded-lg">
              매핑 없음 — 이전 노드 결과 전체가 전달됩니다.
            </p>
          )}

          {mappings.map((m, i) => (
            <div key={i} className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 items-center">
              {sourceFields.length > 0 ? (
                <select
                  value={m.from}
                  onChange={(e) => updateRow(i, "from", e.target.value)}
                  className="text-xs border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
                >
                  {sourceFields.map((f) => <option key={f} value={f}>{f}</option>)}
                </select>
              ) : (
                <input
                  value={m.from}
                  onChange={(e) => updateRow(i, "from", e.target.value)}
                  placeholder="출력 필드명"
                  className="text-xs border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
                />
              )}
              <ArrowRight size={12} className="text-gray-400" />
              {targetFields.length > 0 ? (
                <select
                  value={m.to}
                  onChange={(e) => updateRow(i, "to", e.target.value)}
                  className="text-xs border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-purple-400"
                >
                  {targetFields.map((f) => <option key={f} value={f}>{f}</option>)}
                </select>
              ) : (
                <input
                  value={m.to}
                  onChange={(e) => updateRow(i, "to", e.target.value)}
                  placeholder="입력 필드명"
                  className="text-xs border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-purple-400"
                />
              )}
              <button
                onClick={() => removeRow(i)}
                className="p-1 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}

          <button
            onClick={addRow}
            className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 px-1"
          >
            <Plus size={13} />
            매핑 추가
          </button>
        </div>

        <div className="bg-gray-50 rounded-lg p-3 text-[11px] text-gray-500 space-y-0.5">
          <p>• 매핑을 설정하면 이전 노드의 특정 필드만 다음 노드로 전달됩니다.</p>
          <p>• 매핑이 없으면 이전 노드의 전체 결과가 전달됩니다.</p>
        </div>

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            취소
          </button>
          <button
            onClick={() => { onSave(edge.id, mappings.filter((m) => m.from.trim() && m.to.trim())); onClose(); }}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            저장
          </button>
        </div>
      </div>
    </div>
  );
}

export default function WorkflowBuilder({
  workflowId,
  onBack,
}: {
  workflowId: string | null;
  onBack: () => void;
}) {
  const { data: session } = useSession();
  const token = session?.user?.accessToken;

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [wfName, setWfName] = useState("새 워크플로");
  const [execMode, setExecMode] = useState<"sequential" | "hierarchical">("sequential");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [currentId, setCurrentId] = useState<string | null>(workflowId);
  const [showSaveAsTeam, setShowSaveAsTeam] = useState(false);
  const [teamAgentName, setTeamAgentName] = useState("");

  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const agentMap = useMemo(() => new Map(agents.map((a) => [a.id, a])), [agents]);

  const [showRunModal, setShowRunModal] = useState(false);
  const [running, setRunning] = useState(false);
  const [activeRun, setActiveRun] = useState<WorkflowRun | null>(null);
  const [mappingEdge, setMappingEdge] = useState<Edge | null>(null);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rfInstanceRef = useRef<ReactFlowInstance<any, any> | null>(null);

  // 실제 등록된 에이전트 로드 (팀 우선, 없으면 토큰 포함해 전체 조회)
  useEffect(() => {
    if (token === undefined) return;
    (async () => {
      try {
        const teamId = session?.user?.teamId;
        const list = teamId
          ? await api.getTeamAgents(teamId, {}, token)
          : await api.getAgents(token);
        setAgents(list);
      } finally {
        setAgentsLoading(false);
      }
    })();
  }, [session, token]);

  // 기존 워크플로 로드
  useEffect(() => {
    if (!workflowId || !token) return;
    (async () => {
      const wf: Workflow = await api.getWorkflow(workflowId, token);
      setWfName(wf.name);
      setExecMode((wf.execution_mode as "sequential" | "hierarchical") || "sequential");
      setNodes(wf.nodes as Node[]);
      setEdges(wf.edges as Edge[]);
    })();
  }, [workflowId, token]);

  // 실행 중 2초마다 상태 폴링
  useEffect(() => {
    if (!activeRun || activeRun.status === "completed" || activeRun.status === "failed") return;
    const wfId = currentId;
    if (!wfId) return;

    const interval = setInterval(async () => {
      try {
        const updated = await api.getWorkflowRun(wfId, activeRun.id, token);
        setActiveRun(updated);
        if (updated.status === "completed" || updated.status === "failed") {
          setRunning(false);
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [activeRun, currentId, token]);

  // 엣지 연결
  const onConnect = useCallback(
    (params: Connection) =>
      setEdges((eds) => addEdge({ ...params, id: `e-${Date.now()}` }, eds)),
    [setEdges],
  );

  // 엣지 매핑 저장
  const onSaveMapping = useCallback((edgeId: string, mapping: EdgeMapping[]) => {
    setEdges((eds) =>
      eds.map((e) =>
        e.id === edgeId
          ? { ...e, data: { ...(e.data as object | undefined), mapping } }
          : e
      )
    );
  }, [setEdges]);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }, []);

  // 드롭 → 새 노드 생성
  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const raw = e.dataTransfer.getData("application/agentflow-agent");
      if (!raw || !rfInstanceRef.current) return;
      const agent: Agent = JSON.parse(raw);

      const position = rfInstanceRef.current.screenToFlowPosition({
        x: e.clientX,
        y: e.clientY,
      });

      const newNode: Node = {
        id: `node-${Date.now()}`,
        type: "agentNode",
        position,
        data: {
          agentId: agent.id,
          label: agent.name,
          role: agent.role,
          tags: agent.tags ?? [],
        } satisfies AgentNodeData,
      };
      setNodes((nds) => [...nds, newNode]);
    },
    [setNodes],
  );

  // 저장
  async function handleSave() {
    setSaving(true);
    setSaveMsg(null);
    try {
      const payload = { ...rfToApi(nodes, edges), execution_mode: execMode };
      if (currentId) {
        await api.updateWorkflow(currentId, { name: wfName, ...payload }, token);
      } else {
        const created = await api.createWorkflow({ name: wfName, ...payload }, token);
        setCurrentId(created.id);
      }
      setSaveMsg("저장됨");
      setTimeout(() => setSaveMsg(null), 2000);
    } catch (err) {
      setSaveMsg(parseApiError(err));
    } finally {
      setSaving(false);
    }
  }

  // 실행
  async function handleRun(task: string) {
    let wfId = currentId;

    // 저장되지 않은 워크플로는 먼저 저장
    if (!wfId) {
      try {
        const payload = rfToApi(nodes, edges);
        const created = await api.createWorkflow({ name: wfName, ...payload }, token);
        setCurrentId(created.id);
        wfId = created.id;
      } catch {
        setSaveMsg("실행 전 저장에 실패했습니다.");
        return;
      }
    }

    setShowRunModal(false);
    setRunning(true);

    try {
      const run = await api.runWorkflow(wfId, task, token);
      setActiveRun(run);
    } catch (err) {
      setSaveMsg(parseApiError(err));
      setRunning(false);
    }
  }

  // 충돌 감지
  const conflicts = useMemo<Conflict[]>(() => [
    ...detectCycles(nodes, edges),
    ...detectDuplicates(nodes),
    ...detectSchemaMismatches(edges, nodes, agentMap),
  ], [nodes, edges, agentMap]);

  const conflictNodeIds = useMemo(() => {
    const ids = new Set<string>();
    if (conflicts.some((c) => c.type === "cycle")) {
      nodes.forEach((n) => ids.add(n.id));
    }
    conflicts
      .filter((c) => c.type === "duplicate")
      .forEach((c) => {
        const agentId = c.id.replace("dup-", "");
        nodes.filter((n) => (n.data as AgentNodeData).agentId === agentId).forEach((n) => ids.add(n.id));
      });
    return ids;
  }, [conflicts, nodes]);

  // 노드에 충돌 + 실행 상태 반영
  const displayNodes = useMemo(
    () =>
      nodes.map((n) => ({
        ...n,
        data: {
          ...n.data,
          hasConflict: conflictNodeIds.has(n.id),
          runStatus: activeRun?.node_results[n.id]?.status ?? undefined,
        },
      })),
    [nodes, conflictNodeIds, activeRun],
  );

  const hasErrors = conflicts.some((c) => c.severity === "error");

  return (
    <div className="flex flex-col h-full">
      {/* 툴바 */}
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-200 bg-white shrink-0">
        <button onClick={onBack} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500">
          <ArrowLeft size={16} />
        </button>

        <input
          value={wfName}
          onChange={(e) => setWfName(e.target.value)}
          className="flex-1 text-sm font-semibold text-gray-800 bg-transparent border-0 focus:outline-none focus:ring-1 focus:ring-blue-300 rounded px-1"
        />

        {saveMsg && (
          <span className={`text-xs ${saveMsg === "저장됨" ? "text-green-600" : "text-red-500"}`}>
            {saveMsg}
          </span>
        )}

        {hasErrors && (
          <span className="flex items-center gap-1 text-xs text-red-500">
            <XCircle size={13} />
            {conflicts.filter((c) => c.severity === "error").length}개 오류
          </span>
        )}

        {/* 실행 방식 토글 */}
        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5 text-xs">
          {(["sequential", "hierarchical"] as const).map(mode => (
            <button
              key={mode}
              onClick={() => setExecMode(mode)}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                execMode === mode
                  ? "bg-white text-gray-800 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {mode === "sequential" ? "순차" : "계층"}
            </button>
          ))}
        </div>

        {/* 팀으로 저장 */}
        {currentId && (
          <button
            onClick={() => { setTeamAgentName(wfName + " 팀"); setShowSaveAsTeam(true); }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-purple-600 text-white hover:bg-purple-700 transition-colors"
            title="이 워크플로를 하나의 팀 에이전트로 저장"
          >
            👥 팀으로 저장
          </button>
        )}

        {/* 실행 버튼 */}
        <button
          onClick={() => setShowRunModal(true)}
          disabled={running || nodes.length === 0 || hasErrors}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
        >
          {running ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
          {running ? "실행 중..." : "실행"}
        </button>

        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60 transition-colors"
        >
          {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
          저장
        </button>
      </div>

      {/* 팀으로 저장 모달 */}
      {showSaveAsTeam && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
          onClick={() => setShowSaveAsTeam(false)}>
          <div className="bg-white rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl"
            onClick={e => e.stopPropagation()}>
            <h3 className="font-bold text-lg mb-1">워크플로를 팀 에이전트로 저장</h3>
            <p className="text-sm text-gray-500 mb-4">
              저장된 팀 에이전트는 에이전트 목록에서 하나의 에이전트처럼 사용할 수 있습니다.
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-600 block mb-1">팀 에이전트 이름</label>
                <input
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-400"
                  value={teamAgentName}
                  onChange={e => setTeamAgentName(e.target.value)}
                  placeholder="예: 리서치 팀"
                />
              </div>
              <div className="bg-purple-50 rounded-lg p-3 text-xs text-purple-700">
                <p>• 실행 방식: <strong>{execMode === "sequential" ? "순차 실행" : "계층 실행 (관리자-작업자)"}</strong></p>
                <p>• 노드 수: <strong>{nodes.length}개 에이전트</strong></p>
                <p>• 이 팀 에이전트에 작업을 주면 모든 에이전트가 협력해 완료합니다.</p>
              </div>
            </div>
            <div className="flex gap-3 justify-end mt-4">
              <button onClick={() => setShowSaveAsTeam(false)}
                className="px-4 py-2 border rounded-lg text-sm text-gray-600">취소</button>
              <button
                onClick={async () => {
                  if (!currentId || !teamAgentName.trim()) return;
                  try {
                    await handleSave(); // 최신 상태로 먼저 저장
                    const result = await api.saveWorkflowAsAgent(
                      currentId,
                      { agent_name: teamAgentName },
                      token
                    );
                    alert(result.message);
                    setShowSaveAsTeam(false);
                  } catch (e) {
                    alert("저장 실패: " + (e instanceof Error ? e.message : "오류"));
                  }
                }}
                disabled={!teamAgentName.trim()}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 disabled:opacity-50"
              >
                팀 에이전트 생성
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 3-패널 레이아웃 */}
      <div className="flex flex-1 min-h-0">
        <AgentPalette agents={agents} loading={agentsLoading} />

        {/* React Flow 캔버스 + 실행 결과 패널 */}
        <div className="flex-1 min-w-0 flex flex-col">
          <div className="flex-1 min-h-0 relative" onDragOver={onDragOver} onDrop={onDrop}>
            {nodes.length === 0 && <EmptyCanvasHint />}
            <ReactFlow
              nodes={displayNodes as Node[]}
              edges={edges.map((e) => {
                const hasMappings = ((e.data as { mapping?: EdgeMapping[] } | undefined)?.mapping?.length ?? 0) > 0;
                return hasMappings ? { ...e, style: { stroke: "#7c3aed", strokeWidth: 2 } } : e;
              })}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onEdgeClick={(_, edge) => setMappingEdge(edge)}
              onInit={(instance) => { rfInstanceRef.current = instance; }}
              nodeTypes={NODE_TYPES}
              fitView
              deleteKeyCode="Backspace"
            >
              <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#e5e7eb" />
              <Controls />
              <MiniMap
                nodeColor={(n) => {
                  const role = (n.data as AgentNodeData).role;
                  return role === "researcher" ? "#3b82f6"
                    : role === "writer" ? "#a855f7"
                    : role === "analyst" ? "#f59e0b"
                    : role === "coder" ? "#22c55e"
                    : "#9ca3af";
                }}
                maskColor="rgba(255,255,255,0.7)"
              />
            </ReactFlow>
          </div>

          {/* 실행 결과 패널 (실행 시 표시) */}
          {activeRun && (
            <RunResultPanel run={activeRun} nodes={nodes} />
          )}
        </div>

        <ConflictPanel conflicts={conflicts} />
      </div>

      {/* 실행 태스크 입력 모달 */}
      {showRunModal && (
        <RunModal
          onRun={handleRun}
          onClose={() => setShowRunModal(false)}
          running={running}
        />
      )}

      {/* 엣지 데이터 매핑 모달 */}
      {mappingEdge && (
        <EdgeMappingModal
          edge={mappingEdge}
          sourceNode={nodes.find((n) => n.id === mappingEdge.source)}
          targetNode={nodes.find((n) => n.id === mappingEdge.target)}
          sourceAgent={agentMap.get((nodes.find((n) => n.id === mappingEdge.source)?.data as AgentNodeData | undefined)?.agentId ?? "")}
          targetAgent={agentMap.get((nodes.find((n) => n.id === mappingEdge.target)?.data as AgentNodeData | undefined)?.agentId ?? "")}
          onSave={onSaveMapping}
          onClose={() => setMappingEdge(null)}
        />
      )}
    </div>
  );
}
