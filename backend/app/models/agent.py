from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


AgentVisibility = Literal["public", "team", "private"]
LLMProvider = Literal["claude", "openai", "gemini", "local"]
MemoryType = Literal["none", "short", "long"]


class AgentBase(BaseModel):
    name: str
    role: str
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

    # 고급 스튜디오 필드
    llm_provider: LLMProvider = "claude"
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    system_prompt: Optional[str] = None
    memory_type: MemoryType = "none"
    context_window_size: Optional[int] = None
    max_retries: int = 1
    timeout_seconds: int = 120
    is_studio_agent: bool = False


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
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

    # 고급 스튜디오 필드
    llm_provider: Optional[LLMProvider] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    system_prompt: Optional[str] = None
    memory_type: Optional[MemoryType] = None
    context_window_size: Optional[int] = None
    max_retries: Optional[int] = None
    timeout_seconds: Optional[int] = None
    is_studio_agent: Optional[bool] = None


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

    # 고급 스튜디오 필드
    llm_provider: LLMProvider = "claude"
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    system_prompt: Optional[str] = None
    memory_type: MemoryType = "none"
    context_window_size: Optional[int] = None
    max_retries: int = 1
    timeout_seconds: int = 120
    is_studio_agent: bool = False

    model_config = {"from_attributes": True}
