from sqlalchemy import Column, Integer, String, Float, Text, Boolean
from datetime import datetime

from app.db import Base


class ModelConfigModel(Base):
    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    api_url = Column(String(500), nullable=False)
    api_key = Column(String(500), nullable=False, default="")
    model = Column(String(255), nullable=False)
    temperature = Column(Float, nullable=False, default=0.7)
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
            "temperature": self.temperature,
            "extra_params_json": self.extra_params_json,
            "extra_body_json": self.extra_body_json,
            "extra_headers_json": self.extra_headers_json,
            "is_default": bool(self.is_default),
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class GlobalSettingsModel(Base):
    __tablename__ = "global_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_system_prompt = Column(Text, nullable=False, default="")
    task_planner_prompt = Column(Text, nullable=False, default="")
    task_planner_user_prompt = Column(Text, nullable=False, default="")
    task_windows_tool_prompt = Column(Text, nullable=False, default="")
    task_linux_tool_prompt = Column(Text, nullable=False, default="")
    task_mac_tool_prompt = Column(Text, nullable=False, default="")
    task_failure_repair_prompt = Column(Text, nullable=False, default="")
    task_command_rules_prompt = Column(Text, nullable=False, default="")
    task_command_blacklist_json = Column(Text, nullable=False, default="[]")
    task_command_whitelist_json = Column(Text, nullable=False, default="[]")

    def to_dict(self):
        return {
            "chat_system_prompt": self.chat_system_prompt,
            "task_planner_prompt": self.task_planner_prompt,
            "task_planner_user_prompt": self.task_planner_user_prompt,
            "task_windows_tool_prompt": self.task_windows_tool_prompt,
            "task_linux_tool_prompt": self.task_linux_tool_prompt,
            "task_mac_tool_prompt": self.task_mac_tool_prompt,
            "task_failure_repair_prompt": self.task_failure_repair_prompt,
            "task_command_rules_prompt": self.task_command_rules_prompt,
            "task_command_blacklist_json": self.task_command_blacklist_json,
            "task_command_whitelist_json": self.task_command_whitelist_json
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
