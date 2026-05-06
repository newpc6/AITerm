from sqlalchemy import Column, Integer, String, Text
from datetime import datetime

from app.db.base import Base


class SystemDictModel(Base):
    __tablename__ = "system_dict"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=False, default="global", index=True)
    key = Column(String(100), nullable=False)
    value = Column(Text, nullable=False, default="")
    description = Column(String(500), nullable=False, default="")
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "description": self.description,
            "sort_order": self.sort_order,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class AuthSettingsModel(Base):
    __tablename__ = "auth_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    enabled = Column(Integer, nullable=False, default=1)
    allow_password_login = Column(Integer, nullable=False, default=1)
    session_ttl_hours = Column(Integer, nullable=False, default=24)

    def to_dict(self):
        return {
            "enabled": bool(self.enabled),
            "allow_password_login": bool(self.allow_password_login),
            "session_ttl_hours": self.session_ttl_hours
        }
