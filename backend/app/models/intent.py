from pydantic import BaseModel
from typing import Optional


class ParseIntentRequest(BaseModel):
    text: str = ""
    input: str = ""   # 프론트엔드 호환 별칭

    def get_text(self) -> str:
        return self.text or self.input


class AgentConfig(BaseModel):
    name: str
    role: str
    goal: str
    tools: list[str]
    execution_order: int


class ParseIntentResponse(BaseModel):
    agents: list[AgentConfig]
    raw_input: str
    model_used: Optional[str] = None
    is_mock: bool = False
