import json
import asyncio
import logging
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse

from app.models.common import Response, PaginatedResponse
from app.models.tool import (
    Tool, ToolCreate, ToolUpdate, ToolExecuteRequest, ToolExecuteResult,
    ToolParameters, ToolConfigSchema, ToolImportResult, ToolExport,
    ToolsImportResponse, BuiltinTool, UserTool, TemplateImportRequest,
)
from app.repositories.tool import ToolRepository
from app.api.deps import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tools", tags=["tools"])
tool_repo = ToolRepository()
BUILTIN_TOOLS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "tools"


async def _execute_tool_code(code: str, arguments: dict):
    local_vars = {"arguments": arguments, "result": None}
    wrapped_code = f"""
{code}

if 'execute' in dir():
    result = execute(arguments)
"""
    exec_globals = {"__builtins__": __builtins__,
                    "json": json, "asyncio": asyncio}
    exec(wrapped_code, exec_globals, local_vars)
    if asyncio.iscoroutine(local_vars.get("result")):
        return await local_vars["result"]
    return local_vars.get("result")


# ── Library (admin-only) ──

@router.get("/library", response_model=Response[List[Tool]])
async def list_library(type: str = None, user=Depends(require_admin)):
    tools = await tool_repo.list_library_tools(type_filter=type)
    return Response(data=tools)


@router.post("/library", response_model=Response[Tool])
async def create_library_tool(payload: ToolCreate, user=Depends(require_admin)):
    existing = await tool_repo.get_tool_by_name(payload.name)
    if existing:
        raise HTTPException(
            status_code=400, detail="Tool with this name already exists")
    tool = await tool_repo.create_tool(
        name=payload.name, display_name=payload.display_name,
        description=payload.description, code=payload.code,
        parameters=payload.parameters, config_schema=payload.config_schema,
        enabled=payload.enabled, sandbox_only=payload.sandbox_only,
        is_builtin=False, user_id=None, scope="public", is_template=payload.is_template,
    )
    return Response(data=tool)


@router.put("/library/{tool_id}", response_model=Response[Tool])
async def update_library_tool(tool_id: str, payload: ToolUpdate, user=Depends(require_admin)):
    tool = await tool_repo.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if payload.name and payload.name != tool.name:
        existing = await tool_repo.get_tool_by_name(payload.name)
        if existing:
            raise HTTPException(
                status_code=400, detail="Tool with this name already exists")
    update_data = {k: v for k, v in payload.model_dump().items()
                   if v is not None}
    updated = await tool_repo.update_tool(tool_id=tool_id, **update_data)
    return Response(data=updated)


@router.delete("/library/{tool_id}", response_model=Response[bool])
async def delete_library_tool(tool_id: str, user=Depends(require_admin)):
    tool = await tool_repo.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if tool.is_builtin:
        raise HTTPException(
            status_code=403, detail="Built-in tools cannot be deleted")
    deleted = await tool_repo.delete_tool(tool_id)
    return Response(data=deleted)


# ── My Tools (all users) ──

@router.get("/my", response_model=Response[List[UserTool]])
async def list_my_tools(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    tools = await tool_repo.list_user_tools(user_id=int(user.id))
    return Response(data=tools)


@router.post("/my", response_model=Response[Tool])
async def create_my_tool(payload: ToolCreate, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    existing = await tool_repo.get_tool_by_name(payload.name)
    if existing:
        raise HTTPException(
            status_code=400, detail="Tool with this name already exists")
    tool = await tool_repo.create_tool(
        name=payload.name, display_name=payload.display_name,
        description=payload.description, code=payload.code,
        parameters=payload.parameters, config_schema=payload.config_schema,
        enabled=True, sandbox_only=payload.sandbox_only,
        is_builtin=False, user_id=int(user.id), scope="private", is_template=False,
    )
    return Response(data=tool)


@router.put("/my/{tool_id}", response_model=Response[Tool])
async def update_my_tool(tool_id: str, payload: ToolUpdate, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    tool = await tool_repo.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if tool.is_builtin or (tool.user_id and str(tool.user_id) != user.id):
        raise HTTPException(status_code=403, detail="Cannot edit this tool")
    if payload.name and payload.name != tool.name:
        existing = await tool_repo.get_tool_by_name(payload.name)
        if existing:
            raise HTTPException(
                status_code=400, detail="Tool with this name already exists")
    update_data = {k: v for k, v in payload.model_dump().items()
                   if v is not None}
    updated = await tool_repo.update_tool(tool_id=tool_id, **update_data)
    return Response(data=updated)


@router.delete("/my/{tool_id}", response_model=Response[bool])
async def delete_my_tool(tool_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    tool = await tool_repo.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if tool.is_builtin or (tool.user_id and str(tool.user_id) != user.id):
        raise HTTPException(status_code=403, detail="Cannot delete this tool")
    deleted = await tool_repo.delete_tool(tool_id)
    return Response(data=deleted)


@router.post("/my/{tool_id}/toggle", response_model=Response[UserTool])
async def toggle_my_tool(tool_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    tool = await tool_repo.get_tool(tool_id)
    if tool and tool.is_builtin:
        pass
    current_state = True
    uts = await tool_repo.list_user_tools(user_id=int(user.id))
    for ut in uts:
        if ut.tool_id == tool_id:
            current_state = ut.enabled
            break
    result = await tool_repo.toggle_user_tool(
        user_id=int(user.id), tool_id=int(tool_id), enabled=not current_state
    )
    return Response(data=result)


# ── Templates ──

@router.get("/templates", response_model=Response[List[Tool]])
async def list_templates(user=Depends(get_current_user)):
    templates = await tool_repo.list_templates()
    return Response(data=templates)


@router.post("/templates/import", response_model=Response[dict])
async def import_templates(payload: TemplateImportRequest, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    tool_ids = [int(tid) for tid in payload.tool_ids]
    count = await tool_repo.import_templates(user_id=int(user.id), tool_ids=tool_ids)
    return Response(data={"imported": count})


# ── Legacy / Generic (kept for backward compat) ──

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
        name=payload.name, display_name=payload.display_name,
        description=payload.description, code=payload.code,
        parameters=payload.parameters, config_schema=payload.config_schema,
        enabled=payload.enabled, sandbox_only=payload.sandbox_only,
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
    update_data = {k: v for k, v in payload.model_dump().items()
                   if v is not None}
    updated = await tool_repo.update_tool(tool_id=tool_id, **update_data)
    return Response(data=updated)


@router.delete("/{tool_id}", response_model=Response[bool])
async def delete_tool(tool_id: str):
    tool = await tool_repo.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if tool.is_builtin:
        raise HTTPException(
            status_code=403, detail="Built-in tools cannot be deleted")
    deleted = await tool_repo.delete_tool(tool_id)
    return Response(data=deleted)


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


@router.post("/export", response_class=JSONResponse)
async def export_tools(tool_ids: List[str] = None):
    tools = await tool_repo.list_tools(enabled_only=False)
    if tool_ids:
        tools = [t for t in tools if t.id in tool_ids]
    export_data = [ToolExport(
        name=t.name, display_name=t.display_name, description=t.description,
        code=t.code, parameters=t.parameters, config_schema=t.config_schema,
        enabled=t.enabled, sandbox_only=t.sandbox_only,
    ).model_dump() for t in tools]
    return JSONResponse(
        content={"code": 0, "message": "ok", "data": export_data},
        headers={"Content-Disposition": "attachment; filename=tools_export.json"},
    )


@router.post("/import", response_model=Response[ToolsImportResponse])
async def import_tools(
    file: UploadFile = File(None),
    json_content: str = Form(None),
    overwrite: bool = Form(False),
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
                    raise HTTPException(
                        status_code=400, detail="Invalid JSON format")
            else:
                raise HTTPException(
                    status_code=400, detail="Invalid JSON format")
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
                    raise HTTPException(
                        status_code=400, detail="Invalid JSON format")
            else:
                raise HTTPException(
                    status_code=400, detail="Invalid JSON format")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON content")
    else:
        raise HTTPException(
            status_code=400, detail="Please provide a file or JSON content")

    results = []
    imported = skipped = failed = 0
    for tool_data in tools_data:
        name = tool_data.get('name', '')
        if not name:
            results.append(ToolImportResult(
                name='unknown', success=False, error="Missing tool name"))
            failed += 1
            continue
        try:
            existing = await tool_repo.get_tool_by_name(name)
            if existing:
                if overwrite:
                    await tool_repo.update_tool(
                        tool_id=existing.id, name=name,
                        display_name=tool_data.get('display_name'),
                        description=tool_data.get('description'),
                        code=tool_data.get('code', ''),
                        parameters=tool_data.get('parameters'),
                        config_schema=tool_data.get('config_schema'),
                        enabled=tool_data.get('enabled', True),
                        sandbox_only=tool_data.get('sandbox_only', False),
                    )
                    results.append(ToolImportResult(
                        name=name, success=True, action="updated"))
                    imported += 1
                else:
                    results.append(ToolImportResult(
                        name=name, success=False, error="Tool already exists", action="skipped"))
                    skipped += 1
            else:
                await tool_repo.create_tool(
                    name=name, display_name=tool_data.get('display_name'),
                    description=tool_data.get('description'), code=tool_data.get('code', ''),
                    parameters=tool_data.get('parameters'), config_schema=tool_data.get('config_schema'),
                    enabled=tool_data.get('enabled', True), sandbox_only=tool_data.get('sandbox_only', False),
                )
                results.append(ToolImportResult(
                    name=name, success=True, action="created"))
                imported += 1
        except Exception as e:
            results.append(ToolImportResult(
                name=name, success=False, error=str(e)))
            failed += 1

    return Response(data=ToolsImportResponse(total=len(tools_data), imported=imported, skipped=skipped, failed=failed, results=results))


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
                    filename=file_path.name,
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
            logger.warning(f"Failed to load {filename}: {e}")

    results = []
    imported = skipped = failed = 0
    for tool_data in tools_data:
        name = tool_data.get('name', '')
        if not name:
            failed += 1
            continue
        try:
            existing = await tool_repo.get_tool_by_name(name)
            if existing:
                if overwrite:
                    await tool_repo.update_tool(
                        tool_id=existing.id, name=name,
                        display_name=tool_data.get('display_name'),
                        description=tool_data.get('description'),
                        code=tool_data.get('code', ''),
                        parameters=tool_data.get('parameters'),
                        config_schema=tool_data.get('config_schema'),
                        enabled=tool_data.get('enabled', True),
                        sandbox_only=tool_data.get('sandbox_only', False),
                    )
                    results.append(ToolImportResult(
                        name=name, success=True, action="updated"))
                    imported += 1
                else:
                    skipped += 1
            else:
                await tool_repo.create_tool(
                    name=name, display_name=tool_data.get('display_name'),
                    description=tool_data.get('description'), code=tool_data.get('code', ''),
                    parameters=tool_data.get('parameters'), config_schema=tool_data.get('config_schema'),
                    enabled=tool_data.get('enabled', True), sandbox_only=tool_data.get('sandbox_only', False),
                )
                results.append(ToolImportResult(
                    name=name, success=True, action="created"))
                imported += 1
        except Exception as e:
            results.append(ToolImportResult(
                name=name, success=False, error=str(e)))
            failed += 1

    return Response(data=ToolsImportResponse(total=len(tools_data), imported=imported, skipped=skipped, failed=failed, results=results))
