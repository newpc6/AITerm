from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ToolParameter(BaseModel):
    type: str = "string"
    description: str = ""
    enum: Optional[List[str]] = None
    default: Optional[Any] = None


class ToolParameters(BaseModel):
    type: str = "object"
    properties: Dict[str, ToolParameter] = Field(default_factory=dict)
    required: Optional[List[str]] = Field(default_factory=list)


class ToolConfigField(BaseModel):
    name: str
    display_name: str
    type: str = "string"
    description: str = ""
    default: Optional[str] = None
    required: bool = True


class ToolConfigSchema(BaseModel):
    fields: List[ToolConfigField] = Field(default_factory=list)


class Tool(BaseModel):
    id: str
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    code: str
    parameters: Optional[ToolParameters] = None
    config_schema: Optional[ToolConfigSchema] = None
    enabled: bool = True
    sandbox_only: bool = False
    is_builtin: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ToolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    code: str = Field(..., min_length=1)
    parameters: Optional[ToolParameters] = None
    config_schema: Optional[ToolConfigSchema] = None
    enabled: bool = True
    sandbox_only: bool = False
    is_builtin: bool = False


class ToolUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    code: Optional[str] = Field(None, min_length=1)
    parameters: Optional[ToolParameters] = None
    config_schema: Optional[ToolConfigSchema] = None
    enabled: Optional[bool] = None
    sandbox_only: Optional[bool] = None


class ToolExecuteRequest(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolExecuteResult(BaseModel):
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]


class ToolCallResult(BaseModel):
    tool_call_id: str
    name: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


class ToolExport(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    code: str
    parameters: Optional[ToolParameters] = None
    config_schema: Optional[ToolConfigSchema] = None
    enabled: bool = True
    sandbox_only: bool = False
    is_builtin: bool = False


class ToolImportResult(BaseModel):
    name: str
    success: bool
    error: Optional[str] = None
    action: Optional[str] = None


class ToolsImportResponse(BaseModel):
    total: int
    imported: int
    skipped: int
    failed: int
    results: List[ToolImportResult]


class BuiltinTool(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    filename: str
