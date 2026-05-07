import json
import logging
from typing import List, Optional

from sqlalchemy import select, delete, func, and_

from app.db import async_session_maker
from app.db.agent import AgentModel
from app.db.model_setting import ModelConfigModel
from app.models.agent import Agent
from app.utils import now_iso

logger = logging.getLogger(__name__)


class AgentRepository:

    async def list_visible(self, user_id: int) -> List[Agent]:
        async with async_session_maker() as session:
            query = select(AgentModel).where(
                AgentModel.user_id == user_id
            )
            result = await session.execute(query.order_by(AgentModel.name))
            agents = list(result.scalars().all())

            public_result = await session.execute(
                select(AgentModel).where(
                    and_(AgentModel.is_public == True, AgentModel.user_id != user_id)
                ).order_by(AgentModel.name)
            )
            agents.extend(public_result.scalars().all())

            return await self._to_domain_list(agents, session)

    async def list_by_user(self, user_id: int) -> List[Agent]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(AgentModel).where(AgentModel.user_id == user_id).order_by(AgentModel.name)
            )
            return await self._to_domain_list(result.scalars().all(), session)

    async def list_public_templates(self) -> List[Agent]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(AgentModel).where(
                    and_(AgentModel.is_public == True, AgentModel.is_template == True)
                ).order_by(AgentModel.name)
            )
            return await self._to_domain_list(result.scalars().all(), session)

    async def get(self, agent_id: str) -> Optional[Agent]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(AgentModel).where(AgentModel.id == int(agent_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            agents = await self._to_domain_list([model], session)
            return agents[0] if agents else None

    async def create(self, user_id: int, **kwargs) -> Agent:
        now = now_iso()
        async with async_session_maker() as session:
            model = AgentModel(
                user_id=user_id,
                name=kwargs.get("name", ""),
                description=kwargs.get("description", ""),
                icon=kwargs.get("icon", "robot"),
                model_id=int(kwargs["model_id"]) if kwargs.get("model_id") else None,
                skill_ids=json.dumps(kwargs.get("skill_ids", [])),
                system_prompt=kwargs.get("system_prompt", ""),
                temperature=kwargs.get("temperature", 0.7),
                max_iterations=kwargs.get("max_iterations", 10),
                extra_body_json=kwargs.get("extra_body_json", "{}"),
                is_default=1 if kwargs.get("is_default") else 0,
                is_public=1 if kwargs.get("is_public") else 0,
                is_template=1 if kwargs.get("is_template") else 0,
                scope=kwargs.get("scope", "private"),
                created_at=now,
                updated_at=now,
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            agents = await self._to_domain_list([model], session)
            return agents[0] if agents else None

    async def update(self, agent_id: str, **kwargs) -> Optional[Agent]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(AgentModel).where(AgentModel.id == int(agent_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None

            for key, value in kwargs.items():
                if value is None:
                    continue
                if key == "model_id" and value:
                    setattr(model, key, int(value))
                elif key in ("is_default", "is_public", "is_template"):
                    setattr(model, key, 1 if value else 0)
                elif key == "skill_ids":
                    setattr(model, key, json.dumps(value))
                elif hasattr(model, key):
                    setattr(model, key, value)

            model.updated_at = now_iso()
            await session.commit()
            await session.refresh(model)
            agents = await self._to_domain_list([model], session)
            return agents[0] if agents else None

    async def delete(self, agent_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(AgentModel).where(AgentModel.id == int(agent_id))
            )
            await session.commit()
            return result.rowcount > 0

    async def set_default(self, user_id: int, agent_id: str) -> None:
        async with async_session_maker() as session:
            await session.execute(
                select(AgentModel).where(AgentModel.user_id == user_id)
            )
            result = await session.execute(
                select(AgentModel).where(
                    and_(AgentModel.user_id == user_id, AgentModel.is_default == True)
                )
            )
            for m in result.scalars().all():
                m.is_default = 0
                m.updated_at = now_iso()

            agent_result = await session.execute(
                select(AgentModel).where(AgentModel.id == int(agent_id))
            )
            agent = agent_result.scalar_one_or_none()
            if agent:
                agent.is_default = 1
                agent.updated_at = now_iso()

            await session.commit()

    async def clone(self, user_id: int, agent_id: str) -> Optional[Agent]:
        source = await self.get(agent_id)
        if not source:
            return None
        return await self.create(
            user_id=user_id,
            name=f"{source.name} (副本)",
            description=source.description,
            icon=source.icon,
            model_id=source.model_id,
            skill_ids=source.skill_ids,
            system_prompt=source.system_prompt,
            temperature=source.temperature,
            max_iterations=source.max_iterations,
            extra_body_json=source.extra_body_json,
            is_public=False,
            is_template=False,
            scope="private",
        )

    async def _to_domain_list(self, models: List[AgentModel], session) -> List[Agent]:
        model_ids = set()
        for m in models:
            if m.model_id:
                model_ids.add(m.model_id)

        model_map = {}
        if model_ids:
            mc_result = await session.execute(
                select(ModelConfigModel).where(ModelConfigModel.id.in_(list(model_ids)))
            )
            model_map = {mc.id: mc.name for mc in mc_result.scalars().all()}

        result = []
        for m in models:
            skill_ids = []
            try:
                skill_ids = json.loads(m.skill_ids) if m.skill_ids else []
            except Exception:
                pass

            result.append(Agent(
                id=str(m.id),
                user_id=str(m.user_id),
                name=m.name,
                description=m.description or "",
                icon=m.icon or "robot",
                model_id=str(m.model_id) if m.model_id else None,
                model_name=model_map.get(m.model_id, ""),
                skill_ids=skill_ids,
                system_prompt=m.system_prompt or "",
                temperature=m.temperature or 0.7,
                max_iterations=m.max_iterations or 10,
                extra_body_json=m.extra_body_json or "{}",
                is_default=bool(m.is_default),
                is_public=bool(m.is_public),
                is_template=bool(m.is_template),
                scope=m.scope or "private",
                team_id=str(m.team_id) if m.team_id else None,
                created_at=m.created_at or "",
                updated_at=m.updated_at or "",
            ))

        return result
