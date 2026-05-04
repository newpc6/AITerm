from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func

from app.db.base import Base


class ToolModel(Base):
    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    code = Column(Text, nullable=False)
    parameters = Column(Text, nullable=True)
    config_schema = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    sandbox_only = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
