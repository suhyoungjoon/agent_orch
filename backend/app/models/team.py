from pydantic import BaseModel
from typing import Literal
from datetime import datetime


class TeamCreate(BaseModel):
    name: str


class TeamResponse(BaseModel):
    id: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AddMemberRequest(BaseModel):
    email: str
    role: Literal["admin", "member", "viewer"] = "member"


class UpdateRoleRequest(BaseModel):
    role: Literal["admin", "member", "viewer"]
