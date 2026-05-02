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
    extra_headers: Dict[str, Any] = {}
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
    extra_headers: Dict[str, Any] = {}
    is_default: bool = False


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    extra_params: Optional[Dict[str, Any]] = None
    extra_body: Optional[Dict[str, Any]] = None
    extra_headers: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None


class GlobalSettings(BaseModel):
    intent_detection_prompt: str = ""
    chat_system_prompt: str = ""
    chat_history_limit: int = 12
    execution_planner_prompt: str = ""
    execution_planner_user_prompt: str = ""
    execution_windows_tool_prompt: str = ""
    execution_linux_tool_prompt: str = ""
    execution_mac_tool_prompt: str = ""
    execution_failure_repair_prompt: str = ""
    execution_command_rules_prompt: str = ""
    execution_command_blacklist: List[str] = []
    execution_command_whitelist: List[str] = []
    sandbox_paths: List[str] = []
    sandbox_rules_prompt: str = ""
    llm_debug_logging: bool = False


class GlobalSettingsUpdate(BaseModel):
    intent_detection_prompt: Optional[str] = None
    chat_system_prompt: Optional[str] = None
    chat_history_limit: Optional[int] = None
    execution_planner_prompt: Optional[str] = None
    execution_planner_user_prompt: Optional[str] = None
    execution_windows_tool_prompt: Optional[str] = None
    execution_linux_tool_prompt: Optional[str] = None
    execution_mac_tool_prompt: Optional[str] = None
    execution_failure_repair_prompt: Optional[str] = None
    execution_command_rules_prompt: Optional[str] = None
    execution_command_blacklist: Optional[List[str]] = None
    execution_command_whitelist: Optional[List[str]] = None
    sandbox_paths: Optional[List[str]] = None
    sandbox_rules_prompt: Optional[str] = None
    llm_debug_logging: Optional[bool] = None
