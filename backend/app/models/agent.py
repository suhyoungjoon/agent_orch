from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from enum import Enum


class AgentRole(str, Enum):
    RESEARCHER = "researcher"
    WRITER = "writer"
    ANALYST = "analyst"
    CODER = "coder"


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


AgentVisibility = Literal["public", "team", "private"]


class AgentBase(BaseModel):
    name: str
    role: AgentRole
    goal: str
    backstory: str


class AgentCreate(AgentBase):
    description: Optional[str] = None
    team_id: Optional[str] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    tags: list[str] = Field(default_factory=list)
    version: str = "1.0.0"
    visibility: AgentVisibility = "team"


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[AgentRole] = None
    goal: Optional[str] = None
    backstory: Optional[str] = None
    description: Optional[str] = None
    status: Optional[AgentStatus] = None
    team_id: Optional[str] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    tags: Optional[list[str]] = None
    version: Optional[str] = None
    visibility: Optional[AgentVisibility] = None


class VisibilityUpdate(BaseModel):
    visibility: AgentVisibility


class AgentResponse(AgentBase):
    id: str
    status: AgentStatus = AgentStatus.IDLE
    description: Optional[str] = None

    team_id: Optional[str] = None
    visibility: AgentVisibility = "team"
    forked_from: Optional[str] = None

    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    tags: list[str] = Field(default_factory=list)

    version: str = "1.0.0"
    success_rate: float = 0.0
    usage_count: int = 0

    model_config = {"from_attributes": True}
