from typing import List, Optional
from pydantic import BaseModel, Field


class ScheduledTask(BaseModel):
    id: str
    user_id: str
    username: str = ""
    name: str
    description: str = ""
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    input_message: str
    enabled: bool = True
    cron_expression: str
    node_id: Optional[str] = None
    max_retries: int = 0
    timeout_seconds: int = 300
    last_run_at: Optional[str] = None
    last_result: Optional[str] = None
    next_run_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class ScheduledTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    agent_id: Optional[str] = None
    input_message: str = Field(..., min_length=1)
    enabled: bool = True
    cron_expression: str = Field(..., min_length=1)
    node_id: Optional[str] = None
    max_retries: int = 0
    timeout_seconds: int = 300


class ScheduledTaskUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    agent_id: Optional[str] = None
    input_message: Optional[str] = None
    enabled: Optional[bool] = None
    cron_expression: Optional[str] = None
    node_id: Optional[str] = None
    max_retries: Optional[int] = None
    timeout_seconds: Optional[int] = None


class ScheduledTaskLog(BaseModel):
    id: str
    task_id: str
    status: str
    output: str = ""
    error: str = ""
    started_at: str
    finished_at: Optional[str] = None
    created_at: str = ""
