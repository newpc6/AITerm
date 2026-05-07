from typing import List, Optional
from pydantic import BaseModel


class TeamCreate(BaseModel):
    name: str
    description: str = ""


class TeamMemberAdd(BaseModel):
    user_id: str
    role: str = "member"


class TeamMemberRole(BaseModel):
    role: str
