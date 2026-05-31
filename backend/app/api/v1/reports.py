from collections import defaultdict
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user
from app.db.models.user_orm import UserORM
from app.db.models.agent_orm import AgentORM
from app.db.models.run_orm import RunORM
from app.db.models.workflow_orm import WorkflowORM
from app.db.repositories.team_repo import TeamRepository
from app.models.report import (
    EnterpriseReportData, EnterpriseOverview,
    TeamReportStat, AgentRankEntry, SynergyPair,
    ModelCostStat, DailyRunStat,
)

router = APIRouter(tags=["reports"])

_COST_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o-mini":   (0.15,  0.60),
    "gpt-4o":        (5.0,  15.0),
    "gpt-4-turbo":  (10.0,  30.0),
    "gpt-4":        (30.0,  60.0),
    "gpt-3.5-turbo": (0.5,   1.5),
}

def _cost(model: str | None, inp: int, out: int) -> float:
    key = next((k for k in _COST_TABLE if (model or "").startswith(k)), "gpt-4o-mini")
    in_rate, out_rate = _COST_TABLE[key]
    return (inp * in_rate + out * out_rate) / 1_000_000


@router.get("/reports/enterprise", response_model=EnterpriseReportData)
async def get_enterprise_report(
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """전사 에이전트 운영 현황 리포트를 반환합니다."""

    # ── 전체 데이터 로드 ───────────────────────────────────────────
    teams    = await TeamRepository(db).list_all()
    agents   = list((await db.execute(select(AgentORM))).scalars().all())
    runs     = list((await db.execute(select(RunORM).order_by(RunORM.created_at.desc()))).scalars().all())
    workflows = list((await db.execute(select(WorkflowORM))).scalars().all())

    team_map  = {t.id: t for t in teams}
    agent_map = {a.id: a for a in agents}

    # ── 전사 개요 ──────────────────────────────────────────────────
    completed  = sum(1 for r in runs if r.status == "completed")
    failed     = sum(1 for r in runs if r.status == "failed")
    running    = sum(1 for r in runs if r.status == "running")
    terminal   = completed + failed
    tot_tokens = sum((r.input_tokens or 0) + (r.output_tokens or 0) for r in runs)
    tot_cost   = sum(_cost(r.model, r.input_tokens or 0, r.output_tokens or 0) for r in runs)

    overview = EnterpriseOverview(
        total_teams=len(teams),
        total_agents=len(agents),
        total_workflows=len(workflows),
        total_runs=len(runs),
        completed_runs=completed,
        failed_runs=failed,
        running_runs=running,
        success_rate=round(completed / terminal, 4) if terminal else 0.0,
        total_tokens=tot_tokens,
        estimated_cost_usd=round(tot_cost, 6),
    )

    # ── 팀별 통계 ──────────────────────────────────────────────────
    team_agents: dict[str, list[AgentORM]] = defaultdict(list)
    for a in agents:
        if a.team_id:
            team_agents[a.team_id].append(a)

    team_agent_ids: dict[str, set[str]] = {
        tid: {a.id for a in ags} for tid, ags in team_agents.items()
    }
    team_runs: dict[str, list[RunORM]] = defaultdict(list)
    for r in runs:
        for tid, ids in team_agent_ids.items():
            if r.agent_id in ids:
                team_runs[tid].append(r)
                break

    team_wf_count: dict[str, int] = defaultdict(int)
    for wf in workflows:
        if wf.team_id:
            team_wf_count[wf.team_id] += 1

    team_stats: list[TeamReportStat] = []
    for t in teams:
        truns = team_runs.get(t.id, [])
        tc = sum(1 for r in truns if r.status == "completed")
        tf = sum(1 for r in truns if r.status == "failed")
        tt = tc + tf
        ttok = sum((r.input_tokens or 0) + (r.output_tokens or 0) for r in truns)
        tcost = sum(_cost(r.model, r.input_tokens or 0, r.output_tokens or 0) for r in truns)
        team_stats.append(TeamReportStat(
            team_id=t.id,
            team_name=t.name,
            agent_count=len(team_agents.get(t.id, [])),
            workflow_count=team_wf_count.get(t.id, 0),
            run_count=len(truns),
            success_rate=round(tc / tt, 4) if tt else 0.0,
            total_tokens=ttok,
            estimated_cost_usd=round(tcost, 6),
        ))
    team_stats.sort(key=lambda x: -x.run_count)

    # ── 에이전트 성능 TOP 10 ───────────────────────────────────────
    agent_run_map: dict[str, list[RunORM]] = defaultdict(list)
    for r in runs:
        agent_run_map[r.agent_id].append(r)

    rank_entries: list[AgentRankEntry] = []
    for a in agents:
        aruns = agent_run_map.get(a.id, [])
        atok  = sum((r.input_tokens or 0) + (r.output_tokens or 0) for r in aruns)
        team  = team_map.get(a.team_id or "", None)
        rank_entries.append(AgentRankEntry(
            agent_id=a.id,
            name=a.name,
            role=a.role,
            team_name=team.name if team else "—",
            usage_count=a.usage_count,
            success_rate=round(a.success_rate, 4),
            total_tokens=atok,
            estimated_cost_usd=round(
                sum(_cost(r.model, r.input_tokens or 0, r.output_tokens or 0) for r in aruns), 6
            ),
        ))
    rank_entries.sort(key=lambda x: (-x.usage_count, -x.success_rate))
    top_agents = rank_entries[:10]

    # ── 시너지 페어링 (워크플로 edges 분석) ────────────────────────
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)

    for wf in workflows:
        nodes_raw = wf.nodes or []
        edges_raw = wf.edges or []

        # node_id → agent_id 매핑
        node_agent: dict[str, str] = {}
        for n in nodes_raw:
            nid = n.get("id")
            aid = (n.get("data") or {}).get("agentId")
            if nid and aid:
                node_agent[nid] = aid

        # 이 워크플로에서 등장한 페어 (중복 제거)
        wf_pairs: set[tuple[str, str]] = set()
        for e in edges_raw:
            src_agent = node_agent.get(e.get("source", ""))
            tgt_agent = node_agent.get(e.get("target", ""))
            if src_agent and tgt_agent and src_agent != tgt_agent:
                # 방향 무관 정규화 (a < b)
                key = (min(src_agent, tgt_agent), max(src_agent, tgt_agent))
                wf_pairs.add(key)

        for pair in wf_pairs:
            pair_counts[pair] += 1

    synergy_pairs: list[SynergyPair] = []
    for (a_id, b_id), count in sorted(pair_counts.items(), key=lambda x: -x[1])[:10]:
        a = agent_map.get(a_id)
        b = agent_map.get(b_id)
        if not a or not b:
            continue
        synergy_pairs.append(SynergyPair(
            agent_a_id=a_id, agent_a_name=a.name, agent_a_role=a.role,
            agent_b_id=b_id, agent_b_name=b.name, agent_b_role=b.role,
            workflow_count=count,
        ))

    # ── 모델별 비용 분포 ───────────────────────────────────────────
    model_runs: dict[str, list[RunORM]] = defaultdict(list)
    for r in runs:
        key = next((k for k in _COST_TABLE if (r.model or "").startswith(k)), r.model or "unknown")
        model_runs[key].append(r)

    model_cost_stats: list[ModelCostStat] = []
    for model, mruns in model_runs.items():
        mtok  = sum((r.input_tokens or 0) + (r.output_tokens or 0) for r in mruns)
        mcost = sum(_cost(r.model, r.input_tokens or 0, r.output_tokens or 0) for r in mruns)
        model_cost_stats.append(ModelCostStat(
            model=model,
            run_count=len(mruns),
            total_tokens=mtok,
            estimated_cost_usd=round(mcost, 6),
            cost_share=round(mcost / tot_cost, 4) if tot_cost else 0.0,
        ))
    model_cost_stats.sort(key=lambda x: -x.estimated_cost_usd)

    # ── 최근 14일 추이 ─────────────────────────────────────────────
    today = datetime.now(timezone.utc).date()
    daily: dict[str, dict] = {}
    for i in range(13, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        daily[d] = {"run_count": 0, "success_count": 0, "total_tokens": 0, "cost": 0.0}

    for r in runs:
        d = r.created_at.date().isoformat()
        if d not in daily:
            continue
        daily[d]["run_count"] += 1
        if r.status == "completed":
            daily[d]["success_count"] += 1
        daily[d]["total_tokens"] += (r.input_tokens or 0) + (r.output_tokens or 0)
        daily[d]["cost"] += _cost(r.model, r.input_tokens or 0, r.output_tokens or 0)

    daily_run_stats = [
        DailyRunStat(
            date=d,
            run_count=v["run_count"],
            success_count=v["success_count"],
            total_tokens=v["total_tokens"],
            estimated_cost_usd=round(v["cost"], 6),
        )
        for d, v in daily.items()
    ]

    return EnterpriseReportData(
        generated_at=datetime.now(timezone.utc),
        overview=overview,
        team_stats=team_stats,
        top_agents=top_agents,
        synergy_pairs=synergy_pairs,
        model_cost_stats=model_cost_stats,
        daily_run_stats=daily_run_stats,
    )
