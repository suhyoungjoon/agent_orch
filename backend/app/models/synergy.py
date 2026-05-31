from pydantic import BaseModel
from app.models.agent import AgentResponse


class SynergyCandidate(BaseModel):
    agent: AgentResponse
    score: float                    # 0.0 ~ 1.0 종합 점수
    tag_score: float                # Jaccard 태그 유사도
    schema_forward_score: float     # source.output → candidate.input 호환도
    schema_reverse_score: float     # candidate.output → source.input 호환도
    reasons: list[str]              # 사람이 읽을 수 있는 근거
    suggested_flow: str | None      # "before" | "after" | "parallel" | None


class SynergyResponse(BaseModel):
    source_agent_id: str
    candidates: list[SynergyCandidate]
    claude_analysis: str | None = None
    is_mock_analysis: bool = False
