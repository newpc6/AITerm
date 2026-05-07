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
    current_user=Depends(require_admin)
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
                    ["osascript", "-e",
                        'POSIX path of (choose folder with prompt "选择沙盒文件夹")'],
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
    current_user=Depends(get_current_user)
):
    is_admin = current_user and current_user.role == "admin"
    uid = None if is_admin else (int(current_user.id) if current_user else None)
    items, total = await service.list_models(page, page_size, user_id=uid)
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
    current_user=Depends(get_current_user)
):
    model = await service.get_model(model_id)
    if not model:
        return Response(code=1001, message="模型不存在")
    return Response(data=model.model_dump())


@router.post("/models")
async def create_model(
    request: ModelConfigCreate,
    service: ModelConfigService = Depends(get_model_config_service),
    current_user=Depends(get_current_user)
):
    try:
        model = await service.create_model(request, user_id=int(current_user.id) if current_user else None)
        return Response(data=model.model_dump())
    except Exception as e:
        return Response(code=1002, message=str(e))


@router.put("/models/{model_id}")
async def update_model(
    model_id: str,
    request: ModelConfigUpdate,
    service: ModelConfigService = Depends(get_model_config_service),
    current_user=Depends(require_admin)
):
    model = await service.update_model(model_id, request)
    if not model:
        return Response(code=1001, message="模型不存在")
    return Response(data=model.model_dump())


@router.delete("/models/{model_id}")
async def delete_model(
    model_id: str,
    service: ModelConfigService = Depends(get_model_config_service),
    current_user=Depends(require_admin)
):
    try:
        success = await service.delete_model(model_id)
        if not success:
            return Response(code=1001, message="模型不存在")
        return Response(data={})
    except ValueError as e:
        return Response(code=1003, message=str(e))


@router.post("/models/{model_id}/test")
async def test_model(
    model_id: str,
    service: ModelConfigService = Depends(get_model_config_service),
    current_user=Depends(require_admin)
):
    model = await service.get_model(model_id)
    if not model:
        return Response(code=1001, message="模型不存在")

    try:
        import httpx

        url = model.api_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"

        headers = {"Content-Type": "application/json"}
        if model.api_key:
            headers["Authorization"] = f"Bearer {model.api_key}"
        if model.extra_headers:
            headers.update({k: v for k, v in model.extra_headers.items()})

        payload = {
            "model": model.model,
            "messages": [
                {"role": "user", "content": "Hi"}
            ],
            "temperature": 0.1,
            "max_tokens": 10,
            "stream": False
        }
        if model.extra_body:
            payload.update(
                {k: v for k, v in model.extra_body.items() if k != "stream"})

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code >= 400:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    pass
                return Response(code=1005, message=error_data.get("error", {}).get("message", f"HTTP {response.status_code}"))

            data = response.json()
            reply = data.get("choices", [{}])[0].get(
                "message", {}).get("content", "")
            usage = data.get("usage", {})

            result = {
                "success": True,
                "reply": reply,
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                    "prompt_cache_hit_tokens": usage.get("prompt_cache_hit_tokens"),
                    "prompt_cache_miss_tokens": usage.get("prompt_cache_miss_tokens"),
                }
            }

            completion_details = usage.get("completion_tokens_details", {})
            if completion_details.get("reasoning_tokens"):
                result["usage"]["reasoning_tokens"] = completion_details["reasoning_tokens"]

            return Response(data=result)
    except Exception as e:
        return Response(code=1005, message=f"测试失败: {str(e)}")


@router.post("/models/{model_id}/default")
async def set_default_model(
    model_id: str,
    service: ModelConfigService = Depends(get_model_config_service),
    current_user=Depends(require_admin)
):
    success = await service.set_default_model(model_id)
    if not success:
        return Response(code=1001, message="模型不存在")
    return Response(data={})


@router.get("/global")
async def get_global_settings(
    service: GlobalSettingsService = Depends(get_global_settings_service),
    current_user=Depends(get_current_user)
):
    settings = await service.get_settings()
    return Response(data=settings.model_dump())


@router.put("/global")
async def update_global_settings(
    request: GlobalSettingsUpdate,
    service: GlobalSettingsService = Depends(get_global_settings_service),
    current_user=Depends(require_admin)
):
    current = await service.get_settings()
    update_data = {k: v for k, v in request.model_dump().items()
                   if v is not None}

    for key, value in update_data.items():
        setattr(current, key, value)

    settings = await service.save_settings(current)
    return Response(data=settings.model_dump())


@router.get("/auth")
async def get_auth_settings(
    repo: AuthSettingsRepository = Depends(get_auth_settings_repository),
    current_user=Depends(get_current_user)
):
    settings = await repo.get_settings()
    return Response(data=settings.model_dump())


@router.put("/auth")
async def update_auth_settings(
    request: AuthSettingsUpdate,
    repo: AuthSettingsRepository = Depends(get_auth_settings_repository),
    current_user=Depends(require_admin)
):
    current = await repo.get_settings()
    update_data = {k: v for k, v in request.model_dump().items()
                   if v is not None}

    for key, value in update_data.items():
        setattr(current, key, value)

    if current.session_ttl_hours <= 0:
        current.session_ttl_hours = 24

    settings = await repo.update_settings(current)
    return Response(data=settings.model_dump())
