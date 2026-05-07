from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.db.base import Base


class ToolModel(Base):
    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    code = Column(Text, nullable=False)
    parameters = Column(Text, nullable=True)
    config_schema = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    sandbox_only = Column(Boolean, default=False, nullable=False)
    is_builtin = Column(Boolean, default=False, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    scope = Column(String(20), default="public", nullable=False)
    is_template = Column(Boolean, default=False, nullable=False)
    team_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(),
                        onupdate=func.now())


class UserToolModel(Base):
    __tablename__ = "user_tools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(),
                        onupdate=func.now())
