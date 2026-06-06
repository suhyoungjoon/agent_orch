from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    execution_mode: Literal["sequential", "hierarchical"] = "sequential"
    # React Flow 형식 노드/엣지를 그대로 수신
    nodes: list[dict] = []
    edges: list[dict] = []


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    execution_mode: Optional[Literal["sequential", "hierarchical"]] = None
    nodes: Optional[list[dict]] = None
    edges: Optional[list[dict]] = None
    status: Optional[str] = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    team_id: Optional[str]
    created_by: Optional[str]
    status: str
    execution_mode: str = "sequential"
    nodes: list[dict]
    edges: list[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
