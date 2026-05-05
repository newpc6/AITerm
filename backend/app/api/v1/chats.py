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
from app.services import ChatOrchestrator, ExecuteService
from app.api.deps import get_chat_orchestrator, get_execute_service, get_current_user

router = APIRouter(prefix="/chats", tags=["chats"])
logger = logging.getLogger("aiterm")

chat_repo = ChatRepository()
message_repo = MessageRepository()


@router.get("")
async def list_chats(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user=Depends(get_current_user)
):
    user_id = None
    include_user_info = False

    if current_user:
        if current_user.role != "admin":
            user_id = int(current_user.id)
        else:
            include_user_info = True

    items, total = await chat_repo.list_chats(page, page_size, user_id=user_id, include_user_info=include_user_info)
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
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator),
    current_user=Depends(get_current_user)
):
    if not request.message or not request.message.strip():
        return Response(code=1001, message="message is required")

    user_id = int(current_user.id) if current_user else None
    result = await orchestrator.create_chat(
        request.node_id,
        request.message,
        request.model_id,
        user_id=user_id
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
        try:
            async for event in orchestrator.stream_chat(
                request.chat_id,
                request.node_id,
                request.message,
                request.model_id
            ):
                yield f"event: {event['event']}\n"
                yield f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Stream chat error: {e}", exc_info=True)
            yield f"event: conversation.error\n"
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

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
    update_data = {k: v for k, v in request.model_dump().items()
                   if v is not None}
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


@router.post("/{chat_id}/confirm")
async def confirm_execution(
    chat_id: str,
    request: dict,
    service: ExecuteService = Depends(get_execute_service)
):
    approved = request.get("approved", False)
    logger.info(f"[confirm] 请求: chat_id={chat_id}, approved={approved}")
    updated_chat = await service.confirm_execution(chat_id, approved)
    if not updated_chat:
        logger.warning(
            f"[confirm] 失败: chat_id={chat_id}, 原因: chat not found or does not require confirmation")
        return Response(code=4040, message="chat not found or does not require confirmation")
    logger.info(
        f"[confirm] 成功: chat_id={chat_id}, status={updated_chat.status}")
    return Response(data=updated_chat.model_dump())


@router.post("/{chat_id}/input")
async def provide_input(
    chat_id: str,
    request: dict,
    service: ExecuteService = Depends(get_execute_service)
):
    user_input = request.get("user_input", "")
    logger.info(
        f"[input] 请求: chat_id={chat_id}, user_input={user_input[:200] if user_input else 'None'}")
    updated_chat = await service.provide_input(chat_id, user_input)
    if not updated_chat:
        logger.warning(
            f"[input] 失败: chat_id={chat_id}, 原因: chat not found or does not require input")
        return Response(code=4040, message="chat not found or does not require input")
    logger.info(f"[input] 成功: chat_id={chat_id}, status={updated_chat.status}")
    return Response(data=updated_chat.model_dump())


@router.post("/{chat_id}/stop")
async def stop_execution(
    chat_id: str,
    service: ExecuteService = Depends(get_execute_service)
):
    logger.info(f"[stop] 请求: chat_id={chat_id}")
    updated_chat = await service.stop_execution(chat_id)
    if not updated_chat:
        logger.warning(
            f"[stop] 失败: chat_id={chat_id}, 原因: chat not found or cannot be stopped")
        return Response(code=4040, message="chat not found or cannot be stopped")
    logger.info(f"[stop] 成功: chat_id={chat_id}, status={updated_chat.status}")
    return Response(data=updated_chat.model_dump())


@router.get("/{chat_id}/continue")
async def continue_execution(
    chat_id: str,
    service: ExecuteService = Depends(get_execute_service)
):
    logger.info(f"[continue] 请求: chat_id={chat_id}")

    async def event_generator():
        try:
            event_count = 0
            async for event in service.continue_with_input(chat_id):
                event_count += 1
                logger.info(
                    f"[continue] 输出事件 #{event_count}: {event.get('event')}, data={json.dumps(event.get('data', {}), ensure_ascii=False)[:200]}")
                yield f"event: {event['event']}\n"
                yield f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
            logger.info(
                f"[continue] 完成: chat_id={chat_id}, 共 {event_count} 个事件")
        except Exception as e:
            logger.error(
                f"[continue] 错误: chat_id={chat_id}, error={e}", exc_info=True)
            yield f"event: conversation.error\n"
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
