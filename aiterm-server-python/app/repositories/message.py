import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, delete, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.db.message import MessageModel
from app.models.chat import Message, MessageType


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

    async def create_message(self, chat_id: str, role: str, content: str, type: str = MessageType.TEXT.value, metadata: Dict[str, Any] = None) -> Message:
        async with async_session_maker() as session:
            model = MessageModel(
                chat_id=int(chat_id),
                role=role,
                type=type,
                content=content,
                extra=json.dumps(metadata or {}, ensure_ascii=False)
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def update_message(self, message_id: str, **kwargs) -> Optional[Message]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(MessageModel).where(MessageModel.id == int(message_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None

            for key, value in kwargs.items():
                if hasattr(model, key):
                    if key == "metadata" and isinstance(value, dict):
                        setattr(model, "extra", json.dumps(
                            value, ensure_ascii=False))
                    else:
                        setattr(model, key, value)

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
        metadata = {}
        try:
            metadata = json.loads(model.extra) if model.extra else {}
        except:
            pass

        return Message(
            id=str(model.id),
            chat_id=str(model.chat_id),
            role=model.role,
            type=model.type,
            content=model.content,
            metadata=metadata,
            created_at=model.created_at.isoformat() if model.created_at else None
        )
