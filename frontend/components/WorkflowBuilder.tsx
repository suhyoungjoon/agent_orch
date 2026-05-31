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
import { api, Agent, Workflow, WorkflowNode, WorkflowEdge } from "@/lib/api";
import WorkflowAgentNode, { AgentNodeData } from "./WorkflowAgentNode";
import {
  Save, ArrowLeft, AlertTriangle, CheckCircle,
  XCircle, Loader2, GripVertical,
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

function AgentPalette({
  agents,
  loading,
}: {
  agents: Agent[];
  loading: boolean;
}) {
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
  workflowId: string | null;  // null = new workflow
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

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rfInstanceRef = useRef<ReactFlowInstance<any, any> | null>(null);

  // 에이전트 목록 로드
  useEffect(() => {
    (async () => {
      try {
        const teamId = session?.user?.teamId;
        const list = teamId
          ? await api.getTeamAgents(teamId, {}, token)
          : await api.getAgents();
        setAgents(list);
      } finally {
        setAgentsLoading(false);
      }
    })();
  }, [session]);

  // 기존 워크플로 로드
  useEffect(() => {
    if (!workflowId) return;
    (async () => {
      const wf: Workflow = await api.getWorkflow(workflowId, token);
      setWfName(wf.name);
      setNodes(wf.nodes as Node[]);
      setEdges(wf.edges as Edge[]);
    })();
  }, [workflowId, token]);

  // 엣지 연결
  const onConnect = useCallback(
    (params: Connection) =>
      setEdges((eds) =>
        addEdge({ ...params, id: `e-${Date.now()}` }, eds)
      ),
    [setEdges],
  );

  // 드래그 오버 (기본 동작 방지)
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

  // 충돌 감지 (메모이즈)
  const conflicts = useMemo<Conflict[]>(() => [
    ...detectCycles(nodes, edges),
    ...detectDuplicates(nodes),
    ...detectSchemaMismatches(edges, nodes, agentMap),
  ], [nodes, edges, agentMap]);

  // 충돌 있는 노드 id 집합
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

  // 충돌 플래그를 노드 data에 반영
  const displayNodes = useMemo(
    () =>
      nodes.map((n) => ({
        ...n,
        data: { ...n.data, hasConflict: conflictNodeIds.has(n.id) },
      })),
    [nodes, conflictNodeIds],
  );

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

        {conflicts.some((c) => c.severity === "error") && (
          <span className="flex items-center gap-1 text-xs text-red-500">
            <XCircle size={13} />
            {conflicts.filter((c) => c.severity === "error").length}개 오류
          </span>
        )}

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

        {/* React Flow 캔버스 */}
        <div className="flex-1 min-w-0" onDragOver={onDragOver} onDrop={onDrop}>
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

        <ConflictPanel conflicts={conflicts} />
      </div>
    </div>
  );
}
