import json
from typing import List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import select, delete, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.db.chat import ChatModel
from app.models.chat import Chat, ChatStatus


class ChatRepository:
    async def list_chats(self, page: int = 1, page_size: int = 20) -> Tuple[List[Chat], int]:
        async with async_session_maker() as session:
            count_result = await session.execute(
                select(func.count(ChatModel.id))
            )
            total = count_result.scalar() or 0

            offset = (page - 1) * page_size
            result = await session.execute(
                select(ChatModel)
                .order_by(desc(ChatModel.updated_at))
                .offset(offset)
                .limit(page_size)
            )
            models = result.scalars().all()
            return [self._to_domain(m) for m in models], total

    async def get_chat(self, chat_id: str) -> Optional[Chat]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ChatModel).where(ChatModel.id == int(chat_id))
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def create_chat(self, title: str = "", node_id: int = 1, model_id: Optional[int] = None, model_name: Optional[str] = None) -> Chat:
        async with async_session_maker() as session:
            model = ChatModel(
                title=title,
                node_id=node_id,
                model_id=model_id,
                model_name=model_name,
                status=ChatStatus.IDLE.value,
                summary=""
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def update_chat(self, chat_id: str, **kwargs) -> Optional[Chat]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ChatModel).where(ChatModel.id == int(chat_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            
            for key, value in kwargs.items():
                if hasattr(model, key):
                    setattr(model, key, value)
            
            await session.commit()
            return self._to_domain(model)

    async def delete_chat(self, chat_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(ChatModel).where(ChatModel.id == int(chat_id))
            )
            await session.commit()
            return result.rowcount > 0

    def _to_domain(self, model: ChatModel) -> Chat:
        return Chat(
            id=str(model.id),
            title=model.title,
            node_id=str(model.node_id),
            model_id=str(model.model_id) if model.model_id else None,
            model_name=model.model_name,
            status=model.status,
            summary=model.summary,
            created_at=model.created_at.isoformat() if model.created_at else None,
            updated_at=model.updated_at.isoformat() if model.updated_at else None
        )
