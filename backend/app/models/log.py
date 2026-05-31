from pydantic import BaseModel
from typing import Optional
from enum import Enum
from datetime import datetime


class LogLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class LogResponse(BaseModel):
    id: str
    run_id: Optional[str] = None
    level: LogLevel
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}
