from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from datetime import datetime, timezone

from app.db.base import Base


class ShareModel(Base):
    __tablename__ = "shares"

    id = Column(Integer, primary_key=True, autoincrement=True)
    share_id = Column(String(32), unique=True, nullable=False, index=True)
    chat_id = Column(Integer, nullable=False, index=True)
    title = Column(String(500), nullable=False, default="")
    password = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    view_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    show_input = Column(Boolean, nullable=False, default=True)
    show_thinking = Column(Boolean, nullable=False, default=True)
    show_tools = Column(Boolean, nullable=False, default=True)
    show_answer = Column(Boolean, nullable=False, default=True)
    show_full_input = Column(Boolean, nullable=False, default=False)

    def to_dict(self):
        created_at_str = None
        if self.created_at:
            dt = self.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            created_at_str = dt.isoformat()

        expires_at_str = None
        if self.expires_at:
            dt = self.expires_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            expires_at_str = dt.isoformat()

        return {
            "id": str(self.id),
            "share_id": self.share_id,
            "chat_id": str(self.chat_id),
            "title": self.title,
            "has_password": bool(self.password),
            "expires_at": expires_at_str,
            "view_count": self.view_count,
            "created_at": created_at_str,
            "show_input": self.show_input,
            "show_thinking": self.show_thinking,
            "show_tools": self.show_tools,
            "show_answer": self.show_answer,
            "show_full_input": self.show_full_input,
        }
