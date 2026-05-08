import json
from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import IGlobalSettingsRepository, IAuthSettingsRepository
from app.models import GlobalSettings, AuthSettings
from app.db import async_session_maker
from app.db.settings import SystemDictModel, AuthSettingsModel
from app.utils import now_iso

DICT_CATEGORY = "global_settings"

CONFIG_KEYS = [
    "chat_system_prompt",
    "chat_history_limit",
    "max_iterations",
    "show_llm_input",
    "execution_planner_prompt",
    "execution_planner_user_prompt",
    "execution_windows_tool_prompt",
    "execution_linux_tool_prompt",
    "execution_mac_tool_prompt",
    "execution_failure_repair_prompt",
    "execution_command_rules_prompt",
    "execution_command_blacklist",
    "execution_command_whitelist",
    "sandbox_paths",
    "sandbox_rules_prompt",
    "llm_debug_logging",
]

DEFAULT_VALUES = {
    "chat_history_limit": "12",
    "max_iterations": "20",
    "show_llm_input": "false",
    "execution_command_blacklist": "[]",
    "execution_command_whitelist": "[]",
    "sandbox_paths": "[]",
    "llm_debug_logging": "false",
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
                "chat_system_prompt": settings.chat_system_prompt,
                "chat_history_limit": str(settings.chat_history_limit),
                "max_iterations": str(settings.max_iterations),
                "show_llm_input": "true" if settings.show_llm_input else "false",
                "execution_planner_prompt": settings.execution_planner_prompt,
                "execution_planner_user_prompt": settings.execution_planner_user_prompt,
                "execution_windows_tool_prompt": settings.execution_windows_tool_prompt,
                "execution_linux_tool_prompt": settings.execution_linux_tool_prompt,
                "execution_mac_tool_prompt": settings.execution_mac_tool_prompt,
                "execution_failure_repair_prompt": settings.execution_failure_repair_prompt,
                "execution_command_rules_prompt": settings.execution_command_rules_prompt,
                "execution_command_blacklist": json.dumps(settings.execution_command_blacklist),
                "execution_command_whitelist": json.dumps(settings.execution_command_whitelist),
                "sandbox_paths": json.dumps(settings.sandbox_paths),
                "sandbox_rules_prompt": settings.sandbox_rules_prompt,
                "llm_debug_logging": "true" if settings.llm_debug_logging else "false",
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
        sandbox_paths = []
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
            sandbox_paths = json.loads(
                get_value("sandbox_paths", "[]"))
        except:
            pass

        try:
            chat_history_limit = int(get_value("chat_history_limit", "12"))
        except:
            chat_history_limit = 12

        try:
            max_iterations = int(get_value("max_iterations", "20"))
        except:
            max_iterations = 20

        show_llm_input = get_value(
            "show_llm_input", "false").lower() == "true"

        llm_debug_logging = get_value(
            "llm_debug_logging", "false").lower() == "true"

        return GlobalSettings(
            chat_system_prompt=get_value("chat_system_prompt"),
            chat_history_limit=chat_history_limit,
            max_iterations=max_iterations,
            show_llm_input=show_llm_input,
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
            sandbox_paths=sandbox_paths,
            sandbox_rules_prompt=get_value("sandbox_rules_prompt"),
            llm_debug_logging=llm_debug_logging,
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
