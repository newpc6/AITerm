import logging
from typing import List, Optional

from sqlalchemy import select, delete, func

from app.db import async_session_maker
from app.db.sandbox_config import (
    SandboxConfigModel, SandboxPathModel, SandboxDangerousPatternModel,
    SandboxCommandBlacklistModel, SandboxCommandWhitelistModel
)
from app.models.sandbox_config import (
    SandboxConfig, SandboxPath, SandboxDangerousPattern,
    SandboxCommandItem
)
from app.utils import now_iso

logger = logging.getLogger(__name__)


class SandboxConfigRepository:

    async def get_config(self) -> Optional[SandboxConfig]:
        async with async_session_maker() as session:
            result = await session.execute(select(SandboxConfigModel).limit(1))
            model = result.scalar_one_or_none()
            return self._to_config(model) if model else None

    async def update_config(self, **kwargs) -> SandboxConfig:
        async with async_session_maker() as session:
            now = now_iso()
            result = await session.execute(select(SandboxConfigModel).limit(1))
            model = result.scalar_one_or_none()

            if not model:
                model = SandboxConfigModel(created_at=now, updated_at=now)
                session.add(model)

            for key, value in kwargs.items():
                if value is not None and hasattr(model, key):
                    if key == "require_confirm":
                        setattr(model, key, 1 if value else 0)
                    elif key == "docker_auto_remove":
                        setattr(model, key, 1 if value else 0)
                    else:
                        setattr(model, key, value)

            model.updated_at = now
            await session.commit()
            await session.refresh(model)
            return self._to_config(model)

    async def list_paths(self) -> List[SandboxPath]:
        async with async_session_maker() as session:
            result = await session.execute(select(SandboxPathModel).order_by(SandboxPathModel.id))
            return [self._to_path(m) for m in result.scalars().all()]

    async def add_path(self, path: str) -> SandboxPath:
        async with async_session_maker() as session:
            now = now_iso()
            model = SandboxPathModel(path=path, created_at=now, updated_at=now)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_path(model)

    async def delete_path(self, path_id: int) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(delete(SandboxPathModel).where(SandboxPathModel.id == path_id))
            await session.commit()
            return result.rowcount > 0

    async def list_dangerous_patterns(self) -> List[SandboxDangerousPattern]:
        async with async_session_maker() as session:
            result = await session.execute(select(SandboxDangerousPatternModel).order_by(SandboxDangerousPatternModel.scope, SandboxDangerousPatternModel.id))
            return [self._to_pattern(m) for m in result.scalars().all()]

    async def add_dangerous_pattern(self, pattern: str, description: str = "", scope: str = "sandbox") -> SandboxDangerousPattern:
        async with async_session_maker() as session:
            now = now_iso()
            model = SandboxDangerousPatternModel(pattern=pattern, description=description, scope=scope, created_at=now, updated_at=now)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_pattern(model)

    async def update_dangerous_pattern(self, pattern_id: int, **kwargs) -> Optional[SandboxDangerousPattern]:
        async with async_session_maker() as session:
            result = await session.execute(select(SandboxDangerousPatternModel).where(SandboxDangerousPatternModel.id == pattern_id))
            model = result.scalar_one_or_none()
            if not model:
                return None
            for key, value in kwargs.items():
                if value is not None and hasattr(model, key):
                    setattr(model, key, value)
            model.updated_at = now_iso()
            await session.commit()
            await session.refresh(model)
            return self._to_pattern(model)

    async def delete_dangerous_pattern(self, pattern_id: int) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(delete(SandboxDangerousPatternModel).where(SandboxDangerousPatternModel.id == pattern_id))
            await session.commit()
            return result.rowcount > 0

    async def list_blacklist(self) -> List[SandboxCommandItem]:
        async with async_session_maker() as session:
            result = await session.execute(select(SandboxCommandBlacklistModel).order_by(SandboxCommandBlacklistModel.scope, SandboxCommandBlacklistModel.id))
            return [self._to_cmd(m) for m in result.scalars().all()]

    async def add_blacklist(self, command: str, scope: str = "sandbox") -> SandboxCommandItem:
        async with async_session_maker() as session:
            now = now_iso()
            model = SandboxCommandBlacklistModel(command=command, scope=scope, created_at=now, updated_at=now)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_cmd(model)

    async def update_blacklist(self, item_id: int, **kwargs) -> Optional[SandboxCommandItem]:
        async with async_session_maker() as session:
            result = await session.execute(select(SandboxCommandBlacklistModel).where(SandboxCommandBlacklistModel.id == item_id))
            model = result.scalar_one_or_none()
            if not model:
                return None
            for key, value in kwargs.items():
                if value is not None and hasattr(model, key):
                    setattr(model, key, value)
            model.updated_at = now_iso()
            await session.commit()
            await session.refresh(model)
            return self._to_cmd(model)

    async def delete_blacklist(self, item_id: int) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(delete(SandboxCommandBlacklistModel).where(SandboxCommandBlacklistModel.id == item_id))
            await session.commit()
            return result.rowcount > 0

    async def list_whitelist(self) -> List[SandboxCommandItem]:
        async with async_session_maker() as session:
            result = await session.execute(select(SandboxCommandWhitelistModel).order_by(SandboxCommandWhitelistModel.scope, SandboxCommandWhitelistModel.id))
            return [self._to_cmd(m) for m in result.scalars().all()]

    async def add_whitelist(self, command: str, scope: str = "sandbox") -> SandboxCommandItem:
        async with async_session_maker() as session:
            now = now_iso()
            model = SandboxCommandWhitelistModel(command=command, scope=scope, created_at=now, updated_at=now)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_cmd(model)

    async def update_whitelist(self, item_id: int, **kwargs) -> Optional[SandboxCommandItem]:
        async with async_session_maker() as session:
            result = await session.execute(select(SandboxCommandWhitelistModel).where(SandboxCommandWhitelistModel.id == item_id))
            model = result.scalar_one_or_none()
            if not model:
                return None
            for key, value in kwargs.items():
                if value is not None and hasattr(model, key):
                    setattr(model, key, value)
            model.updated_at = now_iso()
            await session.commit()
            await session.refresh(model)
            return self._to_cmd(model)

    async def delete_whitelist(self, item_id: int) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(delete(SandboxCommandWhitelistModel).where(SandboxCommandWhitelistModel.id == item_id))
            await session.commit()
            return result.rowcount > 0

    def _to_config(self, m: SandboxConfigModel) -> SandboxConfig:
        return SandboxConfig(
            id=str(m.id),
            mode=m.mode,
            rules_prompt=m.rules_prompt,
            require_confirm=bool(m.require_confirm),
            max_file_size_mb=m.max_file_size_mb,
            docker_image=m.docker_image,
            docker_network=m.docker_network,
            docker_memory=m.docker_memory,
            docker_cpu=m.docker_cpu,
            docker_timeout=m.docker_timeout,
            docker_auto_remove=bool(m.docker_auto_remove),
            updated_by=m.updated_by,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def _to_path(self, m: SandboxPathModel) -> SandboxPath:
        return SandboxPath(id=str(m.id), path=m.path, created_at=m.created_at, updated_at=m.updated_at)

    def _to_pattern(self, m: SandboxDangerousPatternModel) -> SandboxDangerousPattern:
        return SandboxDangerousPattern(id=str(m.id), pattern=m.pattern, description=m.description, scope=m.scope, created_at=m.created_at, updated_at=m.updated_at)

    def _to_cmd(self, m) -> SandboxCommandItem:
        return SandboxCommandItem(id=str(m.id), command=m.command, scope=m.scope, created_at=m.created_at, updated_at=m.updated_at)
