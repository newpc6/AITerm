import logging
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import json

from app.models import Response
from app.models.chat import ChatCreate, ChatUpdate, MessageCreate
from app.models.common import PaginatedResponse
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.services import ChatOrchestrator
from app.api.deps import get_chat_orchestrator

router = APIRouter(prefix="/chats", tags=["chats"])
logger = logging.getLogger("aiterm.chats")

chat_repo = ChatRepository()
message_repo = MessageRepository()


@router.get("")
async def list_chats(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    items, total = await chat_repo.list_chats(page, page_size)
    paginated = PaginatedResponse.create(
        items=[item.model_dump() for item in items],
        total=total,
        page=page,
        page_size=page_size
    )
    return Response(data=paginated.model_dump())


@router.post("")
async def create_chat(
    request: ChatCreate,
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator)
):
    if not request.message or not request.message.strip():
        return Response(code=1001, message="message is required")

    result = await orchestrator.create_chat(
        request.node_id,
        request.message,
        request.model_id
    )
    return Response(data=result)


@router.post("/stream")
async def stream_chat(
    request: ChatCreate,
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator)
):
    logger.info(f"开始流式对话: {request.model_dump()}")
    if not request.message or not request.message.strip():
        return Response(code=1001, message="message is required")

    async def event_generator():
        async for event in orchestrator.stream_chat(
            None,
            request.node_id,
            request.message,
            request.model_id
        ):
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


@router.get("/{chat_id}")
async def get_chat(chat_id: str):
    chat = await chat_repo.get_chat(chat_id)
    if not chat:
        return Response(code=4040, message="chat not found")
    return Response(data=chat.model_dump())


@router.patch("/{chat_id}")
async def update_chat(
    chat_id: str,
    request: ChatUpdate
):
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    if not update_data:
        return Response(code=1002, message="no data to update")
    
    chat = await chat_repo.update_chat(chat_id, **update_data)
    if not chat:
        return Response(code=4040, message="chat not found")
    return Response(data=chat.model_dump())


@router.delete("/{chat_id}")
async def delete_chat(chat_id: str):
    await message_repo.delete_messages_by_chat(chat_id)
    success = await chat_repo.delete_chat(chat_id)
    if not success:
        return Response(code=4040, message="chat not found")
    return Response(data={"chat_id": chat_id, "status": "deleted"})


@router.get("/{chat_id}/messages")
async def get_chat_messages(
    chat_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    chat = await chat_repo.get_chat(chat_id)
    if not chat:
        return Response(code=4040, message="chat not found")
    
    messages = await message_repo.list_messages(chat_id, page, page_size)
    total = await message_repo.count_messages(chat_id)
    
    return Response(
        data={
            "chat_id": chat_id,
            "items": [msg.model_dump() for msg in messages],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )


@router.post("/{chat_id}/messages")
async def create_message(
    chat_id: str,
    request: MessageCreate
):
    chat = await chat_repo.get_chat(chat_id)
    if not chat:
        return Response(code=4040, message="chat not found")
    
    message = await message_repo.create_message(
        chat_id=chat_id,
        role=request.role,
        content=request.content,
        type=request.type,
        metadata=request.metadata
    )
    return Response(data=message.model_dump())


@router.get("/{chat_id}/stream")
async def continue_stream_chat(
    chat_id: str,
    message: str = Query(..., description="用户消息"),
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator)
):
    chat = await chat_repo.get_chat(chat_id)
    if not chat:
        return Response(code=4040, message="chat not found")

    async def event_generator():
        async for event in orchestrator.continue_chat(
            chat_id,
            message
        ):
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
