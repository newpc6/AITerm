from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.sql import func

from app.db.base import Base


class SkillTemplateModel(Base):
    __tablename__ = "skill_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255), default="")
    description = Column(Text, default="")
    version = Column(String(20), default="1.0.0")
    category = Column(String(50), default="custom")
    system_prompt = Column(Text, default="")
    tool_names = Column(Text, default="[]")
    config_json = Column(Text, default="{}")
    status = Column(String(20), default="draft")
    review_comment = Column(Text, default="")
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_default = Column(Integer, default=0)
    is_public = Column(Integer, default=0)
    scope = Column(String(20), default="private")
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)


class UserSkillModel(Base):
    __tablename__ = "user_skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("skill_templates.id"), nullable=False)
    is_active = Column(Integer, default=1)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)
