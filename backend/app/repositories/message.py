import json
from typing import List, Optional
from sqlalchemy import select, delete, desc, func

from app.db import async_session_maker
from app.db.message import MessageModel, MessagePartModel
from app.models.chat import Message, MessageType
from app.utils import ensure_timezone

MAX_CONTENT_LENGTH = 1000000
MAX_FULL_INPUT_LENGTH = 1000000


def truncate_content(content: str, max_length: int = MAX_CONTENT_LENGTH) -> str:
    if len(content) <= max_length:
        return content
    return content[:max_length - 100] + "\n... [内容已截断]"


def truncate_full_input(content: str) -> str:
    if not content:
        return content
    if len(content) <= MAX_FULL_INPUT_LENGTH:
        return content
    return content[:MAX_FULL_INPUT_LENGTH - 100] + "\n... [完整内容过长,已截断]"


class MessageRepository:
    async def list_messages(self, chat_id: str, page: int = 1, page_size: int = 20) -> List[Message]:
        async with async_session_maker() as session:
            offset = (page - 1) * page_size
            result = await session.execute(
                select(MessageModel)
                .where(MessageModel.chat_id == int(chat_id))
                .order_by(desc(MessageModel.created_at))
                .offset(offset)
                .limit(page_size)
            )
            models = result.scalars().all()
            messages = []
            for m in models:
                parts = await self._get_message_parts(session, m.id)
                messages.append(self._to_domain(m, parts))
            messages.reverse()
            return messages

    async def get_message(self, message_id: str) -> Optional[Message]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(MessageModel).where(MessageModel.id == int(message_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            parts = await self._get_message_parts(session, model.id)
            return self._to_domain(model, parts)

    async def create_message(self, chat_id: str, role: str, content: str, type: str = MessageType.TEXT.value) -> Optional[Message]:
        if not content or not content.strip():
            return None
        async with async_session_maker() as session:
            model = MessageModel(
                chat_id=int(chat_id),
                role=role,
                content=content
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)

            return self._to_domain(model, [])

    async def create_message_with_data(self, chat_id: str, role: str,
                                       answer: str = "",
                                       total_duration: float = 0,
                                       iterations: List[dict] = None) -> Optional[Message]:
        async with async_session_maker() as session:
            msg_content = {
                "answer": answer,
                "total_duration": total_duration
            }

            full_input_val = None
            if iterations:
                for iteration in iterations:
                    if iteration.get("full_input"):
                        full_input_val = iteration["full_input"]
                    if iteration.get("usage"):
                        msg_content["usage"] = iteration["usage"]

            model = MessageModel(
                chat_id=int(chat_id),
                role=role,
                content=json.dumps(msg_content, ensure_ascii=False),
                full_input=truncate_full_input(
                    full_input_val) if full_input_val else None
            )
            session.add(model)
            await session.flush()

            if iterations:
                for seq, iteration in enumerate(iterations):
                    iteration_copy = {
                        k: v for k, v in iteration.items() if k != "full_input"}
                    content_str = json.dumps(
                        iteration_copy, ensure_ascii=False)
                    part = MessagePartModel(
                        message_id=model.id,
                        seq=seq,
                        content=truncate_content(content_str)
                    )
                    session.add(part)

            await session.commit()
            await session.refresh(model)

            parts = await self._get_message_parts(session, model.id)
            return self._to_domain(model, parts)

    async def update_message_content(self, message_id: str,
                                     answer: str = None,
                                     total_duration: float = None,
                                     iterations: List[dict] = None) -> Optional[Message]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(MessageModel).where(MessageModel.id == int(message_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None

            try:
                msg_content = json.loads(model.content or "{}")
            except:
                msg_content = {
                    "answer": model.content or "", "total_duration": 0}

            if answer is not None:
                msg_content["answer"] = answer
            if total_duration is not None:
                msg_content["total_duration"] = total_duration

            model.content = json.dumps(msg_content, ensure_ascii=False)

            if iterations is not None:
                full_input_val = None
                for iteration in iterations:
                    if iteration.get("full_input"):
                        full_input_val = iteration["full_input"]
                    if iteration.get("usage"):
                        msg_content["usage"] = iteration["usage"]
                model.full_input = truncate_full_input(
                    full_input_val) if full_input_val else None

                await session.execute(
                    delete(MessagePartModel).where(
                        MessagePartModel.message_id == int(message_id))
                )
                for seq, iteration in enumerate(iterations):
                    iteration_copy = {
                        k: v for k, v in iteration.items() if k != "full_input"}
                    content_str = json.dumps(
                        iteration_copy, ensure_ascii=False)
                    part = MessagePartModel(
                        message_id=int(message_id),
                        seq=seq,
                        content=truncate_content(content_str)
                    )
                    session.add(part)

            await session.commit()

            parts = await self._get_message_parts(session, model.id)
            return self._to_domain(model, parts)

    async def add_iteration(self, message_id: str, iteration: dict) -> Optional[dict]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(func.max(MessagePartModel.seq))
                .where(MessagePartModel.message_id == int(message_id))
            )
            max_seq = result.scalar()
            new_seq = (max_seq or -1) + 1

            iteration_copy = {k: v for k,
                              v in iteration.items() if k != "full_input"}
            content_str = json.dumps(iteration_copy, ensure_ascii=False)
            part = MessagePartModel(
                message_id=int(message_id),
                seq=new_seq,
                content=truncate_content(content_str)
            )
            session.add(part)

            if iteration.get("full_input"):
                result = await session.execute(
                    select(MessageModel).where(
                        MessageModel.id == int(message_id))
                )
                model = result.scalar_one_or_none()
                if model:
                    model.full_input = truncate_full_input(
                        iteration["full_input"])

            if iteration.get("usage"):
                result = await session.execute(
                    select(MessageModel).where(
                        MessageModel.id == int(message_id))
                )
                model = result.scalar_one_or_none()
                if model:
                    try:
                        content_obj = json.loads(model.content or "{}")
                    except:
                        content_obj = {}
                    content_obj["usage"] = iteration["usage"]
                    model.content = json.dumps(content_obj, ensure_ascii=False)

            await session.commit()

            return {"seq": new_seq, "content": iteration}

    async def update_message(self, message_id: str, content: str = None, type: str = None) -> Optional[Message]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(MessageModel).where(MessageModel.id == int(message_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None

            if content is not None:
                model.content = content

                await session.execute(
                    delete(MessagePartModel).where(
                        MessagePartModel.message_id == int(message_id))
                )

            await session.commit()

            parts = await self._get_message_parts(session, model.id)
            return self._to_domain(model, parts)

    async def delete_message(self, message_id: str) -> bool:
        async with async_session_maker() as session:
            await session.execute(
                delete(MessagePartModel).where(
                    MessagePartModel.message_id == int(message_id))
            )
            result = await session.execute(
                delete(MessageModel).where(MessageModel.id == int(message_id))
            )
            await session.commit()
            return result.rowcount > 0

    async def delete_messages_by_chat(self, chat_id: str) -> int:
        async with async_session_maker() as session:
            msg_result = await session.execute(
                select(MessageModel.id).where(
                    MessageModel.chat_id == int(chat_id))
            )
            message_ids = [row[0] for row in msg_result.fetchall()]

            if message_ids:
                await session.execute(
                    delete(MessagePartModel).where(
                        MessagePartModel.message_id.in_(message_ids))
                )

            result = await session.execute(
                delete(MessageModel).where(
                    MessageModel.chat_id == int(chat_id))
            )
            await session.commit()
            return result.rowcount

    async def count_messages(self, chat_id: str) -> int:
        async with async_session_maker() as session:
            result = await session.execute(
                select(func.count(MessageModel.id))
                .where(MessageModel.chat_id == int(chat_id))
            )
            return result.scalar() or 0

    async def get_all_messages(self, chat_id: str) -> List[Message]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(MessageModel)
                .where(MessageModel.chat_id == int(chat_id))
                .order_by(MessageModel.created_at)
            )
            models = result.scalars().all()
            messages = []
            for m in models:
                parts = await self._get_message_parts(session, m.id)
                messages.append(self._to_domain(m, parts))
            return messages

    async def get_message_parts(self, message_id: str) -> List[dict]:
        async with async_session_maker() as session:
            parts = await self._get_message_parts(session, int(message_id))
            return [json.loads(p.content) for p in parts]

    async def _get_message_parts(self, session, message_id: int) -> List[MessagePartModel]:
        result = await session.execute(
            select(MessagePartModel)
            .where(MessagePartModel.message_id == message_id)
            .order_by(MessagePartModel.seq)
        )
        return list(result.scalars().all())

    def _to_domain(self, model: MessageModel, parts: List[MessagePartModel]) -> Message:
        created_at = ensure_timezone(model.created_at)

        if model.role == "user":
            return Message(
                id=str(model.id),
                chat_id=str(model.chat_id),
                role=model.role,
                type="text",
                content=model.content or "",
                full_input=model.full_input,
                created_at=created_at.isoformat() if created_at else None
            )

        try:
            msg_content = json.loads(model.content or "{}")
        except:
            msg_content = {"answer": model.content or "", "total_duration": 0}

        answer = msg_content.get("answer", "")
        total_duration = msg_content.get("total_duration", 0)
        usage = msg_content.get("usage")

        iterations = []
        for p in parts:
            try:
                iteration = json.loads(p.content)
                iterations.append(iteration)
            except:
                pass

        full_content = {
            "answer": answer,
            "total_duration": total_duration,
            "iterations": iterations,
            "full_input": model.full_input
        }
        if usage:
            full_content["usage"] = usage

        return Message(
            id=str(model.id),
            chat_id=str(model.chat_id),
            role=model.role,
            type="text",
            content=json.dumps(full_content, ensure_ascii=False),
            full_input=model.full_input,
            created_at=created_at.isoformat() if created_at else None
        )
