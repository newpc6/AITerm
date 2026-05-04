from pydantic import BaseModel
from typing import Optional

from .enums import UserRole, UserStatus


class User(BaseModel):
    id: str
    username: str
    display_name: str
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.ACTIVE
    last_login_at: Optional[str] = None
    created_at: str
    updated_at: str


class UserCreate(BaseModel):
    username: str
    display_name: str
    password: str
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.ACTIVE


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserResetPassword(BaseModel):
    password: str


class AuthChangePassword(BaseModel):
    current_password: str
    new_password: str
