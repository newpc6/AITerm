import json
from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import IModelConfigRepository, IGlobalSettingsRepository, IAuthSettingsRepository
from app.models import ModelConfig, GlobalSettings, AuthSettings
from app.db import async_session_maker
from app.db.settings import ModelConfigModel, GlobalSettingsModel, AuthSettingsModel


class ModelConfigRepository(IModelConfigRepository):
    async def list_models(self, page: int = 1, page_size: int = 20) -> Tuple[List[ModelConfig], int]:
        async with async_session_maker() as session:
            count_result = await session.execute(
                select(func.count(ModelConfigModel.id))
            )
            total = count_result.scalar() or 0

            offset = (page - 1) * page_size
            result = await session.execute(
                select(ModelConfigModel)
                .order_by(
                    ModelConfigModel.is_default.desc(),
                    ModelConfigModel.name
                )
                .offset(offset)
                .limit(page_size)
            )
            models = result.scalars().all()
            return [self._to_domain(m) for m in models], total

    async def get_model(self, model_id: str) -> Optional[ModelConfig]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ModelConfigModel).where(ModelConfigModel.id == int(model_id))
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def get_default_model(self) -> Optional[ModelConfig]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ModelConfigModel).where(ModelConfigModel.is_default == 1).limit(1)
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def create_model(self, model: ModelConfig) -> ModelConfig:
        async with async_session_maker() as session:
            now = datetime.utcnow().isoformat()
            db_model = ModelConfigModel(
                name=model.name,
                api_url=model.api_url,
                api_key=model.api_key,
                model=model.model,
                temperature=model.temperature,
                extra_params_json=json.dumps(model.extra_params),
                extra_body_json=json.dumps(model.extra_body),
                extra_headers_json=json.dumps(model.extra_headers),
                is_default=1 if model.is_default else 0,
                created_at=now,
                updated_at=now
            )
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return self._to_domain(db_model)

    async def update_model(self, model_id: str, model: ModelConfig) -> Optional[ModelConfig]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ModelConfigModel).where(ModelConfigModel.id == int(model_id))
            )
            db_model = result.scalar_one_or_none()
            if not db_model:
                return None
            
            db_model.name = model.name
            db_model.api_url = model.api_url
            db_model.api_key = model.api_key
            db_model.model = model.model
            db_model.temperature = model.temperature
            db_model.extra_params_json = json.dumps(model.extra_params)
            db_model.extra_body_json = json.dumps(model.extra_body)
            db_model.extra_headers_json = json.dumps(model.extra_headers)
            db_model.is_default = 1 if model.is_default else 0
            db_model.updated_at = datetime.utcnow().isoformat()
            
            await session.commit()
            return self._to_domain(db_model)

    async def delete_model(self, model_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(ModelConfigModel).where(ModelConfigModel.id == int(model_id))
            )
            await session.commit()
            return result.rowcount > 0

    async def set_default_model(self, model_id: str) -> bool:
        async with async_session_maker() as session:
            await session.execute(
                update(ModelConfigModel).values(is_default=0)
            )
            await session.execute(
                update(ModelConfigModel)
                .where(ModelConfigModel.id == int(model_id))
                .values(is_default=1)
            )
            await session.commit()
            return True

    def _to_domain(self, model: ModelConfigModel) -> ModelConfig:
        extra_params = {}
        extra_body = {}
        extra_headers = {}
        try:
            extra_params = json.loads(model.extra_params_json) if model.extra_params_json else {}
        except:
            pass
        try:
            extra_body = json.loads(model.extra_body_json) if model.extra_body_json else {}
        except:
            pass
        try:
            extra_headers = json.loads(model.extra_headers_json) if model.extra_headers_json else {}
        except:
            pass
        
        return ModelConfig(
            id=str(model.id),
            name=model.name,
            api_url=model.api_url,
            api_key=model.api_key,
            model=model.model,
            temperature=model.temperature,
            extra_params=extra_params,
            extra_body=extra_body,
            extra_headers=extra_headers,
            is_default=bool(model.is_default),
            created_at=model.created_at,
            updated_at=model.updated_at
        )


class GlobalSettingsRepository(IGlobalSettingsRepository):
    async def get_settings(self) -> GlobalSettings:
        async with async_session_maker() as session:
            result = await session.execute(select(GlobalSettingsModel))
            model = result.scalar_one_or_none()
            
            if not model:
                model = GlobalSettingsModel()
                session.add(model)
                await session.commit()
                await session.refresh(model)
            
            return self._to_domain(model)

    async def update_settings(self, settings: GlobalSettings) -> GlobalSettings:
        async with async_session_maker() as session:
            result = await session.execute(select(GlobalSettingsModel))
            model = result.scalar_one_or_none()
            
            if not model:
                model = GlobalSettingsModel()
                session.add(model)
            
            model.chat_system_prompt = settings.chat_system_prompt
            model.task_planner_prompt = settings.task_planner_prompt
            model.task_planner_user_prompt = settings.task_planner_user_prompt
            model.task_windows_tool_prompt = settings.task_windows_tool_prompt
            model.task_linux_tool_prompt = settings.task_linux_tool_prompt
            model.task_mac_tool_prompt = settings.task_mac_tool_prompt
            model.task_failure_repair_prompt = settings.task_failure_repair_prompt
            model.task_command_rules_prompt = settings.task_command_rules_prompt
            model.task_command_blacklist_json = json.dumps(settings.task_command_blacklist)
            model.task_command_whitelist_json = json.dumps(settings.task_command_whitelist)
            
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    def _to_domain(self, model: GlobalSettingsModel) -> GlobalSettings:
        blacklist = []
        whitelist = []
        try:
            blacklist = json.loads(model.task_command_blacklist_json) if model.task_command_blacklist_json else []
        except:
            pass
        try:
            whitelist = json.loads(model.task_command_whitelist_json) if model.task_command_whitelist_json else []
        except:
            pass
        
        return GlobalSettings(
            chat_system_prompt=model.chat_system_prompt or "",
            task_planner_prompt=model.task_planner_prompt or "",
            task_planner_user_prompt=model.task_planner_user_prompt or "",
            task_windows_tool_prompt=model.task_windows_tool_prompt or "",
            task_linux_tool_prompt=model.task_linux_tool_prompt or "",
            task_mac_tool_prompt=model.task_mac_tool_prompt or "",
            task_failure_repair_prompt=model.task_failure_repair_prompt or "",
            task_command_rules_prompt=model.task_command_rules_prompt or "",
            task_command_blacklist=blacklist,
            task_command_whitelist=whitelist
        )


class AuthSettingsRepository(IAuthSettingsRepository):
    async def get_settings(self) -> AuthSettings:
        async with async_session_maker() as session:
            result = await session.execute(select(AuthSettingsModel))
            model = result.scalar_one_or_none()
            
            if not model:
                model = AuthSettingsModel()
                session.add(model)
                await session.commit()
                await session.refresh(model)
            
            return self._to_domain(model)

    async def update_settings(self, settings: AuthSettings) -> AuthSettings:
        async with async_session_maker() as session:
            result = await session.execute(select(AuthSettingsModel))
            model = result.scalar_one_or_none()
            
            if not model:
                model = AuthSettingsModel()
                session.add(model)
            
            model.enabled = 1 if settings.enabled else 0
            model.allow_password_login = 1 if settings.allow_password_login else 0
            model.session_ttl_hours = settings.session_ttl_hours
            
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    def _to_domain(self, model: AuthSettingsModel) -> AuthSettings:
        return AuthSettings(
            enabled=bool(model.enabled),
            allow_password_login=bool(model.allow_password_login),
            session_ttl_hours=model.session_ttl_hours
        )
