import json
from typing import List, Optional, Union
from sqlalchemy import select, delete, func

from app.db import async_session_maker
from app.db.tool import ToolModel
from app.models.tool import Tool, ToolParameters, ToolConfigSchema


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
            query = select(ToolModel).order_by(ToolModel.created_at.desc())
            if enabled_only:
                query = query.where(ToolModel.enabled == True)
            result = await session.execute(query)
            models = result.scalars().all()
            return [self._to_domain(m) for m in models]

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
        sandbox_only: bool = False
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
                sandbox_only=sandbox_only
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
        sandbox_only: bool = None
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

            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def delete_tool(self, tool_id: str) -> bool:
        async with async_session_maker() as session:
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
                import logging
                logging.getLogger(__name__).warning(
                    f"Failed to parse parameters: {e}")

        config_schema = None
        if model.config_schema:
            try:
                schema_dict = json.loads(model.config_schema)
                config_schema = ToolConfigSchema(**schema_dict)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"Failed to parse config_schema: {e}")

        return Tool(
            id=str(model.id),
            name=model.name,
            display_name=model.display_name,
            description=model.description,
            code=model.code,
            parameters=parameters,
            config_schema=config_schema,
            enabled=model.enabled,
            sandbox_only=model.sandbox_only,
            created_at=model.created_at.isoformat() if model.created_at else None,
            updated_at=model.updated_at.isoformat() if model.updated_at else None
        )
