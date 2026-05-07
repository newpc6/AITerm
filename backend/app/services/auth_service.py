import secrets
from datetime import datetime, timedelta
from typing import Optional

from app.models import AuthSettings, AuthStatus, AuthLoginData, User, UserRole, UserStatus, Session
from app.repositories import IUserRepository, ISessionRepository, IAuthSettingsRepository
from app.db import async_session_maker
from app.db.user import UserModel
from app.utils import now_iso
from sqlalchemy import select
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(
        self,
        user_repo: IUserRepository,
        session_repo: ISessionRepository,
        auth_settings_repo: IAuthSettingsRepository
    ):
        self.user_repo = user_repo
        self.session_repo = session_repo
        self.auth_settings_repo = auth_settings_repo

    async def get_auth_settings(self) -> AuthSettings:
        return await self.auth_settings_repo.get_settings()

    async def update_auth_settings(self, settings: AuthSettings) -> AuthSettings:
        return await self.auth_settings_repo.update_settings(settings)

    async def get_status(self, token: Optional[str] = None) -> AuthStatus:
        settings = await self.get_auth_settings()
        
        authenticated = False
        user = None
        if token:
            user = await self.validate_session(token)
            if user:
                authenticated = True
        
        return AuthStatus(
            enabled=settings.enabled,
            allow_password_login=settings.allow_password_login,
            authenticated=authenticated,
            user=user
        )

    async def login(self, username: str, password: str) -> Optional[Session]:
        settings = await self.get_auth_settings()
        if not settings.enabled:
            raise ValueError("认证未启用")

        async with async_session_maker() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.username == username)
            )
            user_model = result.scalar_one_or_none()
            
            if not user_model:
                raise ValueError("用户名或密码错误")

            if user_model.status != UserStatus.ACTIVE.value:
                raise ValueError("用户账户已禁用")

            if not pwd_context.verify(password, user_model.password_hash):
                raise ValueError("用户名或密码错误")

            user_model.last_login_at = now_iso()
            await session.commit()

        token = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=settings.session_ttl_hours)

        session_obj = Session(
            id="0",
            token=token,
            user_id=str(user_model.id),
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat()
        )

        return await self.session_repo.create_session(session_obj)

    async def validate_session(self, token: str) -> Optional[User]:
        session = await self.session_repo.get_session(token)
        if not session:
            return None

        expires_at = datetime.fromisoformat(session.expires_at)
        if datetime.utcnow() > expires_at:
            await self.session_repo.delete_session(token)
            return None

        user = await self.user_repo.get_user(session.user_id)
        if not user or user.status != UserStatus.ACTIVE:
            return None

        return user

    async def logout(self, token: str) -> bool:
        return await self.session_repo.delete_session(token)

    async def logout_all(self, user_id: str) -> int:
        return await self.session_repo.delete_user_sessions(user_id)

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.id == int(user_id))
            )
            user_model = result.scalar_one_or_none()
            
            if not user_model:
                raise ValueError("用户不存在")

            if not pwd_context.verify(current_password, user_model.password_hash):
                raise ValueError("当前密码错误")

            user_model.password_hash = pwd_context.hash(new_password)
            user_model.updated_at = now_iso()
            await session.commit()
            
        return True

    async def update_profile(self, user_id: str, data: dict) -> None:
        async with async_session_maker() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.id == int(user_id))
            )
            user_model = result.scalar_one_or_none()
            if not user_model:
                raise ValueError("用户不存在")

            if 'display_name' in data and data['display_name']:
                user_model.display_name = data['display_name']
            user_model.updated_at = now_iso()
            await session.commit()
