import os
import logging
import shutil
from fastapi import APIRouter, Depends, HTTPException

from app.models.common import Response
from app.services.sandbox_manager import SandboxManager
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspace/files", tags=["workspace"])


def _get_sandbox():
    return SandboxManager()


def _resolve(user_id: int, rel_path: str) -> str:
    sm = _get_sandbox()
    base = sm.get_user_workspace(user_id)
    os.makedirs(base, exist_ok=True)
    clean = rel_path.lstrip('/').replace('\\', '/')
    if clean == '':
        return base
    full = os.path.normpath(os.path.join(base, clean))
    abs_full = os.path.abspath(full)
    abs_base = os.path.abspath(base)
    if not abs_full.startswith(abs_base):
        raise HTTPException(status_code=403, detail="Path outside workspace")
    return abs_full


def _tree(root: str, rel_root: str = "") -> list:
    items = []
    try:
        entries = sorted(os.listdir(root), key=lambda x: (not os.path.isdir(os.path.join(root, x)), x.lower()))
    except PermissionError:
        return items
    for name in entries:
        fp = os.path.join(root, name)
        is_dir = os.path.isdir(fp)
        try:
            st = os.stat(fp)
            size = st.st_size
            modified = str(int(st.st_mtime * 1000))
        except Exception:
            size = 0
            modified = ""
        item = {
            "name": name,
            "path": (rel_root + '/' + name).replace('//', '/'),
            "is_dir": is_dir,
            "size": size,
            "modified": modified,
        }
        if is_dir:
            item["children"] = _tree(fp, item["path"])
        items.append(item)
    return items


@router.get("")
async def list_dir(path: str = "", user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    full = _resolve(int(user.id), path)
    if not os.path.exists(full) or not os.path.isdir(full):
        return Response(data=[])
    items = _tree(full, path.rstrip('/') if path else "")
    return Response(data=items)


@router.get("/read")
async def read_file(path: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    full = _resolve(int(user.id), path)
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        size = os.path.getsize(full)
        if size > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (>5MB)")
        content = open(full, 'r', encoding='utf-8', errors='replace').read()
        return Response(data={"content": content, "path": path, "size": size})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/write")
async def write_file(payload: dict, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    full = _resolve(int(user.id), payload.get("path", ""))
    if os.path.isdir(full):
        raise HTTPException(status_code=400, detail="Cannot write to a directory")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(payload.get("content", ""))
    return Response(data={"status": "ok", "path": payload.get("path", "")})


@router.post("/mkdir")
async def mkdir(payload: dict, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    full = _resolve(int(user.id), payload.get("path", ""))
    os.makedirs(full, exist_ok=True)
    return Response(data={"status": "ok", "path": payload.get("path", "")})


@router.post("/delete")
async def delete_path(payload: dict, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    full = _resolve(int(user.id), payload.get("path", ""))
    if not os.path.exists(full):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        if os.path.isdir(full):
            shutil.rmtree(full)
        else:
            os.remove(full)
        return Response(data={"status": "ok"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rename")
async def rename(payload: dict, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    old_full = _resolve(int(user.id), payload.get("old_path", ""))
    new_full = _resolve(int(user.id), payload.get("new_path", ""))
    if not os.path.exists(old_full):
        raise HTTPException(status_code=404, detail="Not found")
    if os.path.exists(new_full):
        raise HTTPException(status_code=400, detail="Target already exists")
    os.makedirs(os.path.dirname(new_full), exist_ok=True)
    os.rename(old_full, new_full)
    return Response(data={"status": "ok", "path": payload.get("new_path", "")})


@router.post("/upload")
async def upload_file(path: str = "", content: str = "", user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    full = _resolve(int(user.id), path)
    os.makedirs(os.path.dirname(full) if os.path.dirname(full) else full, exist_ok=True)
    dirname = os.path.dirname(full) or full
    os.makedirs(dirname, exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(content)
    return Response(data={"status": "ok", "path": path})
