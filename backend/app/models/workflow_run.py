from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NodeRunResult(BaseModel):
    status: str  # "pending" | "running" | "completed" | "failed"
    agent_id: str
    agent_name: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None


class WorkflowRunRequest(BaseModel):
    task: str


class WorkflowRunResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    task: str
    node_results: dict  # node_id -> NodeRunResult dict
    error: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
