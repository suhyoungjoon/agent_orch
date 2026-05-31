from pydantic import BaseModel
from typing import Optional
from enum import Enum
from datetime import datetime


class RunStatus(str, Enum):
    PENDING = "pending"
    PENDING_APPROVAL = "pending_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunRequest(BaseModel):
    task: str
    context: Optional[str] = None
    require_approval: bool = False


class ApprovalAction(BaseModel):
    note: Optional[str] = None


class RunResponse(BaseModel):
    run_id: str
    agent_id: str
    task: str
    status: RunStatus
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    user_id: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    model: Optional[str] = None
    input_sample: Optional[str] = None
    output_sample: Optional[str] = None
    duration_ms: Optional[float] = None
    context: Optional[str] = None
    approval_required: bool = False
    approval_status: Optional[str] = None
    approved_by: Optional[str] = None
    approval_note: Optional[str] = None
    approved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PendingRunResponse(RunResponse):
    agent_name: Optional[str] = None
    requester_name: Optional[str] = None
