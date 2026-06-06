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
import { api, Agent, Workflow, WorkflowNode, WorkflowEdge, WorkflowRun, NodeRunResult } from "@/lib/api";
import WorkflowAgentNode, { AgentNodeData } from "./WorkflowAgentNode";
import {
  Save, ArrowLeft, AlertTriangle, CheckCircle,
  XCircle, Loader2, GripVertical, Play, ChevronDown, ChevronUp,
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

function RunResultPanel({
  run,
  nodes,
}: {
  run: WorkflowRun;
  nodes: Node[];
}) {
  const [expanded, setExpanded] = useState<string | null>(null);

  const statusColor = {
    pending:   "bg-gray-100 text-gray-600",
    running:   "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    failed:    "bg-red-100 text-red-700",
  };

  return (
    <div className="border-t border-gray-200 bg-white max-h-56 overflow-y-auto">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-100 sticky top-0 bg-white">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${statusColor[run.status]}`}>
          {run.status === "pending" ? "대기중"
           : run.status === "running" ? "실행중"
           : run.status === "completed" ? "완료"
           : "실패"}
        </span>
        <span className="text-xs text-gray-500 flex-1 truncate">작업: {run.task}</span>
        {run.error && (
          <span className="text-xs text-red-500 truncate max-w-xs">{run.error}</span>
        )}
      </div>

      <div className="divide-y divide-gray-50">
        {nodes.map((node) => {
          const nodeResult: NodeRunResult | undefined = run.node_results[node.id];
          const label = (node.data as AgentNodeData).label;
          const isExpanded = expanded === node.id;

          if (!nodeResult) return (
            <div key={node.id} className="flex items-center gap-2 px-4 py-2 text-xs text-gray-400">
              <span className="w-2 h-2 rounded-full bg-gray-200 shrink-0" />
              {label}
            </div>
          );

          return (
            <div key={node.id} className="px-4 py-2">
              <button
                onClick={() => setExpanded(isExpanded ? null : node.id)}
                className="w-full flex items-center gap-2 text-left"
              >
                <span className={`w-2 h-2 rounded-full shrink-0 ${
                  nodeResult.status === "running"   ? "bg-blue-400 animate-pulse"
                  : nodeResult.status === "completed" ? "bg-green-400"
                  : nodeResult.status === "failed"    ? "bg-red-400"
                  : "bg-gray-300"
                }`} />
                <span className="text-xs font-medium text-gray-700 flex-1 truncate">{label}</span>
                {nodeResult.status === "running" && <Loader2 size={11} className="animate-spin text-blue-500" />}
                {nodeResult.result && (
                  isExpanded ? <ChevronUp size={12} className="text-gray-400" /> : <ChevronDown size={12} className="text-gray-400" />
                )}
              </button>

              {isExpanded && nodeResult.result && (
                <div className="mt-2 text-[11px] text-gray-600 bg-gray-50 rounded-lg p-2 max-h-32 overflow-y-auto whitespace-pre-wrap">
                  {nodeResult.result}
                </div>
              )}
              {isExpanded && nodeResult.error && (
                <div className="mt-2 text-[11px] text-red-600 bg-red-50 rounded-lg p-2">
                  {nodeResult.error}
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

function rfToApi(nodes: Node[], edges: Edge[]): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.type ?? "agentNode",
      position: n.position,
      data: n.data as WorkflowNode["data"],
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle ?? null,
      targetHandle: e.targetHandle ?? null,
    })),
  };
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
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [currentId, setCurrentId] = useState<string | null>(workflowId);

  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const agentMap = useMemo(() => new Map(agents.map((a) => [a.id, a])), [agents]);

  const [showRunModal, setShowRunModal] = useState(false);
  const [running, setRunning] = useState(false);
  const [activeRun, setActiveRun] = useState<WorkflowRun | null>(null);

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
      const payload = rfToApi(nodes, edges);
      if (currentId) {
        await api.updateWorkflow(currentId, { name: wfName, ...payload }, token);
      } else {
        const created = await api.createWorkflow({ name: wfName, ...payload }, token);
        setCurrentId(created.id);
      }
      setSaveMsg("저장됨");
      setTimeout(() => setSaveMsg(null), 2000);
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "저장 실패");
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
      setSaveMsg(err instanceof Error ? err.message : "실행 시작 실패");
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

      {/* 3-패널 레이아웃 */}
      <div className="flex flex-1 min-h-0">
        <AgentPalette agents={agents} loading={agentsLoading} />

        {/* React Flow 캔버스 + 실행 결과 패널 */}
        <div className="flex-1 min-w-0 flex flex-col">
          <div className="flex-1 min-h-0" onDragOver={onDragOver} onDrop={onDrop}>
            <ReactFlow
              nodes={displayNodes as Node[]}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
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
    </div>
  );
}
