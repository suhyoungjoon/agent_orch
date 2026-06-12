from pydantic import BaseModel, Field, field_validator
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
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=50)
    goal: str = Field(min_length=1, max_length=500)
    backstory: str = Field(min_length=1, max_length=1000)

    @field_validator("name", "role")
    @classmethod
    def no_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("공백만으로 구성될 수 없습니다.")
        return v.strip()


class AgentCreate(AgentBase):
    description: Optional[str] = Field(default=None, max_length=500)
    team_id: Optional[str] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    tags: list[str] = Field(default_factory=list, max_length=20)
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    visibility: AgentVisibility = "team"

    # 고급 스튜디오 필드
    llm_provider: LLMProvider = "claude"
    model_name: Optional[str] = Field(default=None, max_length=100)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=32000)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    system_prompt: Optional[str] = Field(default=None, max_length=10000)
    memory_type: MemoryType = "none"
    context_window_size: Optional[int] = Field(default=None, ge=1, le=200000)
    max_retries: int = Field(default=1, ge=1, le=20)
    timeout_seconds: int = Field(default=120, ge=10, le=600)
    is_studio_agent: bool = False


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    role: Optional[str] = Field(default=None, min_length=1, max_length=50)
    goal: Optional[str] = Field(default=None, min_length=1, max_length=500)
    backstory: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    description: Optional[str] = Field(default=None, max_length=500)
    status: Optional[AgentStatus] = None
    team_id: Optional[str] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    tags: Optional[list[str]] = Field(default=None, max_length=20)
    version: Optional[str] = Field(default=None, pattern=r"^\d+\.\d+\.\d+$")
    visibility: Optional[AgentVisibility] = None

    # 고급 스튜디오 필드
    llm_provider: Optional[LLMProvider] = None
    model_name: Optional[str] = Field(default=None, max_length=100)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=32000)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    system_prompt: Optional[str] = Field(default=None, max_length=10000)
    memory_type: Optional[MemoryType] = None
    context_window_size: Optional[int] = Field(default=None, ge=1, le=200000)
    max_retries: Optional[int] = Field(default=None, ge=1, le=20)
    timeout_seconds: Optional[int] = Field(default=None, ge=10, le=600)
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
