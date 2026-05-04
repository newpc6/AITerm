import json
from typing import List, Optional
from sqlalchemy import select, delete, desc, func

from app.db import async_session_maker
from app.db.message import MessageModel
from app.models.chat import Message, MessageType
from app.utils import ensure_timezone


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
            messages = [self._to_domain(m) for m in models]
            messages.reverse()
            return messages

    async def get_message(self, message_id: str) -> Optional[Message]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(MessageModel).where(MessageModel.id == int(message_id))
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def create_message(self, chat_id: str, role: str, content: str, type: str = MessageType.TEXT.value) -> Optional[Message]:
        if not content or not content.strip():
            return None
        async with async_session_maker() as session:
            model = MessageModel(
                chat_id=int(chat_id),
                role=role,
                type=type,
                content=content
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

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
            if type is not None:
                model.type = type

            await session.commit()
            return self._to_domain(model)

    async def delete_message(self, message_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(MessageModel).where(MessageModel.id == int(message_id))
            )
            await session.commit()
            return result.rowcount > 0

    async def delete_messages_by_chat(self, chat_id: str) -> int:
        async with async_session_maker() as session:
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
            return [self._to_domain(m) for m in models]

    def _to_domain(self, model: MessageModel) -> Message:
        created_at = ensure_timezone(model.created_at)
        return Message(
            id=str(model.id),
            chat_id=str(model.chat_id),
            role=model.role,
            type=model.type,
            content=model.content,
            created_at=created_at.isoformat() if created_at else None
        )
