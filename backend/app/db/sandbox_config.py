from sqlalchemy import Column, Integer, String, Text, Float
from sqlalchemy.sql import func

from app.db.base import Base


class SandboxConfigModel(Base):
    __tablename__ = "sandbox_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mode = Column(String(20), nullable=False, default="sandbox")
    rules_prompt = Column(Text, nullable=False, default="")
    require_confirm = Column(Integer, nullable=False, default=1)
    max_file_size_mb = Column(Integer, nullable=False, default=100)
    docker_image = Column(String(200), nullable=False, default="python:3.11-slim")
    docker_network = Column(String(20), nullable=False, default="none")
    docker_memory = Column(String(20), nullable=False, default="512m")
    docker_cpu = Column(Float, nullable=False, default=1.0)
    docker_timeout = Column(Integer, nullable=False, default=300)
    docker_auto_remove = Column(Integer, nullable=False, default=1)
    updated_by = Column(String(100), nullable=True)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)


class SandboxPathModel(Base):
    __tablename__ = "sandbox_paths"

    id = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(String(500), nullable=False, unique=True)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)


class SandboxDangerousPatternModel(Base):
    __tablename__ = "sandbox_dangerous_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern = Column(String(200), nullable=False)
    description = Column(String(500), nullable=False, default="")
    scope = Column(String(20), nullable=False, default="sandbox")
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)


class SandboxCommandBlacklistModel(Base):
    __tablename__ = "sandbox_command_blacklist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command = Column(String(200), nullable=False, unique=True)
    scope = Column(String(20), nullable=False, default="sandbox")
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)


class SandboxCommandWhitelistModel(Base):
    __tablename__ = "sandbox_command_whitelist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command = Column(String(200), nullable=False, unique=True)
    scope = Column(String(20), nullable=False, default="sandbox")
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)
