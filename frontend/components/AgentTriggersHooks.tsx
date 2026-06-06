"use client";
import { useEffect, useState } from "react";
import { api, Trigger, Hook } from "@/lib/api";

interface Props {
  agentId: string;
  token?: string;
}

const TRIGGER_TYPES = [
  { value: "schedule", label: "⏰ 스케줄 (Cron)", desc: "정해진 시간에 자동 실행" },
  { value: "event",    label: "🔗 이벤트",         desc: "다른 에이전트 완료 시 실행" },
  { value: "webhook",  label: "🌐 웹훅",            desc: "외부 HTTP 요청으로 실행" },
];

const TIMINGS = [
  { value: "before_run", label: "실행 전", color: "text-blue-600 bg-blue-50" },
  { value: "after_run",  label: "실행 후", color: "text-green-600 bg-green-50" },
  { value: "on_error",   label: "오류 시", color: "text-red-600 bg-red-50" },
];

const ACTIONS = [
  { value: "notify",    label: "📣 알림 전송",    desc: "외부 URL로 HTTP 알림" },
  { value: "run_agent", label: "🤖 에이전트 실행", desc: "다른 에이전트를 연쇄 실행" },
  { value: "save_data", label: "💾 데이터 저장",   desc: "결과를 감사 로그에 기록" },
];

export default function AgentTriggersHooks({ agentId, token }: Props) {
  const [tab, setTab] = useState<"triggers" | "hooks">("triggers");
  const [triggers, setTriggers] = useState<Trigger[]>([]);
  const [hooks, setHooks]       = useState<Hook[]>([]);
  const [loading, setLoading]   = useState(true);
  const [showTForm, setShowTForm] = useState(false);
  const [showHForm, setShowHForm] = useState(false);
  const [saving, setSaving] = useState(false);

  // 트리거 폼 상태
  const [tForm, setTForm] = useState({
    name: "", type: "schedule",
    cron: "0 9 * * 1-5", task: "",
    source_agent_id: "", on_status: "completed",
    task_template: "",
  });

  // 훅 폼 상태
  const [hForm, setHForm] = useState({
    name: "", timing: "after_run", action: "notify",
    url: "", method: "POST",
    agent_id_target: "", task_template: "이전 결과를 검토해줘: {{result}}",
    key: "last_result", field: "result",
  });

  const load = async () => {
    setLoading(true);
    try {
      const [ts, hs] = await Promise.all([
        api.getTriggers(agentId, undefined, token),
        api.getHooks(agentId, undefined, token),
      ]);
      setTriggers(ts); setHooks(hs);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (agentId) load(); }, [agentId, token]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 트리거 생성 ──────────────────────────────────────────────────
  const handleCreateTrigger = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      let config: Record<string, string> = {};
      if (tForm.type === "schedule") config = { cron: tForm.cron, task: tForm.task };
      if (tForm.type === "event")    config = { source_agent_id: tForm.source_agent_id, on_status: tForm.on_status, task_template: tForm.task_template };
      if (tForm.type === "webhook")  config = { task_template: tForm.task_template };
      await api.createTrigger({ agent_id: agentId, name: tForm.name, type: tForm.type, config }, token);
      setShowTForm(false);
      setTForm({ name: "", type: "schedule", cron: "0 9 * * 1-5", task: "", source_agent_id: "", on_status: "completed", task_template: "" });
      await load();
    } finally { setSaving(false); }
  };

  // ── 훅 생성 ──────────────────────────────────────────────────────
  const handleCreateHook = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      let config: Record<string, string> = {};
      if (hForm.action === "notify")    config = { url: hForm.url, method: hForm.method };
      if (hForm.action === "run_agent") config = { agent_id: hForm.agent_id_target, task_template: hForm.task_template };
      if (hForm.action === "save_data") config = { key: hForm.key, field: hForm.field };
      await api.createHook({ agent_id: agentId, name: hForm.name, timing: hForm.timing, action: hForm.action, config }, token);
      setShowHForm(false);
      await load();
    } finally { setSaving(false); }
  };

  const toggleTrigger = async (t: Trigger) => {
    await api.updateTrigger(t.id, { enabled: !t.enabled }, token);
    await load();
  };

  const toggleHook = async (h: Hook) => {
    await api.updateHook(h.id, { enabled: !h.enabled }, token);
    await load();
  };

  const deleteTrigger = async (id: string) => {
    if (!confirm("트리거를 삭제할까요?")) return;
    await api.deleteTrigger(id, token);
    await load();
  };

  const deleteHook = async (id: string) => {
    if (!confirm("훅을 삭제할까요?")) return;
    await api.deleteHook(id, token);
    await load();
  };

  const fireTrigger = async (id: string) => {
    await api.fireTrigger(id, token);
    alert("트리거 실행 요청이 접수됐습니다.");
  };

  if (loading) return <p className="text-sm text-gray-400 py-6 text-center">로딩 중…</p>;

  return (
    <div className="space-y-4">
      {/* 탭 */}
      <div className="flex gap-1 border-b">
        {(["triggers", "hooks"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t ? "border-indigo-500 text-indigo-700" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>
            {t === "triggers" ? `트리거 (${triggers.length})` : `훅 (${hooks.length})`}
          </button>
        ))}
      </div>

      {/* ── 트리거 탭 ──────────────────────────────────────────────── */}
      {tab === "triggers" && (
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <p className="text-xs text-gray-500">에이전트를 자동으로 실행하는 조건을 설정합니다.</p>
            <button onClick={() => setShowTForm(true)}
              className="text-xs px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
              + 트리거 추가
            </button>
          </div>

          {showTForm && (
            <form onSubmit={handleCreateTrigger} className="border border-indigo-100 rounded-xl p-4 bg-indigo-50 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-600 block mb-1">이름</label>
                  <input className="w-full border rounded-lg px-3 py-2 text-sm" required
                    value={tForm.name} onChange={e => setTForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="매일 오전 9시 보고서" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600 block mb-1">유형</label>
                  <select className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={tForm.type} onChange={e => setTForm(f => ({ ...f, type: e.target.value }))}>
                    {TRIGGER_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </div>
              </div>

              {tForm.type === "schedule" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">Cron 표현식</label>
                    <input className="w-full border rounded-lg px-3 py-2 text-sm font-mono"
                      value={tForm.cron} onChange={e => setTForm(f => ({ ...f, cron: e.target.value }))}
                      placeholder="0 9 * * 1-5" />
                    <p className="text-xs text-gray-400 mt-1">분 시 일 월 요일 (0=월~6=일)</p>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">실행할 작업</label>
                    <input className="w-full border rounded-lg px-3 py-2 text-sm"
                      value={tForm.task} onChange={e => setTForm(f => ({ ...f, task: e.target.value }))}
                      placeholder="주간 보고서를 작성해줘" />
                  </div>
                </div>
              )}

              {tForm.type === "event" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">소스 에이전트 ID</label>
                    <input className="w-full border rounded-lg px-3 py-2 text-sm font-mono"
                      value={tForm.source_agent_id} onChange={e => setTForm(f => ({ ...f, source_agent_id: e.target.value }))}
                      placeholder="agent-alpha-researcher" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">완료 상태</label>
                    <select className="w-full border rounded-lg px-3 py-2 text-sm"
                      value={tForm.on_status} onChange={e => setTForm(f => ({ ...f, on_status: e.target.value }))}>
                      <option value="completed">완료됐을 때</option>
                      <option value="failed">실패했을 때</option>
                      <option value="*">항상</option>
                    </select>
                  </div>
                  <div className="col-span-2">
                    <label className="text-xs font-medium text-gray-600 block mb-1">작업 템플릿</label>
                    <input className="w-full border rounded-lg px-3 py-2 text-sm"
                      value={tForm.task_template} onChange={e => setTForm(f => ({ ...f, task_template: e.target.value }))}
                      placeholder="{{result}} 를 바탕으로 보고서를 작성해줘" />
                  </div>
                </div>
              )}

              {tForm.type === "webhook" && (
                <div>
                  <label className="text-xs font-medium text-gray-600 block mb-1">작업 템플릿</label>
                  <input className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={tForm.task_template} onChange={e => setTForm(f => ({ ...f, task_template: e.target.value }))}
                    placeholder="{{body.message}} 를 분석해줘" />
                  <p className="text-xs text-gray-400 mt-1">웹훅 수신 후 자동으로 URL이 발급됩니다.</p>
                </div>
              )}

              <div className="flex gap-2 justify-end">
                <button type="button" onClick={() => setShowTForm(false)}
                  className="text-xs px-3 py-1.5 border rounded-lg text-gray-600">취소</button>
                <button type="submit" disabled={saving}
                  className="text-xs px-3 py-1.5 bg-indigo-600 text-white rounded-lg disabled:opacity-50">
                  {saving ? "저장 중…" : "저장"}
                </button>
              </div>
            </form>
          )}

          {triggers.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">등록된 트리거가 없습니다.</p>
          ) : (
            triggers.map(t => (
              <div key={t.id} className="border border-gray-100 rounded-xl p-4 bg-white">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{t.name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        t.type === "schedule" ? "bg-blue-50 text-blue-700" :
                        t.type === "event"    ? "bg-purple-50 text-purple-700" :
                                                "bg-green-50 text-green-700"
                      }`}>{t.type}</span>
                      {!t.enabled && <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">비활성</span>}
                    </div>
                    {t.type === "schedule" && (
                      <p className="text-xs text-gray-500 font-mono mt-1">cron: {(t.config as {cron?: string}).cron}</p>
                    )}
                    {t.type === "webhook" && t.webhook_token && (
                      <p className="text-xs text-gray-500 font-mono mt-1 truncate">
                        POST /api/v1/webhooks/{t.webhook_token}
                      </p>
                    )}
                    {t.last_triggered_at && (
                      <p className="text-xs text-gray-400 mt-1">마지막 실행: {new Date(t.last_triggered_at).toLocaleString("ko-KR")} ({t.trigger_count}회)</p>
                    )}
                  </div>
                  <div className="flex gap-1">
                    <button onClick={() => fireTrigger(t.id)}
                      className="text-xs px-2 py-1 bg-indigo-50 text-indigo-700 rounded hover:bg-indigo-100">▶ 실행</button>
                    <button onClick={() => toggleTrigger(t)}
                      className={`text-xs px-2 py-1 rounded ${t.enabled ? "bg-yellow-50 text-yellow-700 hover:bg-yellow-100" : "bg-green-50 text-green-700 hover:bg-green-100"}`}>
                      {t.enabled ? "비활성화" : "활성화"}
                    </button>
                    <button onClick={() => deleteTrigger(t.id)}
                      className="text-xs px-2 py-1 bg-red-50 text-red-600 rounded hover:bg-red-100">삭제</button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ── 훅 탭 ──────────────────────────────────────────────────── */}
      {tab === "hooks" && (
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <p className="text-xs text-gray-500">실행 전·후·오류 시 자동으로 수행할 액션을 설정합니다.</p>
            <button onClick={() => setShowHForm(true)}
              className="text-xs px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
              + 훅 추가
            </button>
          </div>

          {showHForm && (
            <form onSubmit={handleCreateHook} className="border border-indigo-100 rounded-xl p-4 bg-indigo-50 space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-600 block mb-1">이름</label>
                  <input className="w-full border rounded-lg px-3 py-2 text-sm" required
                    value={hForm.name} onChange={e => setHForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="완료 후 슬랙 알림" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600 block mb-1">시점</label>
                  <select className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={hForm.timing} onChange={e => setHForm(f => ({ ...f, timing: e.target.value }))}>
                    {TIMINGS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600 block mb-1">액션</label>
                  <select className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={hForm.action} onChange={e => setHForm(f => ({ ...f, action: e.target.value }))}>
                    {ACTIONS.map(a => <option key={a.value} value={a.value}>{a.label}</option>)}
                  </select>
                </div>
              </div>

              {hForm.action === "notify" && (
                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <label className="text-xs font-medium text-gray-600 block mb-1">알림 URL</label>
                    <input className="w-full border rounded-lg px-3 py-2 text-sm"
                      value={hForm.url} onChange={e => setHForm(f => ({ ...f, url: e.target.value }))}
                      placeholder="https://hooks.slack.com/..." />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">Method</label>
                    <select className="w-full border rounded-lg px-3 py-2 text-sm"
                      value={hForm.method} onChange={e => setHForm(f => ({ ...f, method: e.target.value }))}>
                      <option>POST</option><option>PUT</option><option>PATCH</option>
                    </select>
                  </div>
                </div>
              )}

              {hForm.action === "run_agent" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">실행할 에이전트 ID</label>
                    <input className="w-full border rounded-lg px-3 py-2 text-sm font-mono"
                      value={hForm.agent_id_target} onChange={e => setHForm(f => ({ ...f, agent_id_target: e.target.value }))}
                      placeholder="agent-alpha-writer" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">작업 템플릿</label>
                    <input className="w-full border rounded-lg px-3 py-2 text-sm"
                      value={hForm.task_template} onChange={e => setHForm(f => ({ ...f, task_template: e.target.value }))} />
                  </div>
                </div>
              )}

              {hForm.action === "save_data" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">저장 키</label>
                    <input className="w-full border rounded-lg px-3 py-2 text-sm font-mono"
                      value={hForm.key} onChange={e => setHForm(f => ({ ...f, key: e.target.value }))} />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">저장할 필드</label>
                    <select className="w-full border rounded-lg px-3 py-2 text-sm"
                      value={hForm.field} onChange={e => setHForm(f => ({ ...f, field: e.target.value }))}>
                      <option value="result">result (최종 결과)</option>
                      <option value="error">error (오류 메시지)</option>
                      <option value="task">task (작업 내용)</option>
                    </select>
                  </div>
                </div>
              )}

              <div className="flex gap-2 justify-end">
                <button type="button" onClick={() => setShowHForm(false)}
                  className="text-xs px-3 py-1.5 border rounded-lg text-gray-600">취소</button>
                <button type="submit" disabled={saving}
                  className="text-xs px-3 py-1.5 bg-indigo-600 text-white rounded-lg disabled:opacity-50">
                  {saving ? "저장 중…" : "저장"}
                </button>
              </div>
            </form>
          )}

          {hooks.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">등록된 훅이 없습니다.</p>
          ) : (
            hooks.map(h => {
              const timing = TIMINGS.find(t => t.value === h.timing);
              const action = ACTIONS.find(a => a.value === h.action);
              return (
                <div key={h.id} className="border border-gray-100 rounded-xl p-4 bg-white">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-sm">{h.name}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${timing?.color}`}>{timing?.label}</span>
                        <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">{action?.label}</span>
                        {!h.enabled && <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">비활성</span>}
                      </div>
                      {h.last_error && (
                        <p className="text-xs text-red-500 mt-1 truncate">⚠️ {h.last_error}</p>
                      )}
                      {h.execution_count > 0 && (
                        <p className="text-xs text-gray-400 mt-1">{h.execution_count}회 실행</p>
                      )}
                    </div>
                    <div className="flex gap-1">
                      <button onClick={() => toggleHook(h)}
                        className={`text-xs px-2 py-1 rounded ${h.enabled ? "bg-yellow-50 text-yellow-700" : "bg-green-50 text-green-700"}`}>
                        {h.enabled ? "비활성화" : "활성화"}
                      </button>
                      <button onClick={() => deleteHook(h.id)}
                        className="text-xs px-2 py-1 bg-red-50 text-red-600 rounded">삭제</button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
