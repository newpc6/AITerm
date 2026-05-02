import json
from typing import List, Optional
from sqlalchemy import select, delete, func

from app.db import async_session_maker
from app.db.tool import ToolModel
from app.models.tool import Tool, ToolParameters, ToolConfigSchema


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
        parameters: ToolParameters = None,
        config_schema: ToolConfigSchema = None,
        enabled: bool = True
    ) -> Optional[Tool]:
        async with async_session_maker() as session:
            model = ToolModel(
                name=name,
                display_name=display_name,
                description=description,
                code=code,
                parameters=parameters.model_dump_json() if parameters else None,
                config_schema=config_schema.model_dump_json() if config_schema else None,
                enabled=enabled
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
        parameters: ToolParameters = None,
        config_schema: ToolConfigSchema = None,
        enabled: bool = None
    ) -> Optional[Tool]:
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
            if parameters is not None:
                model.parameters = parameters.model_dump_json()
            if config_schema is not None:
                model.config_schema = config_schema.model_dump_json()
            if enabled is not None:
                model.enabled = enabled

            await session.commit()
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
                parameters = ToolParameters(**json.loads(model.parameters))
            except:
                pass

        config_schema = None
        if model.config_schema:
            try:
                config_schema = ToolConfigSchema(**json.loads(model.config_schema))
            except:
                pass

        return Tool(
            id=str(model.id),
            name=model.name,
            display_name=model.display_name,
            description=model.description,
            code=model.code,
            parameters=parameters,
            config_schema=config_schema,
            enabled=model.enabled,
            created_at=model.created_at.isoformat() if model.created_at else None,
            updated_at=model.updated_at.isoformat() if model.updated_at else None
        )
