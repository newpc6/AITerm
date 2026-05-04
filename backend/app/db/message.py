from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime, timezone
import json

from app.db.base import Base


class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, nullable=False)
    role = Column(String(50), nullable=False)
    type = Column(String(50), nullable=False, default="text")
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        created_at_str = None
        if self.created_at:
            dt = self.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            created_at_str = dt.isoformat()

        return {
            "id": str(self.id),
            "chat_id": str(self.chat_id),
            "role": self.role,
            "type": self.type,
            "content": self.content,
            "created_at": created_at_str
        }
