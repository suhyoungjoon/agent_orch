from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Literal
from datetime import datetime


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    execution_mode: Literal["sequential", "hierarchical"] = "sequential"
    nodes: list[dict] = Field(default_factory=list, max_length=50)
    edges: list[dict] = Field(default_factory=list, max_length=200)

    @field_validator("name")
    @classmethod
    def name_no_whitespace_only(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("워크플로 이름은 공백만으로 구성될 수 없습니다.")
        return v.strip()

    @model_validator(mode="after")
    def edges_reference_valid_nodes(self) -> "WorkflowCreate":
        node_ids = {n.get("id") for n in self.nodes if n.get("id")}
        for edge in self.edges:
            src = edge.get("source")
            tgt = edge.get("target")
            if src and src not in node_ids:
                raise ValueError(f"엣지의 source '{src}'가 노드 목록에 없습니다.")
            if tgt and tgt not in node_ids:
                raise ValueError(f"엣지의 target '{tgt}'가 노드 목록에 없습니다.")
        return self


class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    execution_mode: Optional[Literal["sequential", "hierarchical"]] = None
    nodes: Optional[list[dict]] = Field(default=None, max_length=50)
    edges: Optional[list[dict]] = Field(default=None, max_length=200)
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("워크플로 이름은 공백만으로 구성될 수 없습니다.")
        return v.strip() if v else v


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
