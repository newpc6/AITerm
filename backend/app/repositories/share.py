import secrets
import hashlib
from typing import Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete, func

from app.db import async_session_maker
from app.db.share import ShareModel
from app.models.share import Share, ShareListItem
from app.utils import ensure_timezone


def generate_share_id() -> str:
    return secrets.token_urlsafe(8)[:12]


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


class ShareRepository:
    async def create_share(
        self,
        chat_id: str,
        title: str = "",
        password: Optional[str] = None,
        expires_in: Optional[int] = None,
        show_input: bool = True,
        show_thinking: bool = True,
        show_tools: bool = True,
        show_answer: bool = True,
        show_full_input: bool = False,
        user_id: int = None,
    ) -> Share:
        async with async_session_maker() as session:
            share_id = generate_share_id()
            while await self._share_id_exists(session, share_id):
                share_id = generate_share_id()

            expires_at = None
            if expires_in and expires_in > 0:
                expires_at = datetime.now(
                    timezone.utc) + timedelta(seconds=expires_in)

            hashed_password = hash_password(password) if password else None

            model = ShareModel(
                share_id=share_id,
                chat_id=int(chat_id),
                title=title,
                password=hashed_password,
                expires_at=expires_at,
                show_input=show_input,
                show_thinking=show_thinking,
                show_tools=show_tools,
                show_answer=show_answer,
                show_full_input=show_full_input,
                user_id=user_id
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def get_share(self, share_id: str) -> Optional[Share]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ShareModel).where(ShareModel.share_id == share_id)
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def get_share_by_chat(self, chat_id: str) -> Optional[Share]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ShareModel).where(ShareModel.chat_id == int(chat_id))
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def list_shares(self, page: int = 1, page_size: int = 20, user_id: int = None) -> Tuple[List[ShareListItem], int]:
        async with async_session_maker() as session:
            if user_id is not None:
                count_query = select(func.count(ShareModel.id)).where(
                    ShareModel.user_id == user_id)
                items_query = select(ShareModel).where(
                    ShareModel.user_id == user_id)
            else:
                count_query = select(func.count(ShareModel.id))
                items_query = select(ShareModel)

            count_result = await session.execute(count_query)
            total = count_result.scalar() or 0

            offset = (page - 1) * page_size
            result = await session.execute(
                items_query
                .order_by(ShareModel.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            models = result.scalars().all()
            return [self._to_list_item(m) for m in models], total

    async def delete_share(self, share_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(ShareModel).where(ShareModel.share_id == share_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def delete_shares_by_ids(self, share_ids: List[str]) -> int:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(ShareModel).where(ShareModel.share_id.in_(share_ids))
            )
            await session.commit()
            return result.rowcount

    async def delete_share_by_chat(self, chat_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(ShareModel).where(ShareModel.chat_id == int(chat_id))
            )
            await session.commit()
            return result.rowcount > 0

    async def increment_view_count(self, share_id: str) -> None:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ShareModel).where(ShareModel.share_id == share_id)
            )
            model = result.scalar_one_or_none()
            if model:
                model.view_count = (model.view_count or 0) + 1
                await session.commit()

    async def verify_share_password(self, share_id: str, password: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ShareModel).where(ShareModel.share_id == share_id)
            )
            model = result.scalar_one_or_none()
            if not model or not model.password:
                return False
            return verify_password(password, model.password)

    async def is_expired(self, share_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ShareModel).where(ShareModel.share_id == share_id)
            )
            model = result.scalar_one_or_none()
            if not model or not model.expires_at:
                return False
            expires_at = ensure_timezone(model.expires_at)
            return datetime.now(timezone.utc) > expires_at

    async def _share_id_exists(self, session, share_id: str) -> bool:
        result = await session.execute(
            select(ShareModel).where(ShareModel.share_id == share_id)
        )
        return result.scalar_one_or_none() is not None

    def _to_domain(self, model: ShareModel) -> Share:
        created_at = ensure_timezone(model.created_at)
        expires_at = ensure_timezone(
            model.expires_at) if model.expires_at else None

        return Share(
            id=str(model.id),
            share_id=model.share_id,
            chat_id=str(model.chat_id),
            title=model.title,
            has_password=bool(model.password),
            expires_at=expires_at.isoformat() if expires_at else None,
            view_count=model.view_count or 0,
            created_at=created_at.isoformat() if created_at else None,
            show_input=model.show_input if model.show_input is not None else True,
            show_thinking=model.show_thinking if model.show_thinking is not None else True,
            show_tools=model.show_tools if model.show_tools is not None else True,
            show_answer=model.show_answer if model.show_answer is not None else True,
            show_full_input=model.show_full_input if model.show_full_input is not None else False
        )

    def _to_list_item(self, model: ShareModel) -> ShareListItem:
        created_at = ensure_timezone(model.created_at)
        expires_at = ensure_timezone(
            model.expires_at) if model.expires_at else None

        return ShareListItem(
            id=str(model.id),
            share_id=model.share_id,
            chat_id=str(model.chat_id),
            title=model.title,
            has_password=bool(model.password),
            expires_at=expires_at.isoformat() if expires_at else None,
            view_count=model.view_count or 0,
            created_at=created_at.isoformat() if created_at else None,
            show_input=model.show_input if model.show_input is not None else True,
            show_thinking=model.show_thinking if model.show_thinking is not None else True,
            show_tools=model.show_tools if model.show_tools is not None else True,
            show_answer=model.show_answer if model.show_answer is not None else True,
            show_full_input=model.show_full_input if model.show_full_input is not None else False
        )
