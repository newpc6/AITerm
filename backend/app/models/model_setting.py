from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, Any


class ApiType(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class ThinkingType(str, Enum):
    DEFAULT = "default"
    ENABLED = "enabled"
    AUTO = "auto"
    DISABLED = "disabled"


class ModelConfig(BaseModel):
    id: str
    name: str
    api_type: str = "openai"
    api_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    context_length: Optional[int] = None
    thinking_type: str = "default"
    extra_params: Dict[str, Any] = {}
    extra_body: Dict[str, Any] = {}
    extra_headers: Dict[str, Any] = {}
    is_default: bool = False
    user_id: Optional[str] = None
    scope: str = "private"
    team_id: Optional[str] = None
    created_at: str
    updated_at: str


class ModelConfigCreate(BaseModel):
    name: str
    api_type: str = "openai"
    api_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    context_length: Optional[int] = None
    thinking_type: str = "default"
    extra_params: Dict[str, Any] = {}
    extra_body: Dict[str, Any] = {}
    extra_headers: Dict[str, Any] = {}
    is_default: bool = False


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    api_type: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    context_length: Optional[int] = None
    thinking_type: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None
    extra_body: Optional[Dict[str, Any]] = None
    extra_headers: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None
