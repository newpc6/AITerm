from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import json

from app.models import Response, TaskConfirmRequest, TaskInputRequest
from app.models.common import PaginatedResponse
from app.services import TaskService
from app.api.deps import get_task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    service: TaskService = Depends(get_task_service)
):
    items, total = await service.list_tasks(page, page_size)
    paginated = PaginatedResponse.create(
        items=[task.model_dump() for task in items],
        total=total,
        page=page,
        page_size=page_size
    )
    return Response(data=paginated.model_dump())


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    service: TaskService = Depends(get_task_service)
):
    task = await service.get_task(task_id)
    if not task:
        return Response(code=4040, message="task not found")
    return Response(data=task.model_dump())


@router.get("/{task_id}/events")
async def stream_task_events(
    task_id: str,
    service: TaskService = Depends(get_task_service)
):
    task = await service.get_task(task_id)
    if not task:
        return Response(code=4040, message="task not found")

    async def event_generator():
        async for event in service.execute_task(task_id, task.conversation_id):
            yield f"event: {event['event']}\n"
            yield f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.post("/{task_id}/confirm")
async def confirm_task(
    task_id: str,
    request: TaskConfirmRequest,
    service: TaskService = Depends(get_task_service)
):
    task = await service.confirm_task(task_id, request.approved)
    if not task:
        return Response(code=4040, message="task not found or does not require confirmation")
    return Response(data=task.model_dump())


@router.post("/{task_id}/input")
async def provide_task_input(
    task_id: str,
    request: TaskInputRequest,
    service: TaskService = Depends(get_task_service)
):
    task = await service.provide_input(task_id, request.user_input)
    if not task:
        return Response(code=4040, message="task not found or does not require input")
    return Response(data=task.model_dump())


@router.get("/{task_id}/continue")
async def continue_task_with_input(
    task_id: str,
    service: TaskService = Depends(get_task_service)
):
    task = await service.get_task(task_id)
    if not task:
        return Response(code=4040, message="task not found")

    async def event_generator():
        async for event in service.continue_with_input(task_id, task.conversation_id):
            yield f"event: {event['event']}\n"
            yield f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.post("/{task_id}/stop")
async def stop_task(
    task_id: str,
    service: TaskService = Depends(get_task_service)
):
    task = await service.stop_task(task_id)
    if not task:
        return Response(code=4040, message="task not found or cannot be stopped")
    return Response(data=task.model_dump())


@router.post("/{task_id}/restart")
async def restart_task(
    task_id: str,
    service: TaskService = Depends(get_task_service)
):
    task = await service.restart_task(task_id)
    if not task:
        return Response(code=4040, message="task not found or cannot be restarted")
    return Response(data=task.model_dump())


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    service: TaskService = Depends(get_task_service)
):
    success = await service.delete_task(task_id)
    if not success:
        return Response(code=4040, message="task not found")
    return Response(data={"task_id": task_id, "status": "deleted"})
