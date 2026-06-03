"""ROI 측정 서비스 — 팀별 월간 지표 계산 + Claude 인사이트."""
import uuid
import json
from datetime import datetime, timezone
from collections import defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.run_orm import RunORM
from app.db.models.agent_orm import AgentORM
from app.db.models.roi_snapshot_orm import ROISnapshotORM

# 비용표 (USD / 1M tokens) — gpt-4o-mini 기준
_COST_TABLE = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o":       {"input": 2.50, "output": 10.00},
    "gpt-4-turbo":  {"input": 10.00, "output": 30.00},
    "default":      {"input": 0.15, "output": 0.60},
}

# 인간 작업 대비 절감 시간 추정
_ASSUMED_HUMAN_HOURS_PER_TASK = 2.0  # 작업 1건당 평균 2시간 절감 가정
_HUMAN_HOURLY_RATE_USD = 50.0        # 시간당 $50 (중급 직원 기준)


def _calc_cost(input_tokens: int, output_tokens: int, model: str | None) -> float:
    rates = _COST_TABLE.get(model or "default", _COST_TABLE["default"])
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


async def _get_claude_insights(
    period: str,
    team_id: str,
    metrics: dict,
) -> tuple[str, list[dict]]:
    if not settings.anthropic_api_key:
        return (
            f"[Mock] {period} 기간 ROI 분석: 성공률 {metrics['success_rate']:.0%}, "
            f"비용 ${metrics['cost']:.2f}, 절감 시간 {metrics['hours_saved']:.1f}h",
            [
                {"priority": "high", "action": "실패율이 높은 에이전트의 프롬프트를 개선하세요."},
                {"priority": "medium", "action": "토큰 사용량이 많은 작업의 입력을 최적화하세요."},
            ],
        )
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        prompt = f"""AI 에이전트 플랫폼 ROI 분석 — {period} 기간 보고서

팀 ID: {team_id}
총 실행: {metrics['total_runs']}건
성공률: {metrics['success_rate']:.1%}
총 비용: ${metrics['cost']:.4f}
절감 시간: {metrics['hours_saved']:.1f}시간
ROI 배수: {metrics['roi_multiplier']:.1f}x

다음 JSON 형식으로만 답하세요 (추가 설명 없이):
{{
  "insights": "2-3문장 핵심 인사이트",
  "recommendations": [
    {{"priority": "high|medium|low", "action": "구체적 행동 지침"}},
    {{"priority": "high|medium|low", "action": "구체적 행동 지침"}}
  ]
}}"""
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(msg.content[0].text)
        return data.get("insights", ""), data.get("recommendations", [])
    except Exception:
        return f"{period} ROI 데이터 분석 완료. 성공률과 비용 효율을 지속적으로 모니터링하세요.", []


async def compute_roi_snapshot(
    db: AsyncSession,
    *,
    team_id: str,
    period: str,   # "2026-06"
) -> ROISnapshotORM:
    """팀의 월별 ROI 스냅샷 계산·저장 (이미 있으면 갱신)."""
    year, month = map(int, period.split("-"))

    # 기간 내 실행 조회
    from sqlalchemy import extract
    runs_q = select(RunORM).where(
        RunORM.agent_id.in_(
            select(AgentORM.id).where(AgentORM.team_id == team_id)
        ),
        extract("year", RunORM.created_at) == year,
        extract("month", RunORM.created_at) == month,
    )
    result = await db.execute(runs_q)
    runs = result.scalars().all()

    total = len(runs)
    succeeded = sum(1 for r in runs if r.status == "completed")
    failed = sum(1 for r in runs if r.status == "failed")
    total_in = sum(r.input_tokens or 0 for r in runs)
    total_out = sum(r.output_tokens or 0 for r in runs)
    cost = sum(_calc_cost(r.input_tokens or 0, r.output_tokens or 0, r.model) for r in runs)
    durations = [r.duration_ms for r in runs if r.duration_ms]
    avg_dur = sum(durations) / len(durations) if durations else None
    hours_saved = succeeded * _ASSUMED_HUMAN_HOURS_PER_TASK
    value_created = hours_saved * _HUMAN_HOURLY_RATE_USD
    roi_mult = value_created / cost if cost > 0 else 0.0
    cost_per_task = cost / succeeded if succeeded > 0 else None
    success_rate = succeeded / total if total > 0 else 0.0

    # 에이전트별 통계
    agent_stats: dict[str, dict] = defaultdict(lambda: {"runs": 0, "success": 0})
    for r in runs:
        agent_stats[r.agent_id]["runs"] += 1
        if r.status == "completed":
            agent_stats[r.agent_id]["success"] += 1
    top_agents = sorted(
        [
            {
                "agent_id": aid,
                "runs": s["runs"],
                "success_rate": s["success"] / s["runs"] if s["runs"] else 0,
            }
            for aid, s in agent_stats.items()
        ],
        key=lambda x: x["runs"],
        reverse=True,
    )[:5]

    # 섀도우 AI 에이전트 수 (팀 없이 실행된 에이전트)
    sprawl_q = select(func.count(AgentORM.id.distinct())).where(
        AgentORM.team_id.is_(None),
    )
    sprawl_result = await db.execute(sprawl_q)
    sprawl_count = sprawl_result.scalar() or 0

    metrics = {
        "total_runs": total, "success_rate": success_rate,
        "cost": cost, "hours_saved": hours_saved, "roi_multiplier": roi_mult,
    }
    insights, recommendations = await _get_claude_insights(period, team_id, metrics)

    # upsert
    existing_q = select(ROISnapshotORM).where(
        ROISnapshotORM.team_id == team_id,
        ROISnapshotORM.period == period,
    )
    ex_result = await db.execute(existing_q)
    snap = ex_result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if snap:
        snap.total_runs = total; snap.successful_runs = succeeded; snap.failed_runs = failed
        snap.total_agents_used = len(agent_stats)
        snap.total_input_tokens = total_in; snap.total_output_tokens = total_out
        snap.estimated_cost_usd = round(cost, 6)
        snap.avg_duration_ms = round(avg_dur, 1) if avg_dur else None
        snap.estimated_hours_saved = round(hours_saved, 2)
        snap.cost_per_successful_task_usd = round(cost_per_task, 6) if cost_per_task else None
        snap.roi_multiplier = round(roi_mult, 2)
        snap.top_agents = top_agents; snap.agent_sprawl_count = sprawl_count
        snap.claude_insights = insights; snap.claude_recommendations = recommendations
        snap.updated_at = now
    else:
        snap = ROISnapshotORM(
            id=str(uuid.uuid4()), team_id=team_id, period=period,
            total_runs=total, successful_runs=succeeded, failed_runs=failed,
            total_agents_used=len(agent_stats),
            total_input_tokens=total_in, total_output_tokens=total_out,
            estimated_cost_usd=round(cost, 6),
            avg_duration_ms=round(avg_dur, 1) if avg_dur else None,
            estimated_hours_saved=round(hours_saved, 2),
            cost_per_successful_task_usd=round(cost_per_task, 6) if cost_per_task else None,
            roi_multiplier=round(roi_mult, 2),
            top_agents=top_agents, agent_sprawl_count=sprawl_count,
            claude_insights=insights, claude_recommendations=recommendations,
            created_at=now, updated_at=now,
        )
        db.add(snap)

    await db.flush()
    return snap


async def get_snapshot(db: AsyncSession, team_id: str, period: str) -> ROISnapshotORM | None:
    q = select(ROISnapshotORM).where(
        ROISnapshotORM.team_id == team_id,
        ROISnapshotORM.period == period,
    )
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def list_snapshots(db: AsyncSession, team_id: str, limit: int = 12) -> list[ROISnapshotORM]:
    q = (
        select(ROISnapshotORM)
        .where(ROISnapshotORM.team_id == team_id)
        .order_by(ROISnapshotORM.period.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    return list(result.scalars().all())
