from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class ModelConfig(BaseModel):
    id: str
    name: str
    api_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    extra_params: Dict[str, Any] = {}
    extra_body: Dict[str, Any] = {}
    extra_headers: Dict[str, str] = {}
    is_default: bool = False
    created_at: str
    updated_at: str


class ModelConfigCreate(BaseModel):
    name: str
    api_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    extra_params: Dict[str, Any] = {}
    extra_body: Dict[str, Any] = {}
    extra_headers: Dict[str, str] = {}
    is_default: bool = False


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    extra_params: Optional[Dict[str, Any]] = None
    extra_body: Optional[Dict[str, Any]] = None
    extra_headers: Optional[Dict[str, str]] = None
    is_default: Optional[bool] = None


class GlobalSettings(BaseModel):
    chat_system_prompt: str = ""
    task_planner_prompt: str = ""
    task_planner_user_prompt: str = ""
    task_windows_tool_prompt: str = ""
    task_linux_tool_prompt: str = ""
    task_mac_tool_prompt: str = ""
    task_failure_repair_prompt: str = ""
    task_command_rules_prompt: str = ""
    task_command_blacklist: List[str] = []
    task_command_whitelist: List[str] = []


class GlobalSettingsUpdate(BaseModel):
    chat_system_prompt: Optional[str] = None
    task_planner_prompt: Optional[str] = None
    task_planner_user_prompt: Optional[str] = None
    task_windows_tool_prompt: Optional[str] = None
    task_linux_tool_prompt: Optional[str] = None
    task_mac_tool_prompt: Optional[str] = None
    task_failure_repair_prompt: Optional[str] = None
    task_command_rules_prompt: Optional[str] = None
    task_command_blacklist: Optional[List[str]] = None
    task_command_whitelist: Optional[List[str]] = None
