from sqlalchemy import Column, Integer, String, Text
from datetime import datetime

from app.db.base import Base


class ModelConfigModel(Base):
    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    api_url = Column(String(500), nullable=False)
    api_key = Column(String(500), nullable=False, default="")
    model = Column(String(255), nullable=False)
    temperature = Column(Integer, nullable=False, default=70)
    context_length = Column(Integer, nullable=True)
    extra_params_json = Column(Text, nullable=False, default="{}")
    extra_body_json = Column(Text, nullable=False, default="{}")
    extra_headers_json = Column(Text, nullable=False, default="{}")
    is_default = Column(Integer, nullable=False, default=0)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "api_url": self.api_url,
            "api_key": self.api_key,
            "model": self.model,
            "temperature": self.temperature / 100.0,
            "context_length": self.context_length,
            "extra_params_json": self.extra_params_json,
            "extra_body_json": self.extra_body_json,
            "extra_headers_json": self.extra_headers_json,
            "is_default": bool(self.is_default),
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


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
