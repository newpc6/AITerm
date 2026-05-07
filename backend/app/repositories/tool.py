import json
import logging
from typing import List, Optional, Union, Tuple
from sqlalchemy import select, delete, func, and_

from app.db import async_session_maker
from app.db.tool import ToolModel, UserToolModel
from app.models.tool import Tool, ToolParameters, ToolConfigSchema, UserTool
from app.utils import now_iso

logger = logging.getLogger(__name__)


def _serialize_parameters(params: Union[ToolParameters, dict, None]) -> Optional[str]:
    if params is None:
        return None
    if isinstance(params, dict):
        return json.dumps(params, ensure_ascii=False)
    return json.dumps(params.model_dump(), ensure_ascii=False)


def _serialize_config_schema(schema: Union[ToolConfigSchema, dict, None]) -> Optional[str]:
    if schema is None:
        return None
    if isinstance(schema, dict):
        return json.dumps(schema, ensure_ascii=False)
    return json.dumps(schema.model_dump(), ensure_ascii=False)


class ToolRepository:

    async def list_tools(self, enabled_only: bool = False) -> List[Tool]:
        async with async_session_maker() as session:
            query = select(ToolModel).order_by(ToolModel.name)
            if enabled_only:
                query = query.where(ToolModel.enabled == True)
            result = await session.execute(query)
            return [self._to_domain(m) for m in result.scalars().all()]

    async def list_library_tools(self, user_id: int = None, type_filter: str = None) -> List[Tool]:
        async with async_session_maker() as session:
            query = select(ToolModel).where(
                ToolModel.scope.in_(["public"])
            )
            if type_filter == "builtin":
                query = query.where(ToolModel.is_builtin == True)
            elif type_filter == "template":
                query = query.where(ToolModel.is_template == True)
            query = query.order_by(ToolModel.is_builtin.desc(), ToolModel.name)
            result = await session.execute(query)
            return [self._to_domain(m) for m in result.scalars().all()]

    async def list_user_tools(self, user_id: int) -> List[UserTool]:
        async with async_session_maker() as session:
            builtin_query = select(ToolModel).where(
                ToolModel.is_builtin == True
            )
            builtin_result = await session.execute(builtin_query)
            builtin_tools = {m.id: m for m in builtin_result.scalars().all()}

            private_query = select(ToolModel).where(
                ToolModel.user_id == user_id
            )
            private_result = await session.execute(private_query)
            private_tools = {m.id: m for m in private_result.scalars().all()}

            ut_query = select(UserToolModel).where(
                UserToolModel.user_id == user_id
            )
            ut_result = await session.execute(ut_query)
            ut_map = {ut.tool_id: ut for ut in ut_result.scalars().all()}

            imported_tool_ids = set()
            for tid in ut_map:
                if tid not in builtin_tools and tid not in private_tools:
                    imported_tool_ids.add(tid)

            imported_tools = {}
            if imported_tool_ids:
                imp_query = select(ToolModel).where(
                    ToolModel.id.in_(list(imported_tool_ids))
                )
                imp_result = await session.execute(imp_query)
                imported_tools = {m.id: m for m in imp_result.scalars().all()}

            result = []

            for tool_id, tool in sorted(builtin_tools.items(), key=lambda x: x[1].name):
                ut = ut_map.get(tool_id)
                result.append(UserTool(
                    id=str(tool_id),
                    user_id=str(user_id),
                    tool_id=str(tool_id),
                    tool_name=tool.name,
                    tool_display_name=tool.display_name,
                    tool_description=tool.description,
                    enabled=ut.enabled if ut else True,
                    is_builtin=True,
                    scope="public",
                    created_at=tool.created_at.isoformat() if tool.created_at else "",
                    updated_at=tool.updated_at.isoformat() if tool.updated_at else "",
                ))

            for tool_id, tool in sorted(private_tools.items(), key=lambda x: x[1].name):
                ut = ut_map.get(tool_id)
                result.append(UserTool(
                    id=str(tool_id),
                    user_id=str(user_id),
                    tool_id=str(tool_id),
                    tool_name=tool.name,
                    tool_display_name=tool.display_name,
                    tool_description=tool.description,
                    enabled=ut.enabled if ut else True,
                    is_builtin=False,
                    scope="private",
                    created_at=tool.created_at.isoformat() if tool.created_at else "",
                    updated_at=tool.updated_at.isoformat() if tool.updated_at else "",
                ))

            for tool_id, tool in sorted(imported_tools.items(), key=lambda x: x[1].name):
                ut = ut_map.get(tool_id)
                result.append(UserTool(
                    id=str(tool_id),
                    user_id=str(user_id),
                    tool_id=str(tool_id),
                    tool_name=tool.name,
                    tool_display_name=tool.display_name,
                    tool_description=tool.description,
                    enabled=ut.enabled if ut else True,
                    is_builtin=False,
                    scope=ut.scope if ut else "public",
                    created_at=tool.created_at.isoformat() if tool.created_at else "",
                    updated_at=tool.updated_at.isoformat() if tool.updated_at else "",
                ))

            return result

    async def get_user_enabled_tools(self, user_id: int) -> List[Tool]:
        async with async_session_maker() as session:
            builtin_result = await session.execute(
                select(ToolModel).where(ToolModel.is_builtin == True)
            )
            builtin_tools = {m.id: m for m in builtin_result.scalars().all()}

            private_result = await session.execute(
                select(ToolModel).where(ToolModel.user_id == user_id)
            )
            private_tools = {m.id: m for m in private_result.scalars().all()}

            ut_result = await session.execute(
                select(UserToolModel).where(
                    and_(UserToolModel.user_id == user_id,
                         UserToolModel.enabled == True)
                )
            )
            ut_map = {ut.tool_id: ut for ut in ut_result.scalars().all()}

            result = []

            for tool_id, tool in builtin_tools.items():
                ut = ut_map.get(tool_id)
                if ut is None:
                    result.append(self._to_domain(tool))
                elif ut.enabled:
                    tool.enabled = True
                    result.append(self._to_domain(tool))

            for tool_id, tool in private_tools.items():
                ut = ut_map.get(tool_id)
                if ut is None or ut.enabled:
                    result.append(self._to_domain(tool))

            imported_tool_ids = set(
                ut_map.keys()) - set(builtin_tools.keys()) - set(private_tools.keys())
            if imported_tool_ids:
                imp_result = await session.execute(
                    select(ToolModel).where(
                        ToolModel.id.in_(list(imported_tool_ids)))
                )
                for m in imp_result.scalars().all():
                    ut = ut_map.get(m.id)
                    if ut and ut.enabled:
                        result.append(self._to_domain(m))

            return result

    async def list_user_enabled_tool_ids(self, user_id: int) -> Tuple[List[int], List[int]]:
        tools = await self.get_user_enabled_tools(user_id)
        return [int(t.id) for t in tools], [t.name for t in tools]

    async def list_templates(self) -> List[Tool]:
        async with async_session_maker() as session:
            query = select(ToolModel).where(
                and_(ToolModel.is_template == True,
                     ToolModel.scope == "public")
            ).order_by(ToolModel.name)
            result = await session.execute(query)
            return [self._to_domain(m) for m in result.scalars().all()]

    async def import_templates(self, user_id: int, tool_ids: List[int]) -> int:
        count = 0
        async with async_session_maker() as session:
            for tid in tool_ids:
                existing = await session.execute(
                    select(UserToolModel).where(
                        and_(UserToolModel.user_id == user_id,
                             UserToolModel.tool_id == tid)
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                session.add(UserToolModel(
                    user_id=user_id, tool_id=tid, enabled=True,
                    created_at=now_iso(), updated_at=now_iso()
                ))
                count += 1
            await session.commit()
        return count

    async def toggle_user_tool(self, user_id: int, tool_id: int, enabled: bool) -> Optional[UserTool]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(UserToolModel).where(
                    and_(UserToolModel.user_id == user_id,
                         UserToolModel.tool_id == tool_id)
                )
            )
            ut = result.scalar_one_or_none()
            if not ut:
                ut = UserToolModel(
                    user_id=user_id, tool_id=tool_id, enabled=enabled,
                    created_at=now_iso(), updated_at=now_iso()
                )
                session.add(ut)
            else:
                ut.enabled = enabled
                ut.updated_at = now_iso()
            await session.commit()
            await session.refresh(ut)
            return self._user_tool_to_domain(ut)

    async def get_tool(self, tool_id: str) -> Optional[Tool]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ToolModel).where(ToolModel.id == int(tool_id))
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def get_tool_by_name(self, name: str) -> Optional[Tool]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ToolModel).where(ToolModel.name == name)
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def create_tool(
        self,
        name: str,
        code: str,
        display_name: str = None,
        description: str = None,
        parameters: Union[ToolParameters, dict] = None,
        config_schema: Union[ToolConfigSchema, dict] = None,
        enabled: bool = True,
        sandbox_only: bool = False,
        is_builtin: bool = False,
        user_id: int = None,
        scope: str = "public",
        is_template: bool = False,
    ) -> Optional[Tool]:
        params_json = _serialize_parameters(parameters)
        schema_json = _serialize_config_schema(config_schema)

        async with async_session_maker() as session:
            model = ToolModel(
                name=name,
                display_name=display_name,
                description=description,
                code=code,
                parameters=params_json,
                config_schema=schema_json,
                enabled=enabled,
                sandbox_only=sandbox_only,
                is_builtin=is_builtin,
                user_id=user_id,
                scope=scope,
                is_template=is_template,
                created_at=now_iso(),
                updated_at=now_iso(),
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def update_tool(
        self,
        tool_id: str,
        name: str = None,
        display_name: str = None,
        description: str = None,
        code: str = None,
        parameters: Union[ToolParameters, dict] = None,
        config_schema: Union[ToolConfigSchema, dict] = None,
        enabled: bool = None,
        sandbox_only: bool = None,
        is_builtin: bool = None,
        scope: str = None,
        is_template: bool = None,
    ) -> Optional[Tool]:
        params_json = _serialize_parameters(
            parameters) if parameters is not None else None
        schema_json = _serialize_config_schema(
            config_schema) if config_schema is not None else None

        async with async_session_maker() as session:
            result = await session.execute(
                select(ToolModel).where(ToolModel.id == int(tool_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None

            if name is not None:
                model.name = name
            if display_name is not None:
                model.display_name = display_name
            if description is not None:
                model.description = description
            if code is not None:
                model.code = code
            if params_json is not None:
                model.parameters = params_json
            if schema_json is not None:
                model.config_schema = schema_json
            if enabled is not None:
                model.enabled = enabled
            if sandbox_only is not None:
                model.sandbox_only = sandbox_only
            if is_builtin is not None:
                model.is_builtin = is_builtin
            if scope is not None:
                model.scope = scope
            if is_template is not None:
                model.is_template = is_template
            model.updated_at = now_iso()

            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def delete_tool(self, tool_id: str) -> bool:
        async with async_session_maker() as session:
            await session.execute(delete(UserToolModel).where(UserToolModel.tool_id == int(tool_id)))
            result = await session.execute(
                delete(ToolModel).where(ToolModel.id == int(tool_id))
            )
            await session.commit()
            return result.rowcount > 0

    async def count_tools(self) -> int:
        async with async_session_maker() as session:
            result = await session.execute(
                select(func.count(ToolModel.id))
            )
            return result.scalar() or 0

    def _to_domain(self, model: ToolModel) -> Tool:
        parameters = None
        if model.parameters:
            try:
                param_dict = json.loads(model.parameters)
                if "required" not in param_dict or param_dict["required"] is None:
                    param_dict["required"] = []
                parameters = ToolParameters(**param_dict)
            except Exception as e:
                logger.warning(f"Failed to parse parameters: {e}")

        config_schema = None
        if model.config_schema:
            try:
                schema_dict = json.loads(model.config_schema)
                config_schema = ToolConfigSchema(**schema_dict)
            except Exception as e:
                logger.warning(f"Failed to parse config_schema: {e}")

        return Tool(
            id=str(model.id),
            name=model.name,
            display_name=model.display_name,
            description=model.description,
            code=model.code,
            parameters=parameters,
            config_schema=config_schema,
            enabled=bool(model.enabled),
            sandbox_only=bool(model.sandbox_only),
            is_builtin=bool(model.is_builtin),
            user_id=str(model.user_id) if model.user_id else None,
            scope=model.scope or "public",
            is_template=bool(model.is_template),
            team_id=str(model.team_id) if model.team_id else None,
            created_at=model.created_at.isoformat() if model.created_at else None,
            updated_at=model.updated_at.isoformat() if model.updated_at else None,
        )

    def _user_tool_to_domain(self, ut: UserToolModel) -> UserTool:
        return UserTool(
            id=str(ut.id),
            user_id=str(ut.user_id),
            tool_id=str(ut.tool_id),
            enabled=bool(ut.enabled),
            created_at=ut.created_at.isoformat() if ut.created_at else "",
            updated_at=ut.updated_at.isoformat() if ut.updated_at else "",
        )
