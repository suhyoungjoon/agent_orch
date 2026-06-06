"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  Save, Play, ChevronDown, ChevronUp, Info,
  Loader2, CheckCircle, XCircle, RotateCcw, Cpu,
} from "lucide-react";
import { api, Agent, LLMProvider, MemoryType, StudioAgentInput } from "@/lib/api";
import AgentTriggersHooks from "./AgentTriggersHooks";

// ── 모델 카탈로그 ────────────────────────────────────────────────────
const MODEL_CATALOG: Record<LLMProvider, { label: string; models: { id: string; label: string; supportsTemp: boolean; supportsTopP: boolean }[] }> = {
  claude: {
    label: "Anthropic Claude",
    models: [
      { id: "claude-opus-4-8",          label: "Claude Opus 4.8",    supportsTemp: true,  supportsTopP: false },
      { id: "claude-sonnet-4-6",         label: "Claude Sonnet 4.6",  supportsTemp: true,  supportsTopP: false },
      { id: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5",   supportsTemp: true,  supportsTopP: false },
    ],
  },
  openai: {
    label: "OpenAI",
    models: [
      { id: "gpt-4o",       label: "GPT-4o",       supportsTemp: true, supportsTopP: true },
      { id: "gpt-4o-mini",  label: "GPT-4o Mini",  supportsTemp: true, supportsTopP: true },
      { id: "gpt-4-turbo",  label: "GPT-4 Turbo",  supportsTemp: true, supportsTopP: true },
      { id: "o1-preview",   label: "o1 Preview",   supportsTemp: false, supportsTopP: false },
    ],
  },
  gemini: {
    label: "Google Gemini",
    models: [
      { id: "gemini-1.5-pro",   label: "Gemini 1.5 Pro",   supportsTemp: true, supportsTopP: true },
      { id: "gemini-1.5-flash", label: "Gemini 1.5 Flash",  supportsTemp: true, supportsTopP: true },
      { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash",  supportsTemp: true, supportsTopP: true },
    ],
  },
  local: {
    label: "로컬 모델",
    models: [
      { id: "local", label: "로컬 엔드포인트", supportsTemp: true, supportsTopP: true },
    ],
  },
};

// ── 메모리 타입 ──────────────────────────────────────────────────────
const MEMORY_OPTIONS: { value: MemoryType; label: string; desc: string }[] = [
  { value: "none",  label: "없음",     desc: "각 실행 독립 — 이전 실행 기억 없음" },
  { value: "short", label: "단기 메모리", desc: "실행 세션 내 문맥 유지" },
  { value: "long",  label: "장기 메모리", desc: "DB에 기록, 여러 세션에 걸쳐 기억 유지" },
];

const AVAILABLE_TOOLS = ["web_search", "calculate", "get_current_datetime", "fetch_webpage"];

// ── 초기 폼 상태 ─────────────────────────────────────────────────────
function emptyForm(): FormState {
  return {
    name: "", role: "", goal: "", backstory: "", description: "",
    version: "1.0.0", visibility: "team", tags: "",
    llm_provider: "claude",
    model_name: "claude-sonnet-4-6",
    temperature: "1.0", max_tokens: "4096", top_p: "",
    system_prompt: "",
    memory_type: "none", context_window_size: "",
    max_retries: "3", timeout_seconds: "120",
  };
}

function agentToForm(a: Agent): FormState {
  return {
    name: a.name, role: a.role, goal: a.goal,
    backstory: a.backstory, description: a.description ?? "",
    version: a.version, visibility: a.visibility,
    tags: (a.tags ?? []).join(", "),
    llm_provider: a.llm_provider ?? "claude",
    model_name: a.model_name ?? "claude-sonnet-4-6",
    temperature: a.temperature != null ? String(a.temperature) : "1.0",
    max_tokens: a.max_tokens != null ? String(a.max_tokens) : "4096",
    top_p: a.top_p != null ? String(a.top_p) : "",
    system_prompt: a.system_prompt ?? "",
    memory_type: a.memory_type ?? "none",
    context_window_size: a.context_window_size != null ? String(a.context_window_size) : "",
    max_retries: String(a.max_retries ?? 3),
    timeout_seconds: String(a.timeout_seconds ?? 120),
  };
}

interface FormState {
  name: string; role: string; goal: string; backstory: string;
  description: string; version: string; visibility: string; tags: string;
  llm_provider: string; model_name: string;
  temperature: string; max_tokens: string; top_p: string;
  system_prompt: string;
  memory_type: string; context_window_size: string;
  max_retries: string; timeout_seconds: string;
}

// ── 메인 컴포넌트 ────────────────────────────────────────────────────
interface Props {
  agentId?: string;  // 편집 모드
}

export default function AgentStudio({ agentId }: Props) {
  const { data: session } = useSession();
  const router = useRouter();
  const token = session?.user?.accessToken;

  const [tab, setTab] = useState<"basic" | "advanced" | "triggers">("basic");
  const [form, setForm] = useState<FormState>(emptyForm());
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set(AVAILABLE_TOOLS));
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [loadingAgent, setLoadingAgent] = useState(false);

  // 테스트 플레이그라운드
  const [testTask, setTestTask] = useState("");
  const [testRunId, setTestRunId] = useState<string | null>(null);
  const [testStatus, setTestStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [testResult, setTestResult] = useState<string>("");
  const [testError, setTestError] = useState<string>("");
  const [savedAgentId, setSavedAgentId] = useState<string | null>(agentId ?? null);

  // 편집 모드: 기존 에이전트 로드
  useEffect(() => {
    if (!agentId) return;
    setLoadingAgent(true);
    api.getAgent(agentId)
      .then((a) => setForm(agentToForm(a)))
      .catch(() => {})
      .finally(() => setLoadingAgent(false));
  }, [agentId]);

  // 현재 선택된 모델의 capabilities
  const providerCatalog = MODEL_CATALOG[form.llm_provider as LLMProvider] ?? MODEL_CATALOG.claude;
  const modelInfo = providerCatalog.models.find((m) => m.id === form.model_name) ?? providerCatalog.models[0];

  function set(k: keyof FormState, v: string) {
    setForm((p) => ({ ...p, [k]: v }));
  }

  function toggleTool(name: string) {
    setSelectedTools((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }

  function buildPayload(): StudioAgentInput {
    const tags = form.tags.split(",").map((t) => t.trim()).filter(Boolean);
    const temperature = form.temperature ? parseFloat(form.temperature) : null;
    const max_tokens = form.max_tokens ? parseInt(form.max_tokens) : null;
    const top_p = form.top_p ? parseFloat(form.top_p) : null;
    const context_window_size = form.context_window_size ? parseInt(form.context_window_size) : null;
    return {
      name: form.name.trim(),
      role: form.role.trim(),
      goal: form.goal.trim(),
      backstory: form.backstory.trim(),
      description: form.description.trim() || undefined,
      version: form.version.trim() || "1.0.0",
      visibility: form.visibility as StudioAgentInput["visibility"],
      tags,
      is_studio_agent: true,
      llm_provider: form.llm_provider as LLMProvider,
      model_name: form.model_name || null,
      temperature: modelInfo?.supportsTemp ? temperature : null,
      max_tokens,
      top_p: modelInfo?.supportsTopP ? top_p : null,
      system_prompt: form.system_prompt.trim() || null,
      memory_type: form.memory_type as MemoryType,
      context_window_size,
      max_retries: parseInt(form.max_retries) || 3,
      timeout_seconds: parseInt(form.timeout_seconds) || 120,
    };
  }

  async function handleSave() {
    if (!form.name.trim() || !form.role.trim() || !form.goal.trim() || !form.backstory.trim()) {
      setSaveError("이름, 역할, 목표, 배경은 필수입니다.");
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const payload = buildPayload();
      let result: Agent;
      if (savedAgentId) {
        result = await api.updateStudioAgent(savedAgentId, payload, token);
      } else {
        result = await api.createStudioAgent(payload, token);
        setSavedAgentId(result.id);
        router.replace(`/studio/${result.id}`);
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    if (!testTask.trim()) return;
    if (!savedAgentId) {
      setSaveError("먼저 저장해야 테스트할 수 있습니다.");
      return;
    }
    setTestStatus("running");
    setTestResult("");
    setTestError("");
    setTestRunId(null);
    try {
      const run = await api.runAgent(savedAgentId, testTask, undefined, token);
      setTestRunId(run.run_id);
      pollTestResult(run.run_id);
    } catch (e) {
      setTestStatus("error");
      setTestError(e instanceof Error ? e.message : "실행 실패");
    }
  }

  function pollTestResult(runId: string) {
    const iv = setInterval(async () => {
      try {
        const run = await api.getRun(runId);
        if (run.status === "completed") {
          clearInterval(iv);
          setTestStatus("done");
          setTestResult(run.result ?? "");
        } else if (run.status === "failed") {
          clearInterval(iv);
          setTestStatus("error");
          setTestError(run.error ?? "실행 실패");
        }
      } catch {
        clearInterval(iv);
        setTestStatus("error");
        setTestError("결과 조회 실패");
      }
    }, 2000);
  }

  if (loadingAgent) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-400">
        <Loader2 size={20} className="animate-spin mr-2" />
        에이전트 로딩 중...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-0 h-full">
      {/* ── 헤더 툴바 ── */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-3">
          <Cpu size={18} className="text-violet-600" />
          <span className="font-semibold text-gray-800">
            {savedAgentId ? `편집: ${form.name || "에이전트"}` : "새 에이전트 스튜디오"}
          </span>
          {form.version && (
            <span className="text-xs text-gray-400 font-mono">v{form.version}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {saveError && <span className="text-xs text-red-500">{saveError}</span>}
          {saved && (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <CheckCircle size={13} /> 저장됨
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 disabled:opacity-50 transition-colors"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            저장
          </button>
        </div>
      </div>

      {/* ── 본문: 좌(설정) + 우(테스트) ── */}
      <div className="flex flex-1 overflow-hidden min-h-0">

        {/* ── 좌측 설정 패널 ── */}
        <div className="w-1/2 border-r border-gray-200 overflow-y-auto bg-white">
          {/* 탭 */}
          <div className="flex border-b border-gray-200 sticky top-0 bg-white z-10">
            {(["basic", "advanced", "triggers"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  tab === t
                    ? "border-violet-600 text-violet-700"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                {t === "basic" ? "기본 설정" : t === "advanced" ? "고급 설정" : "트리거 & 훅"}
              </button>
            ))}
          </div>

          <div className="p-5 space-y-5">
            {tab === "basic" ? (
              <BasicTab form={form} set={set} />
            ) : tab === "triggers" ? (
              savedAgentId ? (
                <AgentTriggersHooks agentId={savedAgentId} token={token ?? undefined} />
              ) : (
                <p className="text-sm text-gray-400 text-center py-8">먼저 에이전트를 저장해야 트리거/훅을 설정할 수 있습니다.</p>
              )
            ) : (
              <AdvancedTab
                form={form}
                set={set}
                providerCatalog={providerCatalog}
                modelInfo={modelInfo}
                selectedTools={selectedTools}
                toggleTool={toggleTool}
              />
            )}
          </div>
        </div>

        {/* ── 우측 테스트 패널 ── */}
        <div className="w-1/2 flex flex-col bg-gray-50">
          <div className="px-5 py-3 border-b border-gray-200 bg-white">
            <span className="text-sm font-semibold text-gray-700">테스트 플레이그라운드</span>
          </div>

          <div className="flex flex-col flex-1 p-5 gap-4 overflow-y-auto">
            {/* 태스크 입력 */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">태스크</label>
              <textarea
                value={testTask}
                onChange={(e) => setTestTask(e.target.value)}
                placeholder="이 에이전트에게 시킬 작업을 입력하세요..."
                rows={3}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400 resize-none"
              />
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleTest}
                disabled={testStatus === "running" || !testTask.trim()}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
              >
                {testStatus === "running"
                  ? <Loader2 size={14} className="animate-spin" />
                  : <Play size={14} />}
                {testStatus === "running" ? "실행 중..." : "실행"}
              </button>
              {testStatus !== "idle" && (
                <button
                  onClick={() => { setTestStatus("idle"); setTestResult(""); setTestError(""); }}
                  className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600"
                >
                  <RotateCcw size={12} /> 초기화
                </button>
              )}
              {testRunId && (
                <span className="text-xs text-gray-400 font-mono">{testRunId.slice(0, 12)}…</span>
              )}
            </div>

            {/* 결과 */}
            {testStatus === "running" && (
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
                <div className="flex items-center gap-2 text-blue-600 text-sm">
                  <Loader2 size={14} className="animate-spin" />
                  에이전트 실행 중... (2초마다 폴링)
                </div>
              </div>
            )}
            {testStatus === "done" && testResult && (
              <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                <div className="flex items-center gap-1.5 text-green-700 text-xs font-medium mb-2">
                  <CheckCircle size={13} /> 완료
                </div>
                <pre className="text-sm text-gray-800 whitespace-pre-wrap font-sans leading-relaxed">
                  {testResult}
                </pre>
              </div>
            )}
            {testStatus === "error" && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                <div className="flex items-center gap-1.5 text-red-600 text-xs font-medium mb-1">
                  <XCircle size={13} /> 실패
                </div>
                <p className="text-sm text-red-700">{testError}</p>
              </div>
            )}

            {/* 현재 설정 요약 */}
            <div className="rounded-lg border border-gray-200 bg-white p-4 text-xs text-gray-500 space-y-1 mt-auto">
              <p className="font-medium text-gray-700 mb-2">현재 설정 요약</p>
              <p>제공자: <span className="text-gray-800 font-mono">{form.llm_provider}</span></p>
              <p>모델: <span className="text-gray-800 font-mono">{form.model_name || "(기본값)"}</span></p>
              {form.temperature && <p>Temperature: <span className="text-gray-800">{form.temperature}</span></p>}
              {form.max_tokens && <p>Max Tokens: <span className="text-gray-800">{form.max_tokens}</span></p>}
              <p>메모리: <span className="text-gray-800">{form.memory_type}</span></p>
              <p>타임아웃: <span className="text-gray-800">{form.timeout_seconds}s</span></p>
              <p>시스템 프롬프트: <span className="text-gray-800">{form.system_prompt ? "직접 지정" : "자동 생성"}</span></p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── 기본 탭 ──────────────────────────────────────────────────────────
function BasicTab({ form, set }: { form: FormState; set: (k: keyof FormState, v: string) => void }) {
  return (
    <>
      <Field label="에이전트 이름 *">
        <input
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="예: 시장 리서처"
          className={inputCls}
        />
      </Field>

      <Field label="역할 *" hint="researcher, writer, analyst, coder 등 자유 입력">
        <input
          value={form.role}
          onChange={(e) => set("role", e.target.value)}
          placeholder="예: researcher"
          className={inputCls}
        />
      </Field>

      <Field label="목표 *" hint="이 에이전트가 달성해야 할 목표">
        <textarea
          value={form.goal}
          onChange={(e) => set("goal", e.target.value)}
          placeholder="예: 주어진 주제에 대해 신뢰할 수 있는 정보를 수집하고 정리한다."
          rows={3}
          className={`${inputCls} resize-none`}
        />
      </Field>

      <Field label="배경(Backstory) *" hint="에이전트의 전문성과 접근 방식 설명">
        <textarea
          value={form.backstory}
          onChange={(e) => set("backstory", e.target.value)}
          placeholder="예: 10년 경력의 시장 분석가로, 다양한 업계 리서치 경험을 보유하고 있다."
          rows={3}
          className={`${inputCls} resize-none`}
        />
      </Field>

      <Field label="설명 (선택)">
        <input
          value={form.description}
          onChange={(e) => set("description", e.target.value)}
          placeholder="레지스트리에 표시되는 짧은 설명"
          className={inputCls}
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="버전">
          <input
            value={form.version}
            onChange={(e) => set("version", e.target.value)}
            placeholder="1.0.0"
            className={inputCls}
          />
        </Field>
        <Field label="공개 범위">
          <select
            value={form.visibility}
            onChange={(e) => set("visibility", e.target.value)}
            className={inputCls}
          >
            <option value="team">팀 공개</option>
            <option value="public">전체 공개</option>
            <option value="private">비공개</option>
          </select>
        </Field>
      </div>

      <Field label="태그" hint="쉼표로 구분">
        <input
          value={form.tags}
          onChange={(e) => set("tags", e.target.value)}
          placeholder="예: 검색, 분석, 리서치"
          className={inputCls}
        />
      </Field>
    </>
  );
}

// ── 고급 탭 ──────────────────────────────────────────────────────────
function AdvancedTab({
  form, set, providerCatalog, modelInfo, selectedTools, toggleTool,
}: {
  form: FormState;
  set: (k: keyof FormState, v: string) => void;
  providerCatalog: (typeof MODEL_CATALOG)[LLMProvider];
  modelInfo: { id: string; label: string; supportsTemp: boolean; supportsTopP: boolean } | undefined;
  selectedTools: Set<string>;
  toggleTool: (name: string) => void;
}) {
  const [showPromptHelp, setShowPromptHelp] = useState(false);

  return (
    <>
      {/* ── LLM 제공자 ── */}
      <Section title="LLM 설정">
        <Field label="제공자">
          <select
            value={form.llm_provider}
            onChange={(e) => {
              set("llm_provider", e.target.value);
              const first = MODEL_CATALOG[e.target.value as LLMProvider]?.models[0]?.id ?? "";
              set("model_name", first);
            }}
            className={inputCls}
          >
            {(Object.keys(MODEL_CATALOG) as LLMProvider[]).map((p) => (
              <option key={p} value={p}>{MODEL_CATALOG[p].label}</option>
            ))}
          </select>
        </Field>

        <Field label="모델">
          <select
            value={form.model_name}
            onChange={(e) => set("model_name", e.target.value)}
            className={inputCls}
          >
            {providerCatalog.models.map((m) => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </select>
          {form.llm_provider !== "claude" && (
            <p className="mt-1 text-xs text-amber-600">⚠ Claude 외 제공자는 현재 Mock 응답을 반환합니다.</p>
          )}
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field
            label={`Temperature ${modelInfo?.supportsTemp ? "" : "(미지원)"}`}
            hint="0 = 결정적, 2 = 창의적"
            disabled={!modelInfo?.supportsTemp}
          >
            <input
              type="number" min="0" max="2" step="0.1"
              value={form.temperature}
              onChange={(e) => set("temperature", e.target.value)}
              disabled={!modelInfo?.supportsTemp}
              placeholder="1.0"
              className={inputCls}
            />
          </Field>
          <Field label="Max Tokens" hint="최대 출력 토큰 수">
            <input
              type="number" min="256" max="32768" step="256"
              value={form.max_tokens}
              onChange={(e) => set("max_tokens", e.target.value)}
              placeholder="4096"
              className={inputCls}
            />
          </Field>
        </div>

        <Field
          label={`Top-p ${modelInfo?.supportsTopP ? "" : "(미지원)"}`}
          hint="0~1, 낮을수록 집중된 응답"
          disabled={!modelInfo?.supportsTopP}
        >
          <input
            type="number" min="0" max="1" step="0.05"
            value={form.top_p}
            onChange={(e) => set("top_p", e.target.value)}
            disabled={!modelInfo?.supportsTopP}
            placeholder="(기본값 사용)"
            className={inputCls}
          />
        </Field>
      </Section>

      {/* ── 시스템 프롬프트 ── */}
      <Section title="시스템 프롬프트">
        <div className="flex items-center justify-between mb-1">
          <p className="text-xs text-gray-500">비어 있으면 역할/목표/배경으로 자동 생성됩니다.</p>
          <button
            onClick={() => setShowPromptHelp((v) => !v)}
            className="text-xs text-blue-500 flex items-center gap-1"
          >
            <Info size={11} />
            사용 가능한 변수
            {showPromptHelp ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
          </button>
        </div>
        {showPromptHelp && (
          <div className="rounded-lg bg-blue-50 border border-blue-200 p-3 text-xs text-blue-700 mb-2 font-mono leading-relaxed">
            <p>이 필드는 현재 Claude에만 직접 전달됩니다.</p>
            <p className="mt-1 text-blue-500">자동 생성 형식:</p>
            <p>You are a {"{role}"}.</p>
            <p>Goal: {"{goal}"}</p>
            <p>Background: {"{backstory}"}</p>
          </div>
        )}
        <textarea
          value={form.system_prompt}
          onChange={(e) => set("system_prompt", e.target.value)}
          placeholder="직접 시스템 프롬프트를 입력하거나 비워두면 자동 생성됩니다."
          rows={6}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-violet-400 resize-y"
        />
      </Section>

      {/* ── 툴 설정 ── */}
      <Section title="사용 가능한 툴">
        <p className="text-xs text-gray-500 mb-2">선택된 툴만 에이전트가 호출할 수 있습니다.</p>
        <div className="space-y-2">
          {AVAILABLE_TOOLS.map((tool) => (
            <label key={tool} className="flex items-center gap-2.5 cursor-pointer group">
              <input
                type="checkbox"
                checked={selectedTools.has(tool)}
                onChange={() => toggleTool(tool)}
                className="rounded accent-violet-600 w-3.5 h-3.5"
              />
              <span className="text-sm text-gray-700 font-mono group-hover:text-gray-900">{tool}</span>
            </label>
          ))}
        </div>
      </Section>

      {/* ── 메모리 ── */}
      <Section title="메모리 설정">
        <div className="space-y-2">
          {MEMORY_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={`flex items-start gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                form.memory_type === opt.value
                  ? "border-violet-400 bg-violet-50"
                  : "border-gray-200 hover:border-gray-300"
              }`}
            >
              <input
                type="radio"
                name="memory_type"
                value={opt.value}
                checked={form.memory_type === opt.value}
                onChange={(e) => set("memory_type", e.target.value)}
                className="mt-0.5 accent-violet-600"
              />
              <div>
                <p className="text-sm font-medium text-gray-800">{opt.label}</p>
                <p className="text-xs text-gray-500 mt-0.5">{opt.desc}</p>
              </div>
            </label>
          ))}
        </div>
        {form.memory_type !== "none" && (
          <Field label="컨텍스트 윈도우 크기 (토큰)" hint="메모리 유지 범위">
            <input
              type="number"
              value={form.context_window_size}
              onChange={(e) => set("context_window_size", e.target.value)}
              placeholder="예: 8000"
              className={inputCls}
            />
          </Field>
        )}
      </Section>

      {/* ── 실행 설정 ── */}
      <Section title="실행 설정">
        <div className="grid grid-cols-2 gap-3">
          <Field label="최대 재시도 횟수" hint="ReAct 루프 반복 상한">
            <input
              type="number" min="1" max="20"
              value={form.max_retries}
              onChange={(e) => set("max_retries", e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label="타임아웃 (초)">
            <input
              type="number" min="10" max="600"
              value={form.timeout_seconds}
              onChange={(e) => set("timeout_seconds", e.target.value)}
              className={inputCls}
            />
          </Field>
        </div>
      </Section>
    </>
  );
}

// ── 공통 UI 헬퍼 ─────────────────────────────────────────────────────
const inputCls =
  "w-full rounded-lg border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400 disabled:bg-gray-100 disabled:text-gray-400";

function Field({
  label, hint, children, disabled,
}: {
  label: string; hint?: string; children: React.ReactNode; disabled?: boolean;
}) {
  return (
    <div className={disabled ? "opacity-50" : ""}>
      <label className="block text-xs font-medium text-gray-700 mb-1">
        {label}
        {hint && <span className="ml-1.5 font-normal text-gray-400">— {hint}</span>}
      </label>
      {children}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 pb-1 border-b border-gray-100">
        {title}
      </h3>
      <div className="space-y-4">{children}</div>
    </div>
  );
}
