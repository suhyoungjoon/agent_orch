"use client";
import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import AppHeader from "@/components/AppHeader";
import { api, MCPServer, MCPTool } from "@/lib/api";
import { ErrorBanner, CardGridSkeleton } from "@/components/ui-shared";
import { Server } from "lucide-react";

const STATUS_COLOR: Record<string, string> = {
  online:  "bg-green-100 text-green-800 border-green-200",
  offline: "bg-gray-100 text-gray-600 border-gray-200",
  error:   "bg-red-100 text-red-700 border-red-200",
  unknown: "bg-yellow-100 text-yellow-700 border-yellow-200",
};

const STATUS_DOT: Record<string, string> = {
  online:  "bg-green-500",
  offline: "bg-gray-400",
  error:   "bg-red-500",
  unknown: "bg-yellow-400",
};

export default function MCPPage() {
  const { data: session } = useSession();
  const token = (session as { accessToken?: string } | null)?.accessToken;

  const [servers, setServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", endpoint: "", description: "" });
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [selectedServer, setSelectedServer] = useState<MCPServer | null>(null);
  const [tools, setTools] = useState<MCPTool[]>([]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMCPServers(token);
      setServers(data);
    } catch {
      setError("MCP 서버 목록을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      await api.createMCPServer(
        { name: form.name, endpoint: form.endpoint || undefined, description: form.description || undefined },
        token
      );
      setForm({ name: "", endpoint: "", description: "" });
      setShowForm(false);
      await load();
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async (server: MCPServer) => {
    setTesting(server.id);
    try {
      const result = await api.testMCPServer(server.id, token);
      await load();
      if (result.ok) {
        setSelectedServer({ ...server, status: "online", tools_cache: result.tools });
        setTools(result.tools);
      }
    } finally {
      setTesting(null);
    }
  };

  const handleDelete = async (serverId: string) => {
    if (!confirm("MCP 서버를 삭제하면 연결된 에이전트 툴도 해제됩니다. 계속할까요?")) return;
    await api.deleteMCPServer(serverId, token);
    if (selectedServer?.id === serverId) { setSelectedServer(null); setTools([]); }
    await load();
  };

  const handleSelectServer = async (server: MCPServer) => {
    setSelectedServer(server);
    if (server.tools_cache) {
      setTools(server.tools_cache);
    } else if (server.endpoint) {
      try {
        const result = await api.getMCPServerTools(server.id, token);
        setTools(result.tools);
      } catch { setTools([]); }
    } else {
      setTools([]);
    }
  };

  const totalTools = servers.reduce((acc, s) => acc + (s.tools_cache?.length ?? 0), 0);
  const onlineCount = servers.filter(s => s.status === "online").length;

  return (
    <div className="min-h-screen bg-gray-50">
      <AppHeader />
      <main className="max-w-7xl mx-auto p-6 space-y-6">
        {/* 헤더 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">MCP 서버 연동</h1>
            <p className="text-sm text-gray-500 mt-1">
              Model Context Protocol 서버를 등록하고 에이전트에 외부 툴을 연결합니다.
            </p>
          </div>
          <button
            onClick={() => setShowForm(true)}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition"
          >
            + 서버 등록
          </button>
        </div>

        {/* 요약 카드 */}
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "등록된 서버", value: servers.length },
            { label: "온라인", value: onlineCount },
            { label: "사용 가능 툴", value: totalTools },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
              <p className="text-3xl font-bold text-gray-900">{value}</p>
              <p className="text-sm text-gray-500 mt-1">{label}</p>
            </div>
          ))}
        </div>

        {/* 서버 등록 폼 */}
        {showForm && (
          <div className="bg-white rounded-xl p-6 shadow-sm border border-indigo-100">
            <h2 className="font-semibold mb-4 text-gray-800">새 MCP 서버 등록</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">서버 이름 *</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                    value={form.name}
                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="예: GitHub MCP Server"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Endpoint URL</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                    value={form.endpoint}
                    onChange={e => setForm(f => ({ ...f, endpoint: e.target.value }))}
                    placeholder="https://mcp.example.com"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">설명</label>
                <input
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="이 서버가 제공하는 기능 설명"
                />
              </div>
              <div className="flex gap-3 justify-end">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 border rounded-lg text-sm text-gray-600 hover:bg-gray-50"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
                >
                  {saving ? "저장 중…" : "등록"}
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="grid grid-cols-5 gap-6">
          {/* 서버 목록 */}
          <div className="col-span-2 space-y-3">
            <h2 className="font-semibold text-gray-700 text-sm">등록된 서버</h2>
            {error ? (
              <ErrorBanner message={error} onRetry={load} />
            ) : loading ? (
              <CardGridSkeleton count={3} />
            ) : servers.length === 0 ? (
              <div className="rounded-2xl border-2 border-dashed border-gray-200 py-12 text-center">
                <Server size={32} className="mx-auto mb-2 text-gray-200" />
                <p className="text-sm font-semibold text-gray-500">등록된 MCP 서버가 없습니다</p>
                <p className="text-xs text-gray-400 mt-1">서버를 등록하면 에이전트가 외부 툴을 사용할 수 있습니다</p>
              </div>
            ) : (
              servers.map(server => (
                <div
                  key={server.id}
                  onClick={() => handleSelectServer(server)}
                  className={`bg-white rounded-xl p-4 shadow-sm border cursor-pointer transition-all hover:shadow-md ${
                    selectedServer?.id === server.id ? "border-indigo-400 ring-1 ring-indigo-300" : "border-gray-100"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[server.status]}`} />
                        <span className="font-medium text-sm truncate">{server.name}</span>
                      </div>
                      {server.description && (
                        <p className="text-xs text-gray-500 mt-1 truncate">{server.description}</p>
                      )}
                      {server.endpoint && (
                        <p className="text-xs text-gray-400 font-mono truncate mt-1">{server.endpoint}</p>
                      )}
                      <div className="flex items-center gap-3 mt-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${STATUS_COLOR[server.status]}`}>
                          {server.status === "online" ? "온라인" :
                           server.status === "offline" ? "오프라인" :
                           server.status === "error" ? "오류" : "미확인"}
                        </span>
                        {server.tools_cache && (
                          <span className="text-xs text-indigo-600 font-medium">
                            툴 {server.tools_cache.length}개
                          </span>
                        )}
                      </div>
                      {server.error_message && (
                        <p className="text-xs text-red-500 mt-1 truncate">{server.error_message}</p>
                      )}
                    </div>
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={e => { e.stopPropagation(); handleTest(server); }}
                        disabled={testing === server.id}
                        className="text-xs px-2 py-1 bg-indigo-50 text-indigo-700 rounded hover:bg-indigo-100 disabled:opacity-50"
                      >
                        {testing === server.id ? "…" : "테스트"}
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); handleDelete(server.id); }}
                        className="text-xs px-2 py-1 bg-red-50 text-red-600 rounded hover:bg-red-100"
                      >
                        삭제
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* 툴 상세 패널 */}
          <div className="col-span-3">
            {selectedServer ? (
              <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 h-full">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="font-semibold text-gray-800">{selectedServer.name}</h2>
                    <p className="text-xs text-gray-400 font-mono">{selectedServer.endpoint}</p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full border ${STATUS_COLOR[selectedServer.status]}`}>
                    {selectedServer.status}
                  </span>
                </div>

                {tools.length === 0 ? (
                  <div className="text-center text-gray-400 py-10">
                    <p className="text-2xl mb-2">🔧</p>
                    <p className="text-sm">툴 정보가 없습니다.</p>
                    <p className="text-xs mt-1">연결 테스트를 실행하면 툴 목록이 자동으로 조회됩니다.</p>
                    <button
                      onClick={() => handleTest(selectedServer)}
                      disabled={testing === selectedServer.id}
                      className="mt-3 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                    >
                      {testing === selectedServer.id ? "연결 중…" : "연결 테스트 실행"}
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2 overflow-y-auto max-h-96">
                    <p className="text-xs text-gray-500 mb-3">총 {tools.length}개 툴 사용 가능</p>
                    {tools.map((tool) => (
                      <div key={tool.name} className="border border-gray-100 rounded-lg p-3 hover:bg-gray-50">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="font-mono text-sm font-semibold text-indigo-700">{tool.name}</p>
                            <p className="text-xs text-gray-600 mt-1">{tool.description}</p>
                            {tool.input_schema && Object.keys((tool.input_schema as {properties?: object}).properties ?? {}).length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1">
                                {Object.keys((tool.input_schema as {properties?: Record<string, unknown>}).properties ?? {}).map(param => (
                                  <span key={param} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-mono">
                                    {param}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                          <span className="text-xs bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded flex-shrink-0">MCP</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-white rounded-xl p-10 shadow-sm border border-dashed border-gray-200 flex flex-col items-center justify-center h-full text-gray-400">
                <p className="text-4xl mb-3">🔌</p>
                <p className="font-medium text-gray-500">서버를 선택하면 툴 목록이 표시됩니다</p>
                <p className="text-sm mt-1">연결 테스트 버튼으로 MCP 서버에 연결하세요.</p>
              </div>
            )}
          </div>
        </div>

        {/* MCP 프로토콜 안내 */}
        <div className="bg-indigo-50 rounded-xl p-5 border border-indigo-100">
          <h3 className="font-semibold text-indigo-800 mb-2">MCP 서버 연결 가이드</h3>
          <div className="grid grid-cols-3 gap-4 text-sm text-indigo-700">
            <div>
              <p className="font-medium mb-1">① 서버 등록</p>
              <p className="text-xs text-indigo-600">MCP 서버 이름과 HTTP Endpoint URL을 입력해 등록합니다.</p>
            </div>
            <div>
              <p className="font-medium mb-1">② 연결 테스트</p>
              <p className="text-xs text-indigo-600">테스트 버튼을 누르면 서버에 접속해 사용 가능한 툴 목록을 자동으로 조회합니다.</p>
            </div>
            <div>
              <p className="font-medium mb-1">③ 에이전트 연결</p>
              <p className="text-xs text-indigo-600">스튜디오에서 에이전트를 편집할 때 MCP 툴을 선택해 연결합니다.</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
