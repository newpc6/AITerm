import logging
from fastapi import APIRouter, Depends, HTTPException

from app.models.common import Response
from app.models.sandbox_config import (
    SandboxConfigUpdate, SandboxFullConfig,
    SandboxPathCreate, SandboxDangerousPatternCreate, SandboxDangerousPatternUpdate,
    SandboxCommandCreate, SandboxCommandUpdate,
)
from app.repositories.sandbox_config import SandboxConfigRepository
from app.api.deps import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sandbox", tags=["sandbox"])

repo = SandboxConfigRepository()


@router.get("/config")
async def get_full_config(current_user=Depends(require_admin)):
    config = await repo.get_config()
    if not config:
        config = await repo.update_config()
    paths = await repo.list_paths()
    patterns = await repo.list_dangerous_patterns()
    blacklist = await repo.list_blacklist()
    whitelist = await repo.list_whitelist()
    return Response(data=SandboxFullConfig(
        config=config,
        paths=paths,
        dangerous_patterns=patterns,
        command_blacklist=blacklist,
        command_whitelist=whitelist,
    ).model_dump())


@router.put("/config")
async def update_config(payload: SandboxConfigUpdate, current_user=Depends(require_admin)):
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_data:
        return Response(code=1002, message="no data to update")
    update_data["updated_by"] = current_user.username if current_user else "system"
    config = await repo.update_config(**update_data)
    return Response(data=config.model_dump())


@router.post("/paths")
async def add_path(payload: SandboxPathCreate, current_user=Depends(require_admin)):
    item = await repo.add_path(payload.path)
    return Response(data=item.model_dump())


@router.delete("/paths/{path_id}")
async def delete_path(path_id: int, current_user=Depends(require_admin)):
    if not await repo.delete_path(path_id):
        raise HTTPException(status_code=404, detail="Path not found")
    return Response(data={"status": "deleted"})


@router.get("/dangerous-patterns")
async def list_dangerous_patterns(current_user=Depends(require_admin)):
    items = await repo.list_dangerous_patterns()
    return Response(data=[p.model_dump() for p in items])


@router.post("/dangerous-patterns")
async def add_dangerous_pattern(payload: SandboxDangerousPatternCreate, current_user=Depends(require_admin)):
    item = await repo.add_dangerous_pattern(payload.pattern, payload.description, payload.scope)
    return Response(data=item.model_dump())


@router.put("/dangerous-patterns/{pattern_id}")
async def update_dangerous_pattern(pattern_id: int, payload: SandboxDangerousPatternUpdate, current_user=Depends(require_admin)):
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    item = await repo.update_dangerous_pattern(pattern_id, **update_data)
    if not item:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return Response(data=item.model_dump())


@router.delete("/dangerous-patterns/{pattern_id}")
async def delete_dangerous_pattern(pattern_id: int, current_user=Depends(require_admin)):
    if not await repo.delete_dangerous_pattern(pattern_id):
        raise HTTPException(status_code=404, detail="Pattern not found")
    return Response(data={"status": "deleted"})


@router.get("/blacklist")
async def list_blacklist(current_user=Depends(require_admin)):
    items = await repo.list_blacklist()
    return Response(data=[p.model_dump() for p in items])


@router.post("/blacklist")
async def add_blacklist(payload: SandboxCommandCreate, current_user=Depends(require_admin)):
    item = await repo.add_blacklist(payload.command, payload.scope)
    return Response(data=item.model_dump())


@router.put("/blacklist/{item_id}")
async def update_blacklist(item_id: int, payload: SandboxCommandUpdate, current_user=Depends(require_admin)):
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    item = await repo.update_blacklist(item_id, **update_data)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return Response(data=item.model_dump())


@router.delete("/blacklist/{item_id}")
async def delete_blacklist(item_id: int, current_user=Depends(require_admin)):
    if not await repo.delete_blacklist(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    return Response(data={"status": "deleted"})


@router.get("/whitelist")
async def list_whitelist(current_user=Depends(require_admin)):
    items = await repo.list_whitelist()
    return Response(data=[p.model_dump() for p in items])


@router.post("/whitelist")
async def add_whitelist(payload: SandboxCommandCreate, current_user=Depends(require_admin)):
    item = await repo.add_whitelist(payload.command, payload.scope)
    return Response(data=item.model_dump())


@router.put("/whitelist/{item_id}")
async def update_whitelist(item_id: int, payload: SandboxCommandUpdate, current_user=Depends(require_admin)):
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    item = await repo.update_whitelist(item_id, **update_data)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return Response(data=item.model_dump())


@router.delete("/whitelist/{item_id}")
async def delete_whitelist(item_id: int, current_user=Depends(require_admin)):
    if not await repo.delete_whitelist(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    return Response(data={"status": "deleted"})
