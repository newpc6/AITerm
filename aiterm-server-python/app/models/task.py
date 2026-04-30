from pydantic import BaseModel
from typing import List, Optional

from .enums import TaskStatus, TaskStepStatus


class TaskStep(BaseModel):
    index: int = 0
    title: str = ""
    status: TaskStepStatus = TaskStepStatus.PENDING
    command: str = ""
    result_output: Optional[str] = None
    repair_count: int = 0
    original_command: Optional[str] = None
    first_failure_output: Optional[str] = None
    repaired_output: Optional[str] = None
    last_error: Optional[str] = None
    repair_reason: Optional[str] = None
    repair_suggestion: Optional[str] = None
    repaired_command: Optional[str] = None


class Task(BaseModel):
    id: str
    title: str
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    conversation_id: str
    node_id: str
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    request: str = ""
    pending_command: Optional[str] = None
    risk_reason: Optional[str] = None
    summary: str = ""
    final_result: Optional[str] = None
    steps: List[TaskStep] = []
    input_question: Optional[str] = None
    input_type: Optional[str] = None
    input_options: List[str] = []
    input_placeholder: Optional[str] = None
    user_input: Optional[str] = None
    created_at: str
    updated_at: str


class TaskCreate(BaseModel):
    conversation_id: Optional[str] = None
    node_id: str = "1"
    model_id: Optional[str] = None
    request: str


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[TaskStatus] = None
    progress: Optional[int] = None
    summary: Optional[str] = None
    steps: Optional[List[TaskStep]] = None


class TaskConfirmRequest(BaseModel):
    approved: bool


class TaskInputRequest(BaseModel):
    user_input: str


class TaskPlanStep(BaseModel):
    title: str = ""
    command: str = ""


class UserInputRequest(BaseModel):
    question: str = ""
    input_type: str = "text"
    options: List[str] = []
    placeholder: str = ""
    default_value: str = ""


class TaskPlanResult(BaseModel):
    title: str = ""
    summary: str = ""
    requires_confirmation: bool = False
    risk_reason: str = ""
    needs_user_input: bool = False
    input_request: Optional[UserInputRequest] = None
    steps: List[TaskPlanStep] = []


class TaskFailureRepairResult(BaseModel):
    reason: str = ""
    suggestion: str = ""
    corrected_title: str = ""
    corrected_command: str = ""
