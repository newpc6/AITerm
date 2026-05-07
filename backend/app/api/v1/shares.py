import json
import logging
from fastapi import APIRouter, Depends, Query
from typing import Optional, List

from app.models import Response, ShareCreate, ShareVerify, ShareDetail, Share, ShareListItem
from app.models.common import PaginatedResponse
from app.repositories.share import ShareRepository
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.api.deps import get_current_user

router = APIRouter(prefix="/shares", tags=["shares"])
logger = logging.getLogger("aiterm")

share_repo = ShareRepository()
chat_repo = ChatRepository()
message_repo = MessageRepository()


def filter_message_content(msg: dict, show_input: bool, show_thinking: bool, show_tools: bool, show_answer: bool, show_full_input: bool) -> dict:
    if msg.get("role") == "user":
        return msg

    content = msg.get("content", "")
    try:
        parsed = json.loads(content) if isinstance(content, str) else content
    except:
        return msg if show_answer else None

    if not isinstance(parsed, dict):
        return msg if show_answer else None

    answer = parsed.get("answer", "")
    total_duration = parsed.get("total_duration", 0)
    iterations = parsed.get("iterations", [])

    filtered_iterations = []
    for iteration in iterations:
        if not isinstance(iteration, dict):
            continue

        filtered_iter = {}

        if show_thinking and iteration.get("thinking"):
            filtered_iter["thinking"] = iteration["thinking"]
            if iteration.get("thinking_duration"):
                filtered_iter["thinking_duration"] = iteration["thinking_duration"]
            if iteration.get("thinking_start_time"):
                filtered_iter["thinking_start_time"] = iteration["thinking_start_time"]

        if show_tools and iteration.get("tool_calls"):
            filtered_iter["tool_calls"] = iteration["tool_calls"]

        if show_input:
            if iteration.get("input"):
                filtered_iter["input"] = iteration["input"]
            if iteration.get("full_input"):
                filtered_iter["full_input"] = iteration["full_input"]

        if iteration.get("content"):
            filtered_iter["content"] = iteration["content"]

        if filtered_iter:
            filtered_iterations.append(filtered_iter)

    if not show_answer:
        answer = ""

    filtered_content = {
        "answer": answer,
        "total_duration": total_duration,
        "iterations": filtered_iterations
    }

    if show_full_input and parsed.get("full_input"):
        filtered_content["full_input"] = parsed["full_input"]

    result = dict(msg)
    result["content"] = json.dumps(filtered_content, ensure_ascii=False)
    return result


@router.post("")
async def create_share(request: ShareCreate, user=Depends(get_current_user)):
    chat = await chat_repo.get_chat(request.chat_id)
    if not chat:
        return Response(code=4040, message="chat not found")

    existing_share = await share_repo.get_share_by_chat(request.chat_id)
    if existing_share:
        return Response(data=existing_share.model_dump())

    title = request.title or chat.title or "未命名对话"

    share = await share_repo.create_share(
        chat_id=request.chat_id,
        title=title,
        password=request.password,
        expires_in=request.expires_in,
        show_input=request.show_input if request.show_input is not None else True,
        show_thinking=request.show_thinking if request.show_thinking is not None else True,
        show_tools=request.show_tools if request.show_tools is not None else True,
        show_answer=request.show_answer if request.show_answer is not None else True,
        show_full_input=request.show_full_input if request.show_full_input is not None else False,
        user_id=int(user.id) if user else None,
    )
    return Response(data=share.model_dump())


@router.get("/{share_id}")
async def get_share(share_id: str):
    share = await share_repo.get_share(share_id)
    if not share:
        return Response(code=4040, message="share not found")

    if await share_repo.is_expired(share_id):
        return Response(code=4100, message="share expired")

    return Response(data=share.model_dump())


@router.post("/{share_id}/verify")
async def verify_share(share_id: str, request: ShareVerify):
    share = await share_repo.get_share(share_id)
    if not share:
        return Response(code=4040, message="share not found")

    if await share_repo.is_expired(share_id):
        return Response(code=4100, message="share expired")

    if share.has_password:
        if not request.password:
            return Response(code=4010, message="password required")
        if not await share_repo.verify_share_password(share_id, request.password):
            return Response(code=4011, message="invalid password")

    await share_repo.increment_view_count(share_id)

    chat = await chat_repo.get_chat(share.chat_id)
    messages = await message_repo.get_all_messages(share.chat_id)

    show_input = share.show_input if share.show_input is not None else True
    show_thinking = share.show_thinking if share.show_thinking is not None else True
    show_tools = share.show_tools if share.show_tools is not None else True
    show_answer = share.show_answer if share.show_answer is not None else True
    show_full_input = share.show_full_input if share.show_full_input is not None else False

    message_list = []
    for msg in messages:
        msg_dict = {
            "id": msg.id,
            "role": msg.role,
            "type": msg.type,
            "content": msg.content,
            "created_at": msg.created_at
        }
        filtered = filter_message_content(
            msg_dict, show_input, show_thinking, show_tools, show_answer, show_full_input)
        if filtered:
            message_list.append(filtered)

    detail = ShareDetail(
        share_id=share.share_id,
        title=share.title,
        has_password=share.has_password,
        expires_at=share.expires_at,
        messages=message_list,
        chat_title=chat.title if chat else None,
        created_at=share.created_at,
        show_input=show_input,
        show_thinking=show_thinking,
        show_tools=show_tools,
        show_answer=show_answer,
        show_full_input=show_full_input
    )

    return Response(data=detail.model_dump())


@router.get("/{share_id}/preview")
async def preview_share(share_id: str):
    share = await share_repo.get_share(share_id)
    if not share:
        return Response(code=4040, message="share not found")

    if await share_repo.is_expired(share_id):
        return Response(code=4100, message="share expired")

    return Response(data={
        "share_id": share.share_id,
        "title": share.title,
        "has_password": share.has_password,
        "expires_at": share.expires_at,
        "created_at": share.created_at
    })


@router.delete("/{share_id}")
async def delete_share(share_id: str):
    success = await share_repo.delete_share(share_id)
    if not success:
        return Response(code=4040, message="share not found")
    return Response(data={"share_id": share_id, "status": "deleted"})


@router.post("/batch-delete")
async def batch_delete_shares(share_ids: List[str]):
    count = await share_repo.delete_shares_by_ids(share_ids)
    return Response(data={"deleted_count": count})


@router.get("/chat/{chat_id}")
async def get_share_by_chat(chat_id: str):
    share = await share_repo.get_share_by_chat(chat_id)
    if not share:
        return Response(code=4040, message="share not found")
    return Response(data=share.model_dump())


@router.delete("/chat/{chat_id}")
async def delete_share_by_chat(chat_id: str):
    success = await share_repo.delete_share_by_chat(chat_id)
    if not success:
        return Response(code=4040, message="share not found")
    return Response(data={"chat_id": chat_id, "status": "deleted"})


@router.get("")
async def list_shares(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), user=Depends(get_current_user)):
    uid = int(user.id) if user and user.role != "admin" else None
    items, total = await share_repo.list_shares(page, page_size, user_id=uid)
    return Response(data=PaginatedResponse.create(
        items=[item.model_dump() for item in items],
        total=total,
        page=page,
        page_size=page_size
    ).model_dump())
