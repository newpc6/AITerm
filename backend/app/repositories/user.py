from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import IUserRepository
from app.models import User, UserRole, UserStatus
from app.db import async_session_maker
from app.db.user import UserModel
from app.utils import now_iso


class UserRepository(IUserRepository):
    async def list_users(self, page: int = 1, page_size: int = 20) -> Tuple[List[User], int]:
        async with async_session_maker() as session:
            count_result = await session.execute(
                select(func.count(UserModel.id))
            )
            total = count_result.scalar() or 0

            offset = (page - 1) * page_size
            result = await session.execute(
                select(UserModel)
                .offset(offset)
                .limit(page_size)
            )
            models = result.scalars().all()
            return [self._to_domain(m) for m in models], total

    async def get_user(self, user_id: str) -> Optional[User]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.id == int(user_id))
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.username == username)
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def create_user(self, user: User, password_hash: str) -> User:
        async with async_session_maker() as session:
            now = now_iso()
            model = UserModel(
                username=user.username,
                display_name=user.display_name,
                password_hash=password_hash,
                role=user.role.value if isinstance(user.role, UserRole) else user.role,
                status=user.status.value if isinstance(user.status, UserStatus) else user.status,
                last_login_at="",
                created_at=now,
                updated_at=now
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def update_user(self, user_id: str, user: User) -> Optional[User]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.id == int(user_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            
            model.display_name = user.display_name
            model.role = user.role.value if isinstance(user.role, UserRole) else user.role
            model.status = user.status.value if isinstance(user.status, UserStatus) else user.status
            model.updated_at = now_iso()
            
            await session.commit()
            return self._to_domain(model)

    async def delete_user(self, user_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(UserModel).where(UserModel.id == int(user_id))
            )
            await session.commit()
            return result.rowcount > 0

    async def update_password_hash(self, user_id: str, password_hash: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.id == int(user_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return False
            
            model.password_hash = password_hash
            model.updated_at = now_iso()
            await session.commit()
            return True

    async def update_last_login(self, user_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.id == int(user_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return False
            
            model.last_login_at = now_iso()
            await session.commit()
            return True

    async def count_active_admins(self) -> int:
        async with async_session_maker() as session:
            result = await session.execute(
                select(func.count()).where(
                    UserModel.role == UserRole.ADMIN.value,
                    UserModel.status == UserStatus.ACTIVE.value
                )
            )
            return result.scalar() or 0

    async def get_first_admin(self):
        async with async_session_maker() as session:
            result = await session.execute(
                select(UserModel).where(
                    UserModel.role == UserRole.ADMIN.value,
                    UserModel.status == UserStatus.ACTIVE.value
                ).limit(1)
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    def _to_domain(self, model: UserModel) -> User:
        return User(
            id=str(model.id),
            username=model.username,
            display_name=model.display_name,
            role=UserRole(model.role) if model.role else UserRole.USER,
            status=UserStatus(model.status) if model.status else UserStatus.ACTIVE,
            last_login_at=model.last_login_at,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
