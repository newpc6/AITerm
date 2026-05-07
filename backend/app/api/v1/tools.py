import json
import asyncio
import logging
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

from app.models.common import Response, PaginatedResponse
from app.models.tool import (
    Tool,
    ToolCreate,
    ToolUpdate,
    ToolExecuteRequest,
    ToolExecuteResult,
    ToolParameters,
    ToolConfigSchema,
    ToolImportResult,
    ToolExport,
    ToolsImportResponse,
    BuiltinTool,
)
from app.repositories.tool import ToolRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tools", tags=["tools"])
tool_repo = ToolRepository()
BUILTIN_TOOLS_DIR = Path(__file__).parent.parent.parent.parent / "tools"


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
        raise HTTPException(
            status_code=400, detail="Tool with this name already exists")

    tool = await tool_repo.create_tool(
        name=payload.name,
        display_name=payload.display_name,
        description=payload.description,
        code=payload.code,
        parameters=payload.parameters,
        config_schema=payload.config_schema,
        enabled=payload.enabled,
        sandbox_only=payload.sandbox_only
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
            raise HTTPException(
                status_code=400, detail="Tool with this name already exists")

    updated_tool = await tool_repo.update_tool(
        tool_id=tool_id,
        name=payload.name,
        display_name=payload.display_name,
        description=payload.description,
        code=payload.code,
        parameters=payload.parameters,
        config_schema=payload.config_schema,
        enabled=payload.enabled,
        sandbox_only=payload.sandbox_only
    )
    return Response(data=updated_tool)


@router.delete("/{tool_id}", response_model=Response[bool])
async def delete_tool(tool_id: str):
    tool = await tool_repo.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if tool.is_builtin:
        raise HTTPException(status_code=403, detail="Built-in tools cannot be deleted")
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


@router.post("/export", response_class=JSONResponse)
async def export_tools(tool_ids: List[str] = None):
    tools = await tool_repo.list_tools(enabled_only=False)

    if tool_ids:
        tools = [t for t in tools if t.id in tool_ids]

    export_data = []
    for tool in tools:
        export_item = ToolExport(
            name=tool.name,
            display_name=tool.display_name,
            description=tool.description,
            code=tool.code,
            parameters=tool.parameters,
            config_schema=tool.config_schema,
            enabled=tool.enabled,
            sandbox_only=tool.sandbox_only
        )
        export_data.append(export_item.model_dump())

    return JSONResponse(
        content={
            "code": 0,
            "message": "ok",
            "data": export_data
        },
        headers={
            "Content-Disposition": "attachment; filename=tools_export.json"
        }
    )


@router.post("/import", response_model=Response[ToolsImportResponse])
async def import_tools(
    file: UploadFile = File(None),
    json_content: str = Form(None),
    overwrite: bool = Form(False)
):
    tools_data = []

    if file:
        content = await file.read()
        try:
            data = json.loads(content.decode('utf-8'))
            if isinstance(data, list):
                tools_data = data
            elif isinstance(data, dict):
                if 'data' in data:
                    tools_data = data['data']
                elif 'name' in data:
                    tools_data = [data]
                else:
                    raise HTTPException(status_code=400, detail="Invalid JSON format: missing 'name' field")
            else:
                raise HTTPException(status_code=400, detail="Invalid JSON format")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON file")
    elif json_content:
        try:
            data = json.loads(json_content)
            if isinstance(data, list):
                tools_data = data
            elif isinstance(data, dict):
                if 'data' in data:
                    tools_data = data['data']
                elif 'name' in data:
                    tools_data = [data]
                else:
                    raise HTTPException(status_code=400, detail="Invalid JSON format: missing 'name' field")
            else:
                raise HTTPException(status_code=400, detail="Invalid JSON format")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON content")
    else:
        raise HTTPException(status_code=400, detail="Please provide a file or JSON content")

    results = []
    imported = 0
    skipped = 0
    failed = 0

    for tool_data in tools_data:
        name = tool_data.get('name', '')
        if not name:
            results.append(ToolImportResult(
                name='unknown',
                success=False,
                error="Missing tool name"
            ))
            failed += 1
            continue

        try:
            existing = await tool_repo.get_tool_by_name(name)

            if existing:
                if overwrite:
                    await tool_repo.update_tool(
                        tool_id=existing.id,
                        name=name,
                        display_name=tool_data.get('display_name'),
                        description=tool_data.get('description'),
                        code=tool_data.get('code', ''),
                        parameters=tool_data.get('parameters'),
                        config_schema=tool_data.get('config_schema'),
                        enabled=tool_data.get('enabled', True),
                        sandbox_only=tool_data.get('sandbox_only', False)
                    )
                    results.append(ToolImportResult(
                        name=name,
                        success=True,
                        action="updated"
                    ))
                    imported += 1
                else:
                    results.append(ToolImportResult(
                        name=name,
                        success=False,
                        error="Tool already exists",
                        action="skipped"
                    ))
                    skipped += 1
            else:
                await tool_repo.create_tool(
                    name=name,
                    display_name=tool_data.get('display_name'),
                    description=tool_data.get('description'),
                    code=tool_data.get('code', ''),
                    parameters=tool_data.get('parameters'),
                    config_schema=tool_data.get('config_schema'),
                    enabled=tool_data.get('enabled', True),
                    sandbox_only=tool_data.get('sandbox_only', False)
                )
                results.append(ToolImportResult(
                    name=name,
                    success=True,
                    action="created"
                ))
                imported += 1
        except Exception as e:
            results.append(ToolImportResult(
                name=name,
                success=False,
                error=str(e)
            ))
            failed += 1

    return Response(data=ToolsImportResponse(
        total=len(tools_data),
        imported=imported,
        skipped=skipped,
        failed=failed,
        results=results
    ))


@router.get("/builtin/list", response_model=Response[List[BuiltinTool]])
async def list_builtin_tools():
    builtin_tools = []

    if BUILTIN_TOOLS_DIR.exists():
        for file_path in BUILTIN_TOOLS_DIR.glob("*.json"):
            try:
                content = file_path.read_text(encoding='utf-8')
                data = json.loads(content)
                builtin_tools.append(BuiltinTool(
                    name=data.get('name', file_path.stem),
                    display_name=data.get('display_name'),
                    description=data.get('description'),
                    filename=file_path.name
                ))
            except Exception as e:
                logger.warning(f"Failed to load builtin tool {file_path}: {e}")

    return Response(data=builtin_tools)


@router.post("/builtin/import", response_model=Response[ToolsImportResponse])
async def import_builtin_tools(filenames: List[str], overwrite: bool = False):
    tools_data = []

    for filename in filenames:
        file_path = BUILTIN_TOOLS_DIR / filename
        if not file_path.exists():
            continue

        try:
            content = file_path.read_text(encoding='utf-8')
            data = json.loads(content)
            tools_data.append(data)
        except Exception as e:
            logger.warning(f"Failed to load builtin tool {file_path}: {e}")

    if not tools_data:
        raise HTTPException(
            status_code=400, detail="No valid builtin tools found")

    results = []
    imported = 0
    skipped = 0
    failed = 0

    for tool_data in tools_data:
        name = tool_data.get('name', '')
        if not name:
            results.append(ToolImportResult(
                name='unknown',
                success=False,
                error="Missing tool name"
            ))
            failed += 1
            continue

        try:
            existing = await tool_repo.get_tool_by_name(name)

            if existing:
                if overwrite:
                    await tool_repo.update_tool(
                        tool_id=existing.id,
                        name=name,
                        display_name=tool_data.get('display_name'),
                        description=tool_data.get('description'),
                        code=tool_data.get('code', ''),
                        parameters=tool_data.get('parameters'),
                        config_schema=tool_data.get('config_schema'),
                        enabled=tool_data.get('enabled', True),
                        sandbox_only=tool_data.get('sandbox_only', False)
                    )
                    results.append(ToolImportResult(
                        name=name,
                        success=True,
                        action="updated"
                    ))
                    imported += 1
                else:
                    results.append(ToolImportResult(
                        name=name,
                        success=False,
                        error="Tool already exists",
                        action="skipped"
                    ))
                    skipped += 1
            else:
                await tool_repo.create_tool(
                    name=name,
                    display_name=tool_data.get('display_name'),
                    description=tool_data.get('description'),
                    code=tool_data.get('code', ''),
                    parameters=tool_data.get('parameters'),
                    config_schema=tool_data.get('config_schema'),
                    enabled=tool_data.get('enabled', True),
                    sandbox_only=tool_data.get('sandbox_only', False)
                )
                results.append(ToolImportResult(
                    name=name,
                    success=True,
                    action="created"
                ))
                imported += 1
        except Exception as e:
            results.append(ToolImportResult(
                name=name,
                success=False,
                error=str(e)
            ))
            failed += 1

    return Response(data=ToolsImportResponse(
        total=len(tools_data),
        imported=imported,
        skipped=skipped,
        failed=failed,
        results=results
    ))
