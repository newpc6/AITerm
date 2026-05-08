import json
import logging
from typing import List, Tuple

from sqlalchemy import select, desc, func

from app.db import async_session_maker
from app.db.agent_message import AgentMessageModel, AgentMessagePartModel
from app.models.agent import AgentMessage
from app.utils import now_iso

logger = logging.getLogger(__name__)


class AgentMessageRepository:

    async def add_message(self, agent_id: int, user_id: int, role: str, content: str = "", full_input: str = None) -> AgentMessage:
        now = now_iso()
        async with async_session_maker() as session:
            model = AgentMessageModel(
                agent_id=agent_id, user_id=user_id, role=role,
                content=content, full_input=full_input,
                created_at=now,
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model, [])

    async def add_part(self, message_id: int, seq: int, content: dict) -> None:
        now = now_iso()
        async with async_session_maker() as session:
            part = AgentMessagePartModel(
                message_id=message_id, seq=seq,
                content=json.dumps(content, ensure_ascii=False),
                created_at=now,
            )
            session.add(part)
            await session.commit()

    async def update_message_content(self, message_id: int, content: str) -> None:
        async with async_session_maker() as session:
            result = await session.execute(
                select(AgentMessageModel).where(AgentMessageModel.id == message_id)
            )
            model = result.scalar_one_or_none()
            if model:
                model.content = content
                await session.commit()

    async def get_messages(self, agent_id: int, before_id: int = None, limit: int = 6) -> Tuple[List[AgentMessage], bool]:
        async with async_session_maker() as session:
            query = select(AgentMessageModel).where(AgentMessageModel.agent_id == agent_id)
            if before_id:
                query = query.where(AgentMessageModel.id < before_id)
            query = query.order_by(desc(AgentMessageModel.id)).limit(limit + 1)
            result = await session.execute(query)
            models = result.scalars().all()

            has_more = len(models) > limit
            if has_more:
                models = models[:limit]

            messages = []
            for m in models:
                parts_result = await session.execute(
                    select(AgentMessagePartModel)
                    .where(AgentMessagePartModel.message_id == m.id)
                    .order_by(AgentMessagePartModel.seq)
                )
                parts = parts_result.scalars().all()
                messages.append(self._to_domain(m, parts))

            messages.reverse()
            return messages, has_more

    async def get_latest(self, agent_id: int, limit: int = 20) -> List[AgentMessage]:
        messages, _ = await self.get_messages(agent_id, before_id=None, limit=limit)
        return messages

    def _to_domain(self, m: AgentMessageModel, parts: list) -> AgentMessage:
        def parse_part(p):
            try:
                return json.loads(p.content)
            except Exception:
                return {}
        return AgentMessage(
            id=str(m.id),
            agent_id=str(m.agent_id),
            user_id=str(m.user_id),
            role=m.role,
            content=m.content or "",
            full_input=m.full_input,
            parts=[parse_part(p) for p in parts],
            created_at=m.created_at or "",
        )
