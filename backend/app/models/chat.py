from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ChatStatus(str, Enum):
    IDLE = "idle"
    ANALYZING = "analyzing"
    EXECUTING = "executing"
    WAITING_INPUT = "waiting_input"
    WAITING_CONFIRM = "waiting_confirm"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageType(str, Enum):
    TEXT = "text"
    PLAN = "plan"
    STEP = "step"
    STEP_RESULT = "step_result"
    APPROVAL = "approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    INPUT = "input"
    INPUT_RESPONSE = "input_response"
    OUTPUT = "output"
    ERROR = "error"
    SUMMARY = "summary"
    ANALYSIS = "analysis"
    RETRY = "retry"


class PlanStepData(BaseModel):
    index: int
    title: str
    command: Optional[str] = None


class PlanMetadata(BaseModel):
    steps: List[PlanStepData]


class StepMetadata(BaseModel):
    index: int
    title: str
    command: str
    status: str = "pending"


class StepResultMetadata(BaseModel):
    index: int
    title: str
    command: str
    output: Optional[str] = None
    exit_code: int = 0
    success: bool = True


class ApprovalMetadata(BaseModel):
    commands: List[str]
    reason: str


class ApprovedMetadata(BaseModel):
    commands: List[str]


class RejectedMetadata(BaseModel):
    commands: List[str]
    reason: str


class InputMetadata(BaseModel):
    question: str
    input_type: str = "text"
    options: List[str] = []
    placeholder: str = ""


class InputResponseMetadata(BaseModel):
    question: str
    answer: str


class OutputMetadata(BaseModel):
    command: str
    output: Optional[str] = None
    exit_code: int = 0


class ErrorMetadata(BaseModel):
    message: str
    details: Optional[str] = None


class Message(BaseModel):
    id: str
    chat_id: str
    role: str
    type: str = MessageType.TEXT.value
    content: str
    created_at: Optional[str] = None


class Chat(BaseModel):
    id: str
    title: Optional[str] = None
    node_id: str = "1"
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    status: str = ChatStatus.IDLE.value
    summary: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ChatCreate(BaseModel):
    chat_id: Optional[str] = None
    node_id: str = "1"
    model_id: Optional[str] = None
    message: str


class ConversationCreate(BaseModel):
    conversation_id: Optional[str] = None
    node_id: str = "1"
    model_id: Optional[str] = None
    message: str
    mode: str = "chat"


class ChatUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None


class MessageCreate(BaseModel):
    chat_id: str
    role: str
    type: str = MessageType.TEXT.value
    content: str
