from sqlalchemy import Column, Integer, String, Text, ForeignKey

from app.db.base import Base


class AgentMessageModel(Base):
    __tablename__ = "agent_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, default="")
    tool_calls_json = Column(Text, default="[]")
    created_at = Column(String(50), nullable=False)
