from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class DashboardSummary(BaseModel):
    total_agents: int
    total_runs: int
    completed_runs: int
    failed_runs: int
    running_runs: int
    success_rate: float
    total_tokens: int
    estimated_cost_usd: float


class MemberStat(BaseModel):
    user_id: str
    name: str
    email: str
    runs_count: int
    tokens_used: int
    estimated_cost_usd: float


class AgentStat(BaseModel):
    agent_id: str
    name: str
    role: str
    usage_count: int
    success_rate: float
    total_tokens: int
    avg_tokens_per_run: float
    estimated_cost_usd: float


class RunLog(BaseModel):
    run_id: str
    agent_id: str
    agent_name: Optional[str]
    task: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    user_name: Optional[str]
    model: Optional[str]


class TeamDashboardData(BaseModel):
    team_id: str
    team_name: str
    summary: DashboardSummary
    member_stats: list[MemberStat]
    agent_stats: list[AgentStat]
    recent_runs: list[RunLog]
