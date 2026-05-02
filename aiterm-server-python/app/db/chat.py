from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime, timezone

from app.db.base import Base


class ChatModel(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False, default="")
    node_id = Column(Integer, nullable=False, default=1)
    model_id = Column(Integer, nullable=True)
    model_name = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="idle")
    summary = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(
        timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        created_at_str = None
        if self.created_at:
            dt = self.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            created_at_str = dt.isoformat()

        updated_at_str = None
        if self.updated_at:
            dt = self.updated_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            updated_at_str = dt.isoformat()

        return {
            "id": str(self.id),
            "title": self.title,
            "node_id": str(self.node_id),
            "model_id": str(self.model_id) if self.model_id else None,
            "model_name": self.model_name,
            "status": self.status,
            "summary": self.summary,
            "created_at": created_at_str,
            "updated_at": updated_at_str
        }
