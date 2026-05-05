from typing import List, Optional, Tuple
from sqlalchemy import select, delete, desc, func

from app.db import async_session_maker
from app.db.chat import ChatModel
from app.db.user import UserModel
from app.models.chat import Chat, ChatStatus
from app.utils import ensure_timezone


class ChatRepository:
    async def list_chats(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[int] = None,
        include_user_info: bool = False
    ) -> Tuple[List[Chat], int]:
        async with async_session_maker() as session:
            base_query = select(ChatModel)
            count_query = select(func.count(ChatModel.id))

            if user_id is not None:
                base_query = base_query.where(ChatModel.user_id == user_id)
                count_query = count_query.where(ChatModel.user_id == user_id)

            count_result = await session.execute(count_query)
            total = count_result.scalar() or 0

            offset = (page - 1) * page_size
            result = await session.execute(
                base_query
                .order_by(desc(ChatModel.updated_at))
                .offset(offset)
                .limit(page_size)
            )
            models = result.scalars().all()

            user_map = {}
            if include_user_info:
                user_ids = [m.user_id for m in models if m.user_id]
                if user_ids:
                    user_result = await session.execute(
                        select(UserModel).where(UserModel.id.in_(user_ids))
                    )
                    users = user_result.scalars().all()
                    user_map = {u.id: u for u in users}

            return [self._to_domain(m, user_map.get(m.user_id) if include_user_info else None) for m in models], total

    async def get_chat(self, chat_id: str) -> Optional[Chat]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ChatModel).where(ChatModel.id == int(chat_id))
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def create_chat(
        self,
        title: str = "",
        node_id: int = 1,
        model_id: Optional[int] = None,
        model_name: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Chat:
        async with async_session_maker() as session:
            model = ChatModel(
                title=title,
                node_id=node_id,
                model_id=model_id,
                model_name=model_name,
                user_id=user_id,
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

    def _to_domain(self, model: ChatModel, user: Optional[UserModel] = None) -> Chat:
        created_at = ensure_timezone(model.created_at)
        updated_at = ensure_timezone(model.updated_at)
        user_info = None
        if user:
            user_info = {
                "id": str(user.id),
                "username": user.username,
                "display_name": user.display_name
            }
        return Chat(
            id=str(model.id),
            title=model.title,
            node_id=str(model.node_id),
            model_id=str(model.model_id) if model.model_id else None,
            model_name=model.model_name,
            user_id=str(model.user_id) if model.user_id else None,
            user_info=user_info,
            status=model.status,
            summary=model.summary,
            created_at=created_at.isoformat() if created_at else None,
            updated_at=updated_at.isoformat() if updated_at else None
        )
