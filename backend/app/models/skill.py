from typing import List, Optional
from pydantic import BaseModel, Field


class SkillTemplate(BaseModel):
    id: str
    user_id: str
    name: str
    display_name: str = ""
    description: str = ""
    version: str = "1.0.0"
    category: str = "custom"
    system_prompt: str = ""
    tool_names: List[str] = Field(default_factory=list)
    config_json: str = "{}"
    status: str = "draft"
    review_comment: str = ""
    reviewed_by: Optional[str] = None
    is_default: bool = False
    is_public: bool = False
    scope: str = "private"
    team_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: str = ""
    description: str = ""
    version: str = "1.0.0"
    category: str = "custom"
    system_prompt: str = ""
    tool_names: List[str] = Field(default_factory=list)
    config_json: str = "{}"


class SkillUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    display_name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    category: Optional[str] = None
    system_prompt: Optional[str] = None
    tool_names: Optional[List[str]] = None
    config_json: Optional[str] = None


class SkillReview(BaseModel):
    approved: bool
    comment: str = ""
