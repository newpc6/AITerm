from pydantic import BaseModel
from typing import Optional

from .user import User


class Session(BaseModel):
    id: str
    token: str
    user_id: str
    created_at: str
    expires_at: str


class AuthSettings(BaseModel):
    enabled: bool = False
    allow_password_login: bool = True
    session_ttl_hours: int = 24


class AuthSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    allow_password_login: Optional[bool] = None
    session_ttl_hours: Optional[int] = None


class AuthStatus(BaseModel):
    enabled: bool
    allow_password_login: bool
    authenticated: bool
    user: Optional[User] = None


class AuthLoginData(BaseModel):
    token: str
    expires_at: str
    user: User
