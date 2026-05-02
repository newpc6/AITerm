import json
from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import IModelConfigRepository, IGlobalSettingsRepository, IAuthSettingsRepository
from app.models import ModelConfig, GlobalSettings, AuthSettings
from app.db import async_session_maker
from app.db.settings import ModelConfigModel, SystemDictModel, AuthSettingsModel
from app.utils import now_iso


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
                select(ModelConfigModel).where(
                    ModelConfigModel.id == int(model_id))
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def get_default_model(self) -> Optional[ModelConfig]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ModelConfigModel).where(
                    ModelConfigModel.is_default == 1).limit(1)
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def create_model(self, model: ModelConfig) -> ModelConfig:
        async with async_session_maker() as session:
            now = now_iso()
            db_model = ModelConfigModel(
                name=model.name,
                api_url=model.api_url,
                api_key=model.api_key,
                model=model.model,
                temperature=int(model.temperature * 100),
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
                select(ModelConfigModel).where(
                    ModelConfigModel.id == int(model_id))
            )
            db_model = result.scalar_one_or_none()
            if not db_model:
                return None

            db_model.name = model.name
            db_model.api_url = model.api_url
            db_model.api_key = model.api_key
            db_model.model = model.model
            db_model.temperature = int(model.temperature * 100)
            db_model.extra_params_json = json.dumps(model.extra_params)
            db_model.extra_body_json = json.dumps(model.extra_body)
            db_model.extra_headers_json = json.dumps(model.extra_headers)
            db_model.is_default = 1 if model.is_default else 0
            db_model.updated_at = now_iso()

            await session.commit()
            await session.refresh(db_model)
            return self._to_domain(db_model)

    async def delete_model(self, model_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ModelConfigModel).where(
                    ModelConfigModel.id == int(model_id))
            )
            db_model = result.scalar_one_or_none()
            if not db_model:
                return False

            await session.delete(db_model)
            await session.commit()
            return True

    async def set_default_model(self, model_id: str) -> Optional[ModelConfig]:
        async with async_session_maker() as session:
            await session.execute(
                update(ModelConfigModel).values(is_default=0)
            )

            result = await session.execute(
                select(ModelConfigModel).where(
                    ModelConfigModel.id == int(model_id))
            )
            db_model = result.scalar_one_or_none()
            if not db_model:
                return None

            db_model.is_default = 1
            db_model.updated_at = now_iso()
            await session.commit()
            await session.refresh(db_model)
            return self._to_domain(db_model)

    def _to_domain(self, model: ModelConfigModel) -> ModelConfig:
        extra_params = {}
        extra_body = {}
        extra_headers = {}
        try:
            extra_params = json.loads(
                model.extra_params_json) if model.extra_params_json else {}
        except:
            pass
        try:
            extra_body = json.loads(
                model.extra_body_json) if model.extra_body_json else {}
        except:
            pass
        try:
            extra_headers = json.loads(
                model.extra_headers_json) if model.extra_headers_json else {}
        except:
            pass

        return ModelConfig(
            id=str(model.id),
            name=model.name,
            api_url=model.api_url,
            api_key=model.api_key,
            model=model.model,
            temperature=model.temperature / 100.0,
            extra_params=extra_params,
            extra_body=extra_body,
            extra_headers=extra_headers,
            is_default=bool(model.is_default),
            created_at=model.created_at,
            updated_at=model.updated_at
        )


DICT_CATEGORY = "global_settings"

CONFIG_KEYS = [
    "intent_detection_prompt",
    "chat_system_prompt",
    "chat_history_limit",
    "execution_planner_prompt",
    "execution_planner_user_prompt",
    "execution_windows_tool_prompt",
    "execution_linux_tool_prompt",
    "execution_mac_tool_prompt",
    "execution_failure_repair_prompt",
    "execution_command_rules_prompt",
    "execution_command_blacklist",
    "execution_command_whitelist",
]

DEFAULT_VALUES = {
    "chat_history_limit": "12",
    "execution_command_blacklist": "[]",
    "execution_command_whitelist": "[]",
}


class GlobalSettingsRepository(IGlobalSettingsRepository):
    async def get_settings(self) -> GlobalSettings:
        async with async_session_maker() as session:
            result = await session.execute(
                select(SystemDictModel).where(
                    SystemDictModel.category == DICT_CATEGORY)
            )
            configs = {c.key: c.value for c in result.scalars().all()}

            return self._to_domain(configs)

    async def update_settings(self, settings: GlobalSettings) -> GlobalSettings:
        async with async_session_maker() as session:
            now = now_iso()

            data = {
                "intent_detection_prompt": settings.intent_detection_prompt,
                "chat_system_prompt": settings.chat_system_prompt,
                "chat_history_limit": str(settings.chat_history_limit),
                "execution_planner_prompt": settings.execution_planner_prompt,
                "execution_planner_user_prompt": settings.execution_planner_user_prompt,
                "execution_windows_tool_prompt": settings.execution_windows_tool_prompt,
                "execution_linux_tool_prompt": settings.execution_linux_tool_prompt,
                "execution_mac_tool_prompt": settings.execution_mac_tool_prompt,
                "execution_failure_repair_prompt": settings.execution_failure_repair_prompt,
                "execution_command_rules_prompt": settings.execution_command_rules_prompt,
                "execution_command_blacklist": json.dumps(settings.execution_command_blacklist),
                "execution_command_whitelist": json.dumps(settings.execution_command_whitelist),
            }

            for key, value in data.items():
                result = await session.execute(
                    select(SystemDictModel).where(
                        SystemDictModel.category == DICT_CATEGORY,
                        SystemDictModel.key == key
                    )
                )
                config = result.scalar_one_or_none()
                if config:
                    config.value = value
                    config.updated_at = now
                else:
                    config = SystemDictModel(
                        category=DICT_CATEGORY,
                        key=key,
                        value=value,
                        created_at=now,
                        updated_at=now
                    )
                    session.add(config)

            await session.commit()
            return await self.get_settings()

    def _to_domain(self, configs: dict) -> GlobalSettings:
        def get_value(key: str, default: str = "") -> str:
            return configs.get(key, DEFAULT_VALUES.get(key, default))

        blacklist = []
        whitelist = []
        try:
            blacklist = json.loads(
                get_value("execution_command_blacklist", "[]"))
        except:
            pass
        try:
            whitelist = json.loads(
                get_value("execution_command_whitelist", "[]"))
        except:
            pass

        try:
            chat_history_limit = int(get_value("chat_history_limit", "12"))
        except:
            chat_history_limit = 12

        return GlobalSettings(
            intent_detection_prompt=get_value("intent_detection_prompt"),
            chat_system_prompt=get_value("chat_system_prompt"),
            chat_history_limit=chat_history_limit,
            execution_planner_prompt=get_value("execution_planner_prompt"),
            execution_planner_user_prompt=get_value(
                "execution_planner_user_prompt"),
            execution_windows_tool_prompt=get_value(
                "execution_windows_tool_prompt"),
            execution_linux_tool_prompt=get_value(
                "execution_linux_tool_prompt"),
            execution_mac_tool_prompt=get_value("execution_mac_tool_prompt"),
            execution_failure_repair_prompt=get_value(
                "execution_failure_repair_prompt"),
            execution_command_rules_prompt=get_value(
                "execution_command_rules_prompt"),
            execution_command_blacklist=blacklist,
            execution_command_whitelist=whitelist,
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

            return AuthSettings(
                enabled=bool(model.enabled),
                allow_password_login=bool(model.allow_password_login),
                session_ttl_hours=model.session_ttl_hours
            )

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

            return AuthSettings(
                enabled=bool(model.enabled),
                allow_password_login=bool(model.allow_password_login),
                session_ttl_hours=model.session_ttl_hours
            )
