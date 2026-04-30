from pydantic import BaseModel
from typing import Optional, List

from .enums import ConversationMode


class ConversationMessage(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: str


class Conversation(BaseModel):
    id: str
    title: Optional[str] = None
    last_message: Optional[str] = None
    message_count: int = 0
    latest_task_id: Optional[str] = None
    latest_node_id: Optional[str] = None
    latest_status: Optional[str] = None
    updated_at: Optional[str] = None
    created_at: Optional[str] = None


class ConversationCreate(BaseModel):
    conversation_id: Optional[str] = None
    node_id: str = "1"
    model_id: Optional[str] = None
    message: str
    mode: ConversationMode = ConversationMode.TASK
