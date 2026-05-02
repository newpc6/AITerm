from typing import List, Optional, Tuple
from datetime import datetime
from passlib.context import CryptContext

from app.models import User, UserCreate, UserUpdate, UserRole, UserStatus
from app.repositories import IUserRepository
from app.utils import now_iso

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    def __init__(self, repo: IUserRepository):
        self.repo = repo

    async def list_users(self, page: int = 1, page_size: int = 20) -> Tuple[List[User], int]:
        return await self.repo.list_users(page, page_size)

    async def get_user(self, user_id: str) -> Optional[User]:
        return await self.repo.get_user(user_id)

    async def get_user_by_username(self, username: str) -> Optional[User]:
        return await self.repo.get_user_by_username(username)

    async def create_user(self, data: UserCreate) -> User:
        existing = await self.repo.get_user_by_username(data.username)
        if existing:
            raise ValueError("用户名已存在")

        password_hash = pwd_context.hash(data.password)
        now = now_iso()

        user = User(
            id="0",
            username=data.username,
            display_name=data.display_name or data.username,
            role=data.role or UserRole.USER,
            status=UserStatus.ACTIVE,
            last_login_at="",
            created_at=now,
            updated_at=now
        )

        return await self.repo.create_user(user, password_hash)

    async def update_user(self, user_id: str, data: UserUpdate) -> Optional[User]:
        user = await self.repo.get_user(user_id)
        if not user:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(user, key, value)

        user.updated_at = now_iso()
        return await self.repo.update_user(user_id, user)

    async def delete_user(self, user_id: str) -> bool:
        user = await self.repo.get_user(user_id)
        if not user:
            return False

        if user.role == UserRole.ADMIN:
            admin_count = await self.repo.count_active_admins()
            if admin_count <= 1:
                raise ValueError("不能删除最后一个管理员账户")

        return await self.repo.delete_user(user_id)

    async def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        user = await self.repo.get_user(user_id)
        if not user:
            return False

        user_with_hash = await self.repo.get_user_by_username(user.username)
        if not user_with_hash:
            return False

        password_hash = pwd_context.hash(new_password)
        return await self.repo.update_password_hash(user_id, password_hash)

    async def update_last_login(self, user_id: str) -> bool:
        return await self.repo.update_last_login(user_id)
