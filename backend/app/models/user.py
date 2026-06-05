from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: Literal["admin", "member", "viewer"]
    team_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    team_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class OAuthSyncRequest(BaseModel):
    email: str
    name: str
    provider: str
    provider_id: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AdminResetPasswordRequest(BaseModel):
    new_password: str
