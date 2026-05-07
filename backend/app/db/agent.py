from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey
from sqlalchemy.sql import func

from app.db.base import Base


class AgentModel(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    icon = Column(String(100), default="robot")
    model_id = Column(Integer, ForeignKey("model_configs.id"), nullable=True)
    skill_ids = Column(Text, default="[]")
    system_prompt = Column(Text, default="")
    temperature = Column(Float, default=0.7)
    max_iterations = Column(Integer, default=10)
    extra_body_json = Column(Text, default="{}")
    is_default = Column(Integer, default=0)
    is_public = Column(Integer, default=0)
    is_template = Column(Integer, default=0)
    scope = Column(String(20), default="private")
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)
