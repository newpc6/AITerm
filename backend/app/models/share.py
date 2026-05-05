from pydantic import BaseModel
from typing import Optional, List


class ShareCreate(BaseModel):
    chat_id: str
    title: Optional[str] = None
    password: Optional[str] = None
    expires_in: Optional[int] = None
    show_input: Optional[bool] = True
    show_thinking: Optional[bool] = True
    show_tools: Optional[bool] = True
    show_answer: Optional[bool] = True


class ShareVerify(BaseModel):
    share_id: str
    password: Optional[str] = None


class Share(BaseModel):
    id: str
    share_id: str
    chat_id: str
    title: str
    has_password: bool = False
    expires_at: Optional[str] = None
    view_count: int = 0
    created_at: Optional[str] = None
    show_input: bool = True
    show_thinking: bool = True
    show_tools: bool = True
    show_answer: bool = True


class ShareDetail(BaseModel):
    share_id: str
    title: str
    has_password: bool = False
    expires_at: Optional[str] = None
    messages: List[dict] = []
    chat_title: Optional[str] = None
    created_at: Optional[str] = None
    show_input: bool = True
    show_thinking: bool = True
    show_tools: bool = True
    show_answer: bool = True


class ShareListItem(BaseModel):
    id: str
    share_id: str
    chat_id: str
    title: str
    has_password: bool = False
    expires_at: Optional[str] = None
    view_count: int = 0
    created_at: Optional[str] = None
    show_input: bool = True
    show_thinking: bool = True
    show_tools: bool = True
    show_answer: bool = True
