from pydantic import BaseModel
from datetime import datetime


class EnterpriseOverview(BaseModel):
    total_teams: int
    total_agents: int
    total_workflows: int
    total_runs: int
    completed_runs: int
    failed_runs: int
    running_runs: int
    success_rate: float
    total_tokens: int
    estimated_cost_usd: float


class TeamReportStat(BaseModel):
    team_id: str
    team_name: str
    agent_count: int
    workflow_count: int
    run_count: int
    success_rate: float
    total_tokens: int
    estimated_cost_usd: float


class AgentRankEntry(BaseModel):
    agent_id: str
    name: str
    role: str
    team_name: str
    usage_count: int
    success_rate: float
    total_tokens: int
    estimated_cost_usd: float


class SynergyPair(BaseModel):
    agent_a_id: str
    agent_a_name: str
    agent_a_role: str
    agent_b_id: str
    agent_b_name: str
    agent_b_role: str
    workflow_count: int  # 이 쌍이 함께 사용된 워크플로 수


class ModelCostStat(BaseModel):
    model: str
    run_count: int
    total_tokens: int
    estimated_cost_usd: float
    cost_share: float  # 전체 비용 대비 비율


class DailyRunStat(BaseModel):
    date: str           # "YYYY-MM-DD"
    run_count: int
    success_count: int
    total_tokens: int
    estimated_cost_usd: float


class EnterpriseReportData(BaseModel):
    generated_at: datetime
    overview: EnterpriseOverview
    team_stats: list[TeamReportStat]          # 팀별 비교
    top_agents: list[AgentRankEntry]          # 상위 10개 에이전트
    synergy_pairs: list[SynergyPair]          # 워크플로 기반 시너지 페어 TOP 10
    model_cost_stats: list[ModelCostStat]     # 모델별 비용 분포
    daily_run_stats: list[DailyRunStat]       # 최근 14일 추이
