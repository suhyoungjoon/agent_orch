const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type AgentVisibility = "public" | "team" | "private";

export interface Agent {
  id: string;
  name: string;
  role: "researcher" | "writer" | "analyst" | "coder";
  goal: string;
  backstory: string;
  status: "idle" | "running" | "completed" | "failed";
  description: string | null;
  team_id: string | null;
  visibility: AgentVisibility;
  forked_from: string | null;
  input_schema: Record<string, unknown> | null;
  output_schema: Record<string, unknown> | null;
  tags: string[];
  version: string;
  success_rate: number;
  usage_count: number;
}

export interface Run {
  run_id: string;
  agent_id: string;
  task: string;
  status: "pending" | "pending_approval" | "running" | "completed" | "failed";
  result: string | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  approval_required?: boolean;
  approval_status?: string | null;
  approved_by?: string | null;
  approval_note?: string | null;
  approved_at?: string | null;
}

export interface PendingRun extends Run {
  agent_name: string | null;
  requester_name: string | null;
}

async function request<T>(
  path: string,
  init?: RequestInit,
  token?: string
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { ...headers, ...(init?.headers as Record<string, string> ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface RunRequest {
  task: string;
  context?: string;
  require_approval?: boolean;
}

export interface AgentInput {
  name: string;
  role: string;
  goal: string;
  backstory: string;
  description?: string;
  version?: string;
  tags?: string[];
  team_id?: string | null;
  visibility?: AgentVisibility;
}

export interface TeamAgentsParams {
  search?: string;
  tags?: string;
  visibility?: AgentVisibility;
}

export interface AgentConfig {
  name: string;
  role: string;
  goal: string;
  tools: string[];
  execution_order: number;
}

export interface DashboardSummary {
  total_agents: number;
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  running_runs: number;
  success_rate: number;
  total_tokens: number;
  estimated_cost_usd: number;
}

export interface MemberStat {
  user_id: string;
  name: string;
  email: string;
  runs_count: number;
  tokens_used: number;
  estimated_cost_usd: number;
}

export interface AgentStat {
  agent_id: string;
  name: string;
  role: string;
  usage_count: number;
  success_rate: number;
  total_tokens: number;
  avg_tokens_per_run: number;
  estimated_cost_usd: number;
}

export interface RunLog {
  run_id: string;
  agent_id: string;
  agent_name: string | null;
  task: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  user_name: string | null;
  model: string | null;
}

export interface TeamDashboardData {
  team_id: string;
  team_name: string;
  summary: DashboardSummary;
  member_stats: MemberStat[];
  agent_stats: AgentStat[];
  recent_runs: RunLog[];
}

export interface EnterpriseOverview {
  total_teams: number; total_agents: number; total_workflows: number;
  total_runs: number; completed_runs: number; failed_runs: number; running_runs: number;
  success_rate: number; total_tokens: number; estimated_cost_usd: number;
}
export interface TeamReportStat {
  team_id: string; team_name: string; agent_count: number; workflow_count: number;
  run_count: number; success_rate: number; total_tokens: number; estimated_cost_usd: number;
}
export interface AgentRankEntry {
  agent_id: string; name: string; role: string; team_name: string;
  usage_count: number; success_rate: number; total_tokens: number; estimated_cost_usd: number;
}
export interface SynergyPair {
  agent_a_id: string; agent_a_name: string; agent_a_role: string;
  agent_b_id: string; agent_b_name: string; agent_b_role: string;
  workflow_count: number;
}
export interface ModelCostStat {
  model: string; run_count: number; total_tokens: number;
  estimated_cost_usd: number; cost_share: number;
}
export interface DailyRunStat {
  date: string; run_count: number; success_count: number;
  total_tokens: number; estimated_cost_usd: number;
}
export interface EnterpriseReportData {
  generated_at: string;
  overview: EnterpriseOverview;
  team_stats: TeamReportStat[];
  top_agents: AgentRankEntry[];
  synergy_pairs: SynergyPair[];
  model_cost_stats: ModelCostStat[];
  daily_run_stats: DailyRunStat[];
}

export interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: { agentId: string; label: string; role: string; tags?: string[] };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
}

export interface Workflow {
  id: string;
  name: string;
  description: string | null;
  team_id: string | null;
  created_by: string | null;
  status: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreate {
  name: string;
  description?: string;
  nodes?: WorkflowNode[];
  edges?: WorkflowEdge[];
}

export interface SynergyCandidate {
  agent: Agent;
  score: number;
  tag_score: number;
  schema_forward_score: number;
  schema_reverse_score: number;
  reasons: string[];
  suggested_flow: "before" | "after" | "parallel" | null;
}

export interface SynergyResponse {
  source_agent_id: string;
  candidates: SynergyCandidate[];
  claude_analysis: string | null;
  is_mock_analysis: boolean;
}

export interface ParseIntentResult {
  agents: AgentConfig[];
  raw_input: string;
  model_used: string | null;
  is_mock: boolean;
}

export const api = {
  getAgents: () => request<Agent[]>("/api/v1/agents/"),
  getAgent: (id: string) => request<Agent>(`/api/v1/agents/${id}`),
  runAgent: (id: string, task: string, context?: string, token?: string, requireApproval?: boolean) =>
    request<Run>(
      `/api/v1/agents/${id}/run`,
      { method: "POST", body: JSON.stringify({ task, context, require_approval: requireApproval ?? false }) },
      token
    ),
  getPendingRuns: (token?: string) =>
    request<PendingRun[]>("/api/v1/runs/pending", undefined, token),
  approveRun: (runId: string, note?: string, token?: string) =>
    request<Run>(`/api/v1/runs/${runId}/approve`, { method: "POST", body: JSON.stringify({ note: note ?? null }) }, token),
  rejectRun: (runId: string, note?: string, token?: string) =>
    request<Run>(`/api/v1/runs/${runId}/reject`, { method: "POST", body: JSON.stringify({ note: note ?? null }) }, token),
  getRun: (runId: string) => request<Run>(`/api/v1/runs/${runId}`),
  getRuns: () => request<Run[]>("/api/v1/runs/"),
  parseIntent: (text: string, token?: string) =>
    request<ParseIntentResult>(
      "/api/v1/parse-intent/",
      { method: "POST", body: JSON.stringify({ text }) },
      token
    ),
  createAgent: (data: AgentInput, token?: string) =>
    request<Agent>("/api/v1/agents/", {
      method: "POST",
      body: JSON.stringify(data),
    }, token),
  updateAgent: (id: string, data: Partial<AgentInput>, token?: string) =>
    request<Agent>(`/api/v1/agents/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }, token),
  deleteAgent: (id: string, token?: string) =>
    request<void>(`/api/v1/agents/${id}`, { method: "DELETE" }, token),
  getPublicAgents: (params?: Omit<TeamAgentsParams, "visibility">) => {
    const q = new URLSearchParams({ visibility: "public" });
    if (params?.search) q.set("search", params.search);
    if (params?.tags) q.set("tags", params.tags);
    return request<Agent[]>(`/api/v1/agents/?${q}`);
  },
  getTeamAgents: (teamId: string, params?: TeamAgentsParams, token?: string) => {
    const q = new URLSearchParams();
    if (params?.search) q.set("search", params.search);
    if (params?.tags) q.set("tags", params.tags);
    if (params?.visibility) q.set("visibility", params.visibility);
    return request<Agent[]>(`/api/v1/teams/${teamId}/agents?${q}`, undefined, token);
  },
  forkAgent: (id: string, token?: string) =>
    request<Agent>(`/api/v1/agents/${id}/fork`, { method: "POST" }, token),
  updateVisibility: (id: string, visibility: AgentVisibility, token?: string) =>
    request<Agent>(
      `/api/v1/agents/${id}/visibility`,
      { method: "PATCH", body: JSON.stringify({ visibility }) },
      token
    ),
  getDashboard: (teamId: string, token?: string) =>
    request<TeamDashboardData>(`/api/v1/teams/${teamId}/dashboard`, undefined, token),
  getWorkflows: (token?: string) =>
    request<Workflow[]>("/api/v1/workflows/", undefined, token),
  createWorkflow: (data: WorkflowCreate, token?: string) =>
    request<Workflow>("/api/v1/workflows/", { method: "POST", body: JSON.stringify(data) }, token),
  getWorkflow: (id: string, token?: string) =>
    request<Workflow>(`/api/v1/workflows/${id}`, undefined, token),
  updateWorkflow: (id: string, data: Partial<WorkflowCreate & { status?: string }>, token?: string) =>
    request<Workflow>(`/api/v1/workflows/${id}`, { method: "PATCH", body: JSON.stringify(data) }, token),
  deleteWorkflow: (id: string, token?: string) =>
    request<void>(`/api/v1/workflows/${id}`, { method: "DELETE" }, token),
  getEnterpriseReport: (token?: string) =>
    request<EnterpriseReportData>("/api/v1/reports/enterprise", undefined, token),
  getSynergy: (agentId: string, opts?: { limit?: number; useClaude?: boolean }, token?: string) => {
    const q = new URLSearchParams();
    if (opts?.limit) q.set("limit", String(opts.limit));
    if (opts?.useClaude) q.set("use_claude", "true");
    return request<SynergyResponse>(`/api/v1/agents/${agentId}/synergy?${q}`, undefined, token);
  },
};
