import json
import asyncio
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException

from app.models.common import Response, PaginatedResponse
from app.models.tool import (
    Tool,
    ToolCreate,
    ToolUpdate,
    ToolExecuteRequest,
    ToolExecuteResult,
    ToolParameters,
    ToolConfigSchema,
)
from app.repositories.tool import ToolRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tools", tags=["tools"])
tool_repo = ToolRepository()


@router.get("", response_model=Response[List[Tool]])
async def list_tools(enabled_only: bool = False):
    tools = await tool_repo.list_tools(enabled_only=enabled_only)
    return Response(data=tools)


@router.get("/{tool_id}", response_model=Response[Tool])
async def get_tool(tool_id: str):
    tool = await tool_repo.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return Response(data=tool)


@router.post("", response_model=Response[Tool])
async def create_tool(payload: ToolCreate):
    existing = await tool_repo.get_tool_by_name(payload.name)
    if existing:
        raise HTTPException(status_code=400, detail="Tool with this name already exists")

    tool = await tool_repo.create_tool(
        name=payload.name,
        display_name=payload.display_name,
        description=payload.description,
        code=payload.code,
        parameters=payload.parameters,
        config_schema=payload.config_schema,
        enabled=payload.enabled
    )
    return Response(data=tool)


@router.put("/{tool_id}", response_model=Response[Tool])
async def update_tool(tool_id: str, payload: ToolUpdate):
    tool = await tool_repo.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    if payload.name and payload.name != tool.name:
        existing = await tool_repo.get_tool_by_name(payload.name)
        if existing:
            raise HTTPException(status_code=400, detail="Tool with this name already exists")

    updated_tool = await tool_repo.update_tool(
        tool_id=tool_id,
        name=payload.name,
        display_name=payload.display_name,
        description=payload.description,
        code=payload.code,
        parameters=payload.parameters,
        config_schema=payload.config_schema,
        enabled=payload.enabled
    )
    return Response(data=updated_tool)


@router.delete("/{tool_id}", response_model=Response[bool])
async def delete_tool(tool_id: str):
    deleted = await tool_repo.delete_tool(tool_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tool not found")
    return Response(data=True)


@router.post("/{tool_id}/execute", response_model=Response[ToolExecuteResult])
async def execute_tool(tool_id: str, payload: ToolExecuteRequest):
    tool = await tool_repo.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    if not tool.enabled:
        raise HTTPException(status_code=400, detail="Tool is disabled")

    try:
        result = await _execute_tool_code(tool.code, payload.arguments)
        return Response(data=ToolExecuteResult(success=True, result=result))
    except Exception as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        return Response(data=ToolExecuteResult(success=False, error=str(e)))


async def _execute_tool_code(code: str, arguments: dict):
    local_vars = {"arguments": arguments, "result": None}
    
    wrapped_code = f"""
{code}

if 'execute' in dir():
    result = execute(arguments)
"""

    exec_globals = {
        "__builtins__": __builtins__,
        "json": json,
        "asyncio": asyncio,
    }
    
    exec(wrapped_code, exec_globals, local_vars)
    
    if asyncio.iscoroutine(local_vars.get("result")):
        return await local_vars["result"]
    
    return local_vars.get("result")


@router.get("/schema/openai", response_model=Response[List[dict]])
async def get_openai_tools_schema():
    tools = await tool_repo.list_tools(enabled_only=True)
    
    openai_tools = []
    for tool in tools:
        parameters = tool.parameters or ToolParameters()
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or tool.display_name or tool.name,
                "parameters": parameters.model_dump()
            }
        }
        openai_tools.append(openai_tool)
    
    return Response(data=openai_tools)
