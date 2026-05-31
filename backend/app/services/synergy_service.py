"""
시너지 추천 엔진.

알고리즘 점수 (ANTHROPIC_API_KEY 없이도 동작):
  - tag_score    : 두 에이전트 태그의 Jaccard 유사도           (가중치 35%)
  - schema_fwd   : source.output_schema → candidate.input_schema 호환도 (30%)
  - schema_rev   : candidate.output_schema → source.input_schema 호환도 (15%)
  - performance  : candidate.success_rate                       (15%)
  - role_bonus   : 보완적 역할 쌍 보너스 (flat +0.05)

Claude 분석 (ANTHROPIC_API_KEY 설정 시):
  - 상위 후보들과의 시너지 설명, 워크플로 제안, 적합 작업 유형을 한국어로 반환
"""
from __future__ import annotations
import json
from app.db.models.agent_orm import AgentORM
from app.models.agent import AgentResponse
from app.models.synergy import SynergyCandidate, SynergyResponse

# ── 역할 보완 쌍 ─────────────────────────────────────────────────────────────
_COMPLEMENTARY = {
    frozenset({"researcher", "writer"}),
    frozenset({"researcher", "analyst"}),
    frozenset({"researcher", "coder"}),
    frozenset({"analyst", "writer"}),
    frozenset({"analyst", "coder"}),
    frozenset({"writer", "coder"}),
}


# ── 개별 점수 계산 ────────────────────────────────────────────────────────────

def _tag_score(a: list | None, b: list | None) -> tuple[float, list[str]]:
    """Jaccard 유사도 + 공통 태그 목록"""
    a_set, b_set = set(a or []), set(b or [])
    union = a_set | b_set
    if not union:
        return 0.0, []
    common = sorted(a_set & b_set)
    return len(common) / len(union), common


def _schema_flow_score(
    out_schema: dict | None, in_schema: dict | None
) -> tuple[float, list[str]]:
    """
    out_schema의 프로퍼티 → in_schema의 프로퍼티 매칭 비율.
    in_schema의 required 필드가 커버되면 보너스 +0.3.
    """
    if not out_schema or not in_schema:
        return 0.0, []
    out_props = set((out_schema.get("properties") or {}).keys())
    in_props = set((in_schema.get("properties") or {}).keys())
    if not out_props or not in_props:
        return 0.0, []

    matched = sorted(out_props & in_props)
    if not matched:
        return 0.0, []

    required = set(in_schema.get("required") or [])
    covered = len(set(matched) & required) / len(required) if required else 0.0
    base = len(matched) / len(in_props)
    return round(min(1.0, base + covered * 0.3), 4), matched


def _suggested_flow(fwd: float, rev: float) -> str | None:
    threshold = 0.15
    if fwd >= threshold and rev >= threshold:
        return "parallel"
    if fwd >= threshold:
        return "after"   # source 먼저, 그 다음 candidate
    if rev >= threshold:
        return "before"  # candidate 먼저, 그 다음 source
    return None


def _score_pair(
    source: AgentORM, candidate: AgentORM
) -> tuple[float, float, float, float, list[str], str | None]:
    """
    Returns (final_score, tag_score, fwd_score, rev_score, reasons, suggested_flow)
    """
    reasons: list[str] = []

    ts, common_tags = _tag_score(source.tags, candidate.tags)
    if common_tags:
        reasons.append(f"공통 태그: {', '.join(common_tags)}")

    fwd, fwd_fields = _schema_flow_score(source.output_schema, candidate.input_schema)
    if fwd_fields:
        reasons.append(f"출력→입력 호환 필드: {', '.join(fwd_fields)}")

    rev, rev_fields = _schema_flow_score(candidate.output_schema, source.input_schema)
    if rev_fields:
        reasons.append(f"입력←출력 호환 필드: {', '.join(rev_fields)}")

    perf = candidate.success_rate
    if candidate.usage_count > 0:
        reasons.append(f"성공률 {perf * 100:.0f}% (실행 {candidate.usage_count}회)")

    role_bonus = 0.05 if frozenset({source.role, candidate.role}) in _COMPLEMENTARY else 0.0
    if role_bonus:
        reasons.append(f"역할 상호 보완: {source.role} ↔ {candidate.role}")

    final = round(min(1.0, 0.35 * ts + 0.30 * fwd + 0.15 * rev + 0.15 * perf + role_bonus), 4)
    flow = _suggested_flow(fwd, rev)

    return final, ts, fwd, rev, reasons, flow


# ── 랭킹 ─────────────────────────────────────────────────────────────────────

def rank_candidates(
    source: AgentORM,
    candidates: list[AgentORM],
    limit: int,
) -> list[SynergyCandidate]:
    results: list[SynergyCandidate] = []

    for c in candidates:
        if c.id == source.id:
            continue
        final, ts, fwd, rev, reasons, flow = _score_pair(source, c)
        # 점수가 0이라도 포함 (사용자가 참고할 수 있도록)
        results.append(
            SynergyCandidate(
                agent=AgentResponse.model_validate(c),
                score=final,
                tag_score=ts,
                schema_forward_score=fwd,
                schema_reverse_score=rev,
                reasons=reasons,
                suggested_flow=flow,
            )
        )

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:limit]


# ── Claude 분석 ───────────────────────────────────────────────────────────────

_ANALYSIS_SYSTEM = (
    "You are an AI agent workflow expert. "
    "Analyze synergy between agents and respond in Korean, concisely under 400 characters."
)


def _mock_analysis(source: AgentORM, candidates: list[SynergyCandidate]) -> str:
    if not candidates:
        return "추천할 수 있는 에이전트가 없습니다."
    top = candidates[0]
    return (
        f"[목업] {source.name}과 가장 잘 어울리는 에이전트는 {top.agent.name}입니다 "
        f"(점수 {top.score:.2f}). ANTHROPIC_API_KEY를 설정하면 Claude AI 심층 분석을 받을 수 있습니다."
    )


async def analyze_with_claude(
    source: AgentORM,
    candidates: list[SynergyCandidate],
) -> tuple[str, bool]:
    """Returns (analysis_text, is_mock)"""
    from app.core.config import settings

    if not settings.anthropic_api_key:
        return _mock_analysis(source, candidates), True

    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    source_info = {
        "name": source.name,
        "role": source.role,
        "goal": source.goal,
        "tags": source.tags or [],
        "output_fields": list(((source.output_schema or {}).get("properties") or {}).keys()),
    }
    cand_info = [
        {
            "name": c.agent.name,
            "role": c.agent.role,
            "score": c.score,
            "reasons": c.reasons,
            "suggested_flow": c.suggested_flow,
            "input_fields": list(((c.agent.input_schema or {}).get("properties") or {}).keys()),
        }
        for c in candidates
    ]

    user_msg = f"""기준 에이전트:
{json.dumps(source_info, ensure_ascii=False, indent=2)}

추천 후보 (점수 내림차순):
{json.dumps(cand_info, ensure_ascii=False, indent=2)}

다음을 간결하게 작성해주세요:
1. 상위 2~3개 에이전트와의 시너지 설명 (각 1문장)
2. 최적 실행 순서 제안
3. 이 조합으로 잘 해결되는 작업 유형 1~2가지"""

    response = await client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        thinking={"type": "adaptive"},
        system=_ANALYSIS_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = next(
        (block.text for block in response.content if hasattr(block, "text")),
        "",
    )
    return text.strip(), False


# ── 진입점 ────────────────────────────────────────────────────────────────────

async def get_synergy(
    source: AgentORM,
    candidates: list[AgentORM],
    limit: int = 5,
    use_claude: bool = False,
) -> SynergyResponse:
    ranked = rank_candidates(source, candidates, limit)

    claude_analysis: str | None = None
    is_mock = False

    if use_claude:
        claude_analysis, is_mock = await analyze_with_claude(source, ranked)

    return SynergyResponse(
        source_agent_id=source.id,
        candidates=ranked,
        claude_analysis=claude_analysis,
        is_mock_analysis=is_mock,
    )
