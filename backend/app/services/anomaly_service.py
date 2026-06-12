"""이상 행동 감지 서비스 — 규칙 기반 스코어링 + Claude 분석."""
import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.anomaly_event_orm import AnomalyEventORM
from app.db.models.run_orm import RunORM

# 임계값 설정
_THRESHOLDS = {
    "token_spike_ratio": 3.0,      # 평균 대비 3배 초과 시 이상
    "failure_rate_high": 0.5,      # 최근 10회 중 50% 이상 실패
    "rate_abuse_per_hour": 20,     # 시간당 20회 이상 실행
    "min_runs_for_baseline": 5,    # 기준선 계산을 위한 최소 실행 수
}

_SEVERITY_FROM_SCORE = {
    (0.8, 1.0): "critical",
    (0.6, 0.8): "high",
    (0.4, 0.6): "medium",
    (0.0, 0.4): "low",
}


def _score_to_severity(score: float) -> str:
    for (lo, hi), sev in _SEVERITY_FROM_SCORE.items():
        if lo <= score <= hi:
            return sev
    return "low"


async def _get_claude_analysis(
    agent_name: str, anomaly_type: str, description: str, score: float
) -> tuple[str, str]:
    """Claude에게 이상 행동 분석·권고 요청. API 없으면 기본 텍스트."""
    if not settings.anthropic_api_key:
        return (
            f"[Mock] {anomaly_type} 이상이 감지되었습니다. 위험 점수: {score:.2f}",
            "API 키 설정 후 Claude 심층 분석을 사용하세요.",
        )
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        prompt = f"""에이전트 이상 행동 분석 요청:

에이전트: {agent_name}
이상 유형: {anomaly_type}
설명: {description}
위험 점수: {score:.2f} / 1.0

다음 형식으로 답하세요:
1. 분석: 이상의 원인과 의미 (2-3문장)
2. 권고: 즉시 취해야 할 조치 (1-2문장)"""

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text
        parts = text.split("2. 권고:")
        analysis = parts[0].replace("1. 분석:", "").strip()
        recommendation = parts[1].strip() if len(parts) > 1 else "즉시 해당 에이전트 실행을 중단하고 검토하세요."
        return analysis, recommendation
    except Exception:
        return (
            f"{anomaly_type} 패턴이 감지되었습니다. 위험 점수 {score:.2f}",
            "보안팀에 즉시 보고하고 에이전트 실행을 일시 중단하세요.",
        )


async def check_run_anomalies(
    db: AsyncSession,
    *,
    run: RunORM,
    agent_id: str,
    agent_name: str,
    team_id: str | None,
) -> list[AnomalyEventORM]:
    """실행 완료 후 이상 행동 검사. 감지된 이상 이벤트 목록 반환."""
    detected: list[AnomalyEventORM] = []

    # ── 1. 토큰 급증 감지 ─────────────────────────────────────────
    recent_q = (
        select(func.avg(RunORM.input_tokens + RunORM.output_tokens))
        .where(
            RunORM.agent_id == agent_id,
            RunORM.status == "completed",
            RunORM.run_id != run.run_id,
        )
        .limit(20)
    )
    avg_result = await db.execute(recent_q)
    avg_tokens = avg_result.scalar() or 0

    current_tokens = (run.input_tokens or 0) + (run.output_tokens or 0)
    if avg_tokens > 0 and current_tokens > avg_tokens * _THRESHOLDS["token_spike_ratio"]:
        ratio = current_tokens / avg_tokens
        score = min(0.4 + (ratio - 3) * 0.15, 1.0)
        desc = f"토큰 사용량 {current_tokens:,}개 (평균 {avg_tokens:.0f}개 대비 {ratio:.1f}배)"
        analysis, rec = await _get_claude_analysis(agent_name, "token_spike", desc, score)
        evt = AnomalyEventORM(
            id=str(uuid.uuid4()),
            agent_id=agent_id, run_id=run.run_id, team_id=team_id,
            anomaly_type="token_spike", severity=_score_to_severity(score), score=round(score, 3),
            baseline_value=round(avg_tokens, 1), observed_value=float(current_tokens),
            description=desc, claude_analysis=analysis, claude_recommendation=rec,
        )
        db.add(evt)
        detected.append(evt)

    # ── 2. 실패율 급증 감지 ──────────────────────────────────────
    recent_runs_q = (
        select(RunORM.status)
        .where(RunORM.agent_id == agent_id)
        .order_by(RunORM.created_at.desc())
        .limit(10)
    )
    recent_result = await db.execute(recent_runs_q)
    recent_statuses = [r[0] for r in recent_result.fetchall()]
    if len(recent_statuses) >= _THRESHOLDS["min_runs_for_baseline"]:
        fail_rate = recent_statuses.count("failed") / len(recent_statuses)
        if fail_rate >= _THRESHOLDS["failure_rate_high"]:
            score = min(0.5 + fail_rate * 0.5, 1.0)
            desc = f"최근 {len(recent_statuses)}회 실행 중 {fail_rate*100:.0f}% 실패"
            analysis, rec = await _get_claude_analysis(agent_name, "behavior_drift", desc, score)
            evt = AnomalyEventORM(
                id=str(uuid.uuid4()),
                agent_id=agent_id, run_id=run.run_id, team_id=team_id,
                anomaly_type="behavior_drift", severity=_score_to_severity(score), score=round(score, 3),
                baseline_value=0.2, observed_value=round(fail_rate, 3),
                description=desc, claude_analysis=analysis, claude_recommendation=rec,
            )
            db.add(evt)
            detected.append(evt)

    # ── 3. 실행 빈도 남용 감지 ──────────────────────────────────
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    rate_q = select(func.count()).where(
        RunORM.agent_id == agent_id,
        RunORM.created_at >= one_hour_ago,
    )
    rate_result = await db.execute(rate_q)
    runs_per_hour = rate_result.scalar() or 0
    if runs_per_hour >= _THRESHOLDS["rate_abuse_per_hour"]:
        score = min(0.5 + (runs_per_hour - 20) * 0.02, 1.0)
        desc = f"최근 1시간 내 {runs_per_hour}회 실행 (임계: {_THRESHOLDS['rate_abuse_per_hour']}회)"
        analysis, rec = await _get_claude_analysis(agent_name, "rate_abuse", desc, score)
        evt = AnomalyEventORM(
            id=str(uuid.uuid4()),
            agent_id=agent_id, run_id=run.run_id, team_id=team_id,
            anomaly_type="rate_abuse", severity=_score_to_severity(score), score=round(score, 3),
            baseline_value=float(_THRESHOLDS["rate_abuse_per_hour"]), observed_value=float(runs_per_hour),
            description=desc, claude_analysis=analysis, claude_recommendation=rec,
        )
        db.add(evt)
        detected.append(evt)

    if detected:
        await db.flush()
    return detected


async def record_tool_loop(
    db: AsyncSession,
    *,
    agent_id: str,
    agent_name: str,
    run_id: str | None,
    team_id: str | None,
    tool_name: str,
    repeat_count: int,
) -> AnomalyEventORM:
    """동일 툴 반복 호출(무한루프) 감지 이벤트 기록.

    workflow_executor._run_node_inner() 에서 _MAX_TOOL_REPEATS 임계값 도달 시 호출.
    """
    score = min(0.5 + (repeat_count - 5) * 0.1, 1.0)
    desc = f"'{tool_name}' 툴이 {repeat_count}회 연속 호출됨 (워크플로우 노드 실행 중)"
    analysis, rec = await _get_claude_analysis(agent_name, "tool_loop", desc, score)

    evt = AnomalyEventORM(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        run_id=run_id,
        team_id=team_id,
        anomaly_type="tool_loop",
        severity=_score_to_severity(score),
        score=round(score, 3),
        baseline_value=5.0,
        observed_value=float(repeat_count),
        description=desc,
        claude_analysis=analysis,
        claude_recommendation=rec,
    )
    db.add(evt)
    await db.flush()
    return evt


async def list_anomalies(
    db: AsyncSession,
    *,
    team_id: str | None = None,
    agent_id: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 50,
) -> list[AnomalyEventORM]:
    q = select(AnomalyEventORM).order_by(AnomalyEventORM.detected_at.desc())
    if team_id:
        q = q.where(AnomalyEventORM.team_id == team_id)
    if agent_id:
        q = q.where(AnomalyEventORM.agent_id == agent_id)
    if status:
        q = q.where(AnomalyEventORM.status == status)
    if severity:
        q = q.where(AnomalyEventORM.severity == severity)
    q = q.limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def resolve_anomaly(
    db: AsyncSession,
    anomaly_id: str,
    *,
    resolved_by: str,
    status: str,
    note: str | None = None,
) -> AnomalyEventORM | None:
    evt = await db.get(AnomalyEventORM, anomaly_id)
    if not evt:
        return None
    evt.status = status
    evt.resolved_by = resolved_by
    evt.resolved_at = datetime.now(timezone.utc)
    evt.resolution_note = note
    await db.flush()
    return evt
