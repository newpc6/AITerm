import logging
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.responses import StreamingResponse
from typing import Optional, List
from datetime import datetime
import json

from app.models import (
    Response, ConversationCreate, ConversationMessage,
    TaskConfirmRequest, TaskStatus
)
from app.models.common import PaginatedResponse
from app.services import ConversationService, TaskService, ChatOrchestrator
from app.api.deps import get_conversation_service, get_task_service, get_chat_orchestrator, get_current_user

router = APIRouter(prefix="/conversations", tags=["conversations"])
logger = logging.getLogger("aiterm.conversations")


@router.get("")
async def list_conversations(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    service: ConversationService = Depends(get_conversation_service)
):
    items, total = await service.list_conversations(page, page_size)
    paginated = PaginatedResponse.create(
        items=[item.model_dump() for item in items],
        total=total,
        page=page,
        page_size=page_size
    )
    return Response(data=paginated.model_dump())


@router.post("")
async def create_conversation(
    request: ConversationCreate,
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator)
):
    if not request.message or not request.message.strip():
        return Response(code=1001, message="message is required")

    result = await orchestrator.create_conversation(
        request.conversation_id,
        request.node_id,
        request.message,
        request.mode,
        request.model_id
    )
    return Response(data=result)


@router.post("/stream")
async def stream_conversation(
    request: ConversationCreate,
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator)
):
    logger.info(f"开始流式对话: {request.model_dump()}")
    if not request.message or not request.message.strip():
        return Response(code=1001, message="message is required")

    if request.mode != "chat":
        return Response(code=1011, message="streaming is only supported in chat mode")

    async def event_generator():
        async for event in orchestrator.stream_chat(
            request.conversation_id,
            request.node_id,
            request.message,
            request.model_id
        ):
            yield f"event: {event['event']}\n"
            yield f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.get("/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service),
    task_service: TaskService = Depends(get_task_service)
):
    messages = await conversation_service.get_messages(conversation_id)
    if messages is None:
        return Response(code=4041, message="conversation not found")

    latest_task = await task_service.task_repo.get_latest_task_by_conversation(conversation_id)
    latest_task_id = latest_task.id if latest_task else None

    return Response(
        data={
            "conversation_id": conversation_id,
            "items": [msg.model_dump() for msg in messages],
            "latest_task_id": latest_task_id
        }
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service)
):
    success = await service.delete_conversation(conversation_id)
    if not success:
        return Response(code=4041, message="conversation not found")
    return Response(data={"conversation_id": conversation_id, "status": "deleted"})
