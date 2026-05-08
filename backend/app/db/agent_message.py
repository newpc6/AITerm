from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.mysql import LONGTEXT
from datetime import datetime, timezone

from app.db.base import Base


class AgentMessageModel(Base):
    __tablename__ = "agent_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, default="")
    full_input = Column(LONGTEXT, nullable=True)
    created_at = Column(String(50), nullable=False)


class AgentMessagePartModel(Base):
    __tablename__ = "agent_message_parts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey(
        "agent_messages.id"), nullable=False)
    seq = Column(Integer, nullable=False, default=0)
    content = Column(LONGTEXT, nullable=False, default="{}")
    created_at = Column(String(50), nullable=False)
