from typing import List, Optional
from pydantic import BaseModel, Field


class SandboxConfig(BaseModel):
    id: str
    mode: str = "sandbox"
    rules_prompt: str = ""
    require_confirm: bool = True
    max_file_size_mb: int = 100
    docker_image: str = "python:3.11-slim"
    docker_network: str = "none"
    docker_memory: str = "512m"
    docker_cpu: float = 1.0
    docker_timeout: int = 300
    docker_auto_remove: bool = True
    updated_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class SandboxConfigUpdate(BaseModel):
    mode: Optional[str] = None
    rules_prompt: Optional[str] = None
    require_confirm: Optional[bool] = None
    max_file_size_mb: Optional[int] = None
    docker_image: Optional[str] = None
    docker_network: Optional[str] = None
    docker_memory: Optional[str] = None
    docker_cpu: Optional[float] = None
    docker_timeout: Optional[int] = None
    docker_auto_remove: Optional[bool] = None


class SandboxPath(BaseModel):
    id: str
    path: str
    created_at: str = ""
    updated_at: str = ""


class SandboxPathCreate(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)


class SandboxPathUpdate(BaseModel):
    path: Optional[str] = Field(None, min_length=1, max_length=500)


class SandboxDangerousPattern(BaseModel):
    id: str
    pattern: str
    description: str = ""
    scope: str = "sandbox"
    created_at: str = ""
    updated_at: str = ""


class SandboxDangerousPatternCreate(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    scope: str = "sandbox"


class SandboxDangerousPatternUpdate(BaseModel):
    pattern: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    scope: Optional[str] = None


class SandboxCommandItem(BaseModel):
    id: str
    command: str
    scope: str = "sandbox"
    created_at: str = ""
    updated_at: str = ""


class SandboxCommandCreate(BaseModel):
    command: str = Field(..., min_length=1, max_length=200)
    scope: str = "sandbox"


class SandboxCommandUpdate(BaseModel):
    command: Optional[str] = Field(None, min_length=1, max_length=200)
    scope: Optional[str] = None


class SandboxFullConfig(BaseModel):
    config: SandboxConfig
    paths: List[SandboxPath]
    dangerous_patterns: List[SandboxDangerousPattern]
    command_blacklist: List[SandboxCommandItem]
    command_whitelist: List[SandboxCommandItem]
