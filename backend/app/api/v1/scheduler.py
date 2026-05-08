import logging
from fastapi import APIRouter, Depends, HTTPException

from app.models.common import Response
from app.models.scheduler import ScheduledTaskCreate, ScheduledTaskUpdate
from app.repositories.scheduler import SchedulerRepository
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scheduler", tags=["scheduler"])
repo = SchedulerRepository()


@router.get("")
async def list_tasks(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    is_admin = user.role == "admin"
    tasks = await repo.list_tasks(user_id=int(user.id), is_admin=is_admin)
    return Response(data=[t.model_dump() for t in tasks])


@router.post("")
async def create_task(payload: ScheduledTaskCreate, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    task = await repo.create(user_id=int(user.id), **payload.model_dump())
    return Response(data=task.model_dump())


@router.get("/{task_id}")
async def get_task(task_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    task = await repo.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return Response(data=task.model_dump())


@router.put("/{task_id}")
async def update_task(task_id: str, payload: ScheduledTaskUpdate, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    existing = await repo.get(task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    update_data = {k: v for k, v in payload.model_dump().items()
                   if v is not None}
    task = await repo.update(task_id, **update_data)
    return Response(data=task.model_dump() if task else None)


@router.delete("/{task_id}")
async def delete_task(task_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    await repo.delete(task_id)
    return Response(data={"status": "deleted"})


@router.post("/{task_id}/run")
async def run_task_now(task_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    task = await repo.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    from app.services.scheduler_engine import run_single_task
    import asyncio
    asyncio.create_task(run_single_task(int(task_id)))
    return Response(data={"status": "started"})


@router.get("/{task_id}/logs")
async def task_logs(task_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    logs = await repo.list_logs(task_id)
    return Response(data=[l.model_dump() for l in logs])


@router.post("/{task_id}/toggle")
async def toggle_task(task_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    task = await repo.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    new_enabled = not task.enabled
    await repo.update(task_id, enabled=new_enabled)
    return Response(data={"enabled": new_enabled})
