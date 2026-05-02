from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime

from app.db.base import Base


class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(255), nullable=False, unique=True)
    user_id = Column(Integer, nullable=False)
    created_at = Column(String(50), nullable=False)
    expires_at = Column(String(50), nullable=False)

    def to_dict(self):
        return {
            "id": str(self.id),
            "token": self.token,
            "user_id": str(self.user_id),
            "created_at": self.created_at,
            "expires_at": self.expires_at
        }
