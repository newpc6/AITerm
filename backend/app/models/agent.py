from typing import List, Optional
from pydantic import BaseModel, Field


class Agent(BaseModel):
    id: str
    user_id: str
    name: str
    description: str = ""
    icon: str = "robot"
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    skill_ids: List[int] = Field(default_factory=list)
    system_prompt: str = ""
    temperature: float = 0.7
    max_iterations: int = 10
    extra_body_json: str = "{}"
    is_default: bool = False
    is_public: bool = False
    is_template: bool = False
    scope: str = "private"
    team_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    icon: str = "robot"
    model_id: Optional[str] = None
    skill_ids: List[int] = Field(default_factory=list)
    system_prompt: str = ""
    temperature: float = 0.7
    max_iterations: int = 10
    extra_body_json: str = "{}"
    is_public: bool = False
    is_template: bool = False
    scope: str = "private"


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    icon: Optional[str] = None
    model_id: Optional[str] = None
    skill_ids: Optional[List[int]] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_iterations: Optional[int] = None
    extra_body_json: Optional[str] = None
    is_public: Optional[bool] = None
    is_template: Optional[bool] = None
    scope: Optional[str] = None


class AgentWorkbenchRequest(BaseModel):
    agent_ids: List[str]
    message: str
    node_id: str = "1"
