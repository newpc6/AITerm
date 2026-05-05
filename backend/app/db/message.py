from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime, timezone

from app.db.base import Base


class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, nullable=False)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False, default="{}")
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
            "content": self.content,
            "created_at": created_at_str
        }


class MessagePartModel(Base):
    __tablename__ = "message_parts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, nullable=False)
    seq = Column(Integer, nullable=False, default=0)
    content = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": str(self.id),
            "message_id": str(self.message_id),
            "seq": self.seq,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
