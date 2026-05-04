from fastapi import APIRouter, Depends, Query
from typing import Optional, List
import asyncio
import sys
import os

from app.models import (
    Response, AuthSettings, AuthSettingsUpdate,
    ModelConfig, ModelConfigCreate, ModelConfigUpdate,
    GlobalSettings, GlobalSettingsUpdate
)
from app.models.common import PaginatedResponse
from app.services import ModelConfigService, GlobalSettingsService
from app.api.deps import (
    get_model_config_service, get_global_settings_service,
    get_auth_settings_repository, get_current_user, require_admin
)
from app.repositories import AuthSettingsRepository

router = APIRouter(tags=["settings"])


@router.post("/select-folder")
async def select_folder(
    current_user = Depends(require_admin)
):
    try:
        def open_folder_dialog():
            if sys.platform == "win32":
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                folder = filedialog.askdirectory(title="选择沙盒文件夹")
                root.destroy()
                return folder
            elif sys.platform == "darwin":
                import subprocess
                result = subprocess.run(
                    ["osascript", "-e", 'POSIX path of (choose folder with prompt "选择沙盒文件夹")'],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    return result.stdout.strip()
                return None
            else:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                folder = filedialog.askdirectory(title="选择沙盒文件夹")
                root.destroy()
                return folder
        
        loop = asyncio.get_event_loop()
        folder = await loop.run_in_executor(None, open_folder_dialog)
        
        if folder:
            return Response(data={"path": folder})
        else:
            return Response(data={"path": None})
    except Exception as e:
        return Response(code=1004, message=f"打开文件夹选择对话框失败: {str(e)}")


@router.get("/models")
async def list_models(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    service: ModelConfigService = Depends(get_model_config_service),
    current_user = Depends(get_current_user)
):
    items, total = await service.list_models(page, page_size)
    paginated = PaginatedResponse.create(
        items=[m.model_dump() for m in items],
        total=total,
        page=page,
        page_size=page_size
    )
    return Response(data=paginated.model_dump())


@router.get("/models/{model_id}")
async def get_model(
    model_id: str,
    service: ModelConfigService = Depends(get_model_config_service),
    current_user = Depends(get_current_user)
):
    model = await service.get_model(model_id)
    if not model:
        return Response(code=1001, message="模型不存在")
    return Response(data=model.model_dump())


@router.post("/models")
async def create_model(
    request: ModelConfigCreate,
    service: ModelConfigService = Depends(get_model_config_service),
    current_user = Depends(require_admin)
):
    try:
        model = await service.create_model(request)
        return Response(data=model.model_dump())
    except Exception as e:
        return Response(code=1002, message=str(e))


@router.put("/models/{model_id}")
async def update_model(
    model_id: str,
    request: ModelConfigUpdate,
    service: ModelConfigService = Depends(get_model_config_service),
    current_user = Depends(require_admin)
):
    model = await service.update_model(model_id, request)
    if not model:
        return Response(code=1001, message="模型不存在")
    return Response(data=model.model_dump())


@router.delete("/models/{model_id}")
async def delete_model(
    model_id: str,
    service: ModelConfigService = Depends(get_model_config_service),
    current_user = Depends(require_admin)
):
    try:
        success = await service.delete_model(model_id)
        if not success:
            return Response(code=1001, message="模型不存在")
        return Response(data={})
    except ValueError as e:
        return Response(code=1003, message=str(e))


@router.post("/models/{model_id}/default")
async def set_default_model(
    model_id: str,
    service: ModelConfigService = Depends(get_model_config_service),
    current_user = Depends(require_admin)
):
    success = await service.set_default_model(model_id)
    if not success:
        return Response(code=1001, message="模型不存在")
    return Response(data={})


@router.get("/global")
async def get_global_settings(
    service: GlobalSettingsService = Depends(get_global_settings_service),
    current_user = Depends(get_current_user)
):
    settings = await service.get_settings()
    return Response(data=settings.model_dump())


@router.put("/global")
async def update_global_settings(
    request: GlobalSettingsUpdate,
    service: GlobalSettingsService = Depends(get_global_settings_service),
    current_user = Depends(require_admin)
):
    current = await service.get_settings()
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}

    for key, value in update_data.items():
        setattr(current, key, value)

    settings = await service.save_settings(current)
    return Response(data=settings.model_dump())


@router.get("/auth")
async def get_auth_settings(
    repo: AuthSettingsRepository = Depends(get_auth_settings_repository),
    current_user = Depends(get_current_user)
):
    settings = await repo.get_settings()
    return Response(data=settings.model_dump())


@router.put("/auth")
async def update_auth_settings(
    request: AuthSettingsUpdate,
    repo: AuthSettingsRepository = Depends(get_auth_settings_repository),
    current_user = Depends(require_admin)
):
    current = await repo.get_settings()
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}

    for key, value in update_data.items():
        setattr(current, key, value)

    if current.session_ttl_hours <= 0:
        current.session_ttl_hours = 24

    settings = await repo.update_settings(current)
    return Response(data=settings.model_dump())
