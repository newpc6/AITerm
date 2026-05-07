import os
import logging
from fastapi import APIRouter, Depends, HTTPException

from app.models.common import Response
from app.services.sandbox_manager import SandboxManager
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspace/files", tags=["workspace"])
sandbox = SandboxManager()


@router.get("")
async def list_dir(path: str = "/", user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    full = os.path.join(sandbox.get_user_workspace(int(user.id)), path.lstrip('/'))
    if not os.path.exists(full):
        return Response(data=[])
    items = []
    for name in sorted(os.listdir(full)):
        fp = os.path.join(full, name)
        try:
            st = os.stat(fp)
            items.append({"name": name, "path": (path.rstrip('/') + '/' + name).replace('//', '/'), "is_dir": os.path.isdir(fp), "size": st.st_size, "modified": str(st.st_mtime)})
        except Exception:
            pass
    return Response(data=items)


@router.get("/read")
async def read_file(path: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    full = os.path.join(sandbox.get_user_workspace(int(user.id)), path.lstrip('/'))
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = open(full, 'r', encoding='utf-8', errors='replace').read()
        return Response(data={"content": content})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/write")
async def write_file(payload: dict, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    full = os.path.join(sandbox.get_user_workspace(int(user.id)), payload.get("path", "").lstrip('/'))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(payload.get("content", ""))
    return Response(data={"status": "ok"})


@router.post("/mkdir")
async def mkdir(payload: dict, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    full = os.path.join(sandbox.get_user_workspace(int(user.id)), payload.get("path", "").lstrip('/'))
    os.makedirs(full, exist_ok=True)
    return Response(data={"status": "ok"})


@router.post("/delete")
async def delete_path(payload: dict, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    full = os.path.join(sandbox.get_user_workspace(int(user.id)), payload.get("path", "").lstrip('/'))
    import shutil
    if os.path.isdir(full):
        shutil.rmtree(full)
    elif os.path.isfile(full):
        os.remove(full)
    return Response(data={"status": "ok"})
