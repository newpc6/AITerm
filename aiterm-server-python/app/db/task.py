from sqlalchemy import Column, Integer, String, Text
from datetime import datetime

from app.db import Base


class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    progress = Column(Integer, nullable=False, default=0)
    conversation_id = Column(Integer, nullable=False)
    node_id = Column(Integer, nullable=False)
    model_id = Column(Integer, nullable=True)
    model_name = Column(String(255), nullable=True)
    request = Column(Text, nullable=False, default="")
    pending_command = Column(Text, nullable=True)
    risk_reason = Column(Text, nullable=True)
    summary = Column(Text, nullable=False, default="")
    steps_json = Column(Text, nullable=False, default="[]")
    final_result = Column(Text, nullable=False, default="")
    input_question = Column(Text, nullable=True)
    input_type = Column(String(50), nullable=True)
    input_options_json = Column(Text, nullable=False, default="[]")
    input_placeholder = Column(String(500), nullable=True)
    user_input = Column(Text, nullable=True)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)

    def to_dict(self):
        return {
            "id": str(self.id),
            "title": self.title,
            "status": self.status,
            "progress": self.progress,
            "conversation_id": str(self.conversation_id),
            "node_id": str(self.node_id),
            "model_id": str(self.model_id) if self.model_id else None,
            "model_name": self.model_name,
            "request": self.request,
            "pending_command": self.pending_command,
            "risk_reason": self.risk_reason,
            "summary": self.summary,
            "steps_json": self.steps_json,
            "final_result": self.final_result,
            "input_question": self.input_question,
            "input_type": self.input_type,
            "input_options_json": self.input_options_json,
            "input_placeholder": self.input_placeholder,
            "user_input": self.user_input,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
