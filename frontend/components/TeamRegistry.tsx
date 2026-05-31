"use client";

import { useEffect, useState, useRef } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Agent, api } from "@/lib/api";
import { Search, X, Globe, GitFork, Loader2, Zap } from "lucide-react";
import AgentCard from "./AgentCard";
import CreateAgentButton from "./CreateAgentButton";
import SynergyPanel from "./SynergyPanel";

type Tab = "team" | "public";

const TAG_COLORS = [
  "bg-blue-50 text-blue-600",
  "bg-purple-50 text-purple-600",
  "bg-amber-50 text-amber-700",
  "bg-green-50 text-green-700",
  "bg-rose-50 text-rose-600",
];

export default function TeamRegistry() {
  const { data: session } = useSession();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("team");
  const [search, setSearch] = useState("");
  const [activeTags, setActiveTags] = useState<string[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const [synergyAgent, setSynergyAgent] = useState<Agent | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Collect all available tags from loaded agents
  const allTags = Array.from(new Set(agents.flatMap((a) => a.tags ?? [])));

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(fetchAgents, 250);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [tab, search, activeTags, session]);

  async function fetchAgents() {
    setLoading(true);
    try {
      const params = {
        search: search || undefined,
        tags: activeTags.length ? activeTags.join(",") : undefined,
      };

      if (tab === "team" && session?.user?.teamId) {
        setAgents(
          await api.getTeamAgents(session.user.teamId, params, session.user.accessToken)
        );
      } else if (tab === "team") {
        // No team — fall back to all agents
        setAgents(await api.getAgents());
      } else {
        setAgents(await api.getPublicAgents(params));
      }
    } catch {
      setAgents([]);
    } finally {
      setLoading(false);
    }
  }

  function toggleTag(tag: string) {
    setActiveTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  }

  return (
    <section>
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-800">에이전트 레지스트리</h2>
          <span className="text-sm text-gray-400">{agents.length}개</span>
        </div>
        <CreateAgentButton />
      </div>

      {/* 탭 + 검색 */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <div className="flex rounded-lg border border-gray-200 overflow-hidden shrink-0">
          <TabButton active={tab === "team"} onClick={() => setTab("team")}>
            내 팀
          </TabButton>
          <TabButton active={tab === "public"} onClick={() => setTab("public")}>
            <Globe size={12} className="inline mr-1" />
            공개 레지스트리
          </TabButton>
        </div>

        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="에이전트 이름, 설명 검색..."
            className="w-full pl-9 pr-8 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {/* 태그 필터 */}
      {allTags.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap mb-4">
          {allTags.map((tag, i) => {
            const isActive = activeTags.includes(tag);
            return (
              <button
                key={tag}
                onClick={() => toggleTag(tag)}
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium border transition-colors ${
                  isActive
                    ? "border-blue-400 bg-blue-50 text-blue-700"
                    : `border-transparent ${TAG_COLORS[i % TAG_COLORS.length]}`
                }`}
              >
                #{tag}
              </button>
            );
          })}
          {activeTags.length > 0 && (
            <button
              onClick={() => setActiveTags([])}
              className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-0.5"
            >
              <X size={11} />
              초기화
            </button>
          )}
        </div>
      )}

      {/* 에이전트 그리드 */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-gray-400">
          <Loader2 size={20} className="animate-spin mr-2" />
          <span className="text-sm">불러오는 중...</span>
        </div>
      ) : agents.length === 0 ? (
        <EmptyState tab={tab} hasSearch={!!search || activeTags.length > 0} />
      ) : tab === "team" ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {agents.map((agent) => (
            <div key={agent.id} className="relative group">
              <AgentCard agent={agent} />
              <button
                onClick={() => setSynergyAgent(agent)}
                className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 px-2 py-1 rounded-lg bg-amber-50 text-amber-600 border border-amber-200 text-xs font-medium hover:bg-amber-100"
                title="시너지 분석"
              >
                <Zap size={11} />
                시너지
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {agents.map((agent) => (
            <PublicAgentCard
              key={agent.id}
              agent={agent}
              myTeamId={session?.user?.teamId ?? null}
              token={session?.user?.accessToken}
              onForked={() => router.refresh()}
              onSynergy={() => setSynergyAgent(agent)}
            />
          ))}
        </div>
      )}

      {synergyAgent && (
        <SynergyPanel agent={synergyAgent} onClose={() => setSynergyAgent(null)} />
      )}
    </section>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs font-medium transition-colors ${
        active
          ? "bg-blue-600 text-white"
          : "bg-white text-gray-600 hover:bg-gray-50"
      }`}
    >
      {children}
    </button>
  );
}

function EmptyState({ tab, hasSearch }: { tab: Tab; hasSearch: boolean }) {
  return (
    <div className="rounded-2xl border border-dashed border-gray-300 py-12 text-center text-gray-400">
      {hasSearch ? (
        <>
          <Search size={28} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">검색 결과가 없습니다.</p>
        </>
      ) : tab === "team" ? (
        <>
          <p className="text-sm">팀 에이전트가 없습니다.</p>
          <p className="text-xs mt-1">새 에이전트를 등록하거나 공개 레지스트리에서 Fork하세요.</p>
        </>
      ) : (
        <>
          <Globe size={28} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">공개된 에이전트가 없습니다.</p>
        </>
      )}
    </div>
  );
}

function PublicAgentCard({
  agent,
  myTeamId,
  token,
  onForked,
  onSynergy,
}: {
  agent: Agent;
  myTeamId: string | null;
  token: string | undefined;
  onForked: () => void;
  onSynergy: () => void;
}) {
  const [forking, setForking] = useState(false);
  const isOwnTeam = myTeamId === agent.team_id;

  const ROLE_COLORS: Record<Agent["role"], string> = {
    researcher: "bg-blue-100 text-blue-700",
    writer: "bg-purple-100 text-purple-700",
    analyst: "bg-amber-100 text-amber-700",
    coder: "bg-green-100 text-green-700",
  };

  async function handleFork() {
    setForking(true);
    try {
      await api.forkAgent(agent.id, token);
      onForked();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Fork에 실패했습니다.");
    } finally {
      setForking(false);
    }
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-gray-900 text-sm">{agent.name}</span>
            <span className="text-xs text-gray-400 font-mono">v{agent.version}</span>
            {agent.forked_from && (
              <span className="flex items-center gap-0.5 text-xs text-gray-400">
                <GitFork size={10} /> fork
              </span>
            )}
          </div>
          {agent.description && (
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{agent.description}</p>
          )}
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${ROLE_COLORS[agent.role]}`}>
          {agent.role}
        </span>
      </div>

      {(agent.tags ?? []).length > 0 && (
        <div className="flex flex-wrap gap-1">
          {(agent.tags ?? []).map((tag) => (
            <span key={tag} className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">
              #{tag}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between mt-1 gap-2">
        {agent.usage_count > 0 && (
          <span className="text-xs text-gray-400 shrink-0">{agent.usage_count}회 · {(agent.success_rate * 100).toFixed(0)}%</span>
        )}
        <div className="flex items-center gap-1.5 ml-auto">
          <button
            onClick={onSynergy}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-amber-50 text-amber-600 border border-amber-200 hover:bg-amber-100 transition-colors"
          >
            <Zap size={11} />
            시너지
          </button>
          {!isOwnTeam ? (
            <button
              onClick={handleFork}
              disabled={forking}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-violet-600 text-white hover:bg-violet-700 transition-colors disabled:opacity-50"
            >
              {forking ? <Loader2 size={11} className="animate-spin" /> : <GitFork size={11} />}
              Fork
            </button>
          ) : (
            <span className="text-xs text-gray-400">내 팀</span>
          )}
        </div>
      </div>
    </div>
  );
}
