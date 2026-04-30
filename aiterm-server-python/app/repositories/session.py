from typing import Optional
from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import ISessionRepository
from app.models import Session
from app.db import async_session_maker
from app.db.session import SessionModel


class SessionRepository(ISessionRepository):
    async def get_session(self, token: str) -> Optional[Session]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(SessionModel).where(SessionModel.token == token)
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def create_session(self, session: Session) -> Session:
        async with async_session_maker() as session_ctx:
            model = SessionModel(
                token=session.token,
                user_id=int(session.user_id),
                created_at=session.created_at,
                expires_at=session.expires_at
            )
            session_ctx.add(model)
            await session_ctx.commit()
            await session_ctx.refresh(model)
            return self._to_domain(model)

    async def delete_session(self, token: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(SessionModel).where(SessionModel.token == token)
            )
            await session.commit()
            return result.rowcount > 0

    async def delete_user_sessions(self, user_id: str) -> int:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(SessionModel).where(SessionModel.user_id == int(user_id))
            )
            await session.commit()
            return result.rowcount

    def _to_domain(self, model: SessionModel) -> Session:
        return Session(
            id=str(model.id),
            token=model.token,
            user_id=str(model.user_id),
            created_at=model.created_at,
            expires_at=model.expires_at
        )
