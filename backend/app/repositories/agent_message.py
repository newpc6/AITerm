import json
import logging
from typing import List, Optional, Tuple

from sqlalchemy import select, desc

from app.db import async_session_maker
from app.db.agent_message import AgentMessageModel
from app.models.agent import AgentMessage
from app.utils import now_iso

logger = logging.getLogger(__name__)


class AgentMessageRepository:

    async def add_message(self, agent_id: int, user_id: int, role: str, content: str, tool_calls: list = None) -> AgentMessage:
        now = now_iso()
        async with async_session_maker() as session:
            model = AgentMessageModel(
                agent_id=agent_id, user_id=user_id, role=role,
                content=content,
                tool_calls_json=json.dumps(tool_calls or [], ensure_ascii=False),
                created_at=now,
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def get_messages(self, agent_id: int, before_id: int = None, limit: int = 20) -> Tuple[List[AgentMessage], bool]:
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

            messages = [self._to_domain(m) for m in models]
            messages.reverse()
            return messages, has_more

    async def get_latest(self, agent_id: int, limit: int = 20) -> List[AgentMessage]:
        messages, _ = await self.get_messages(agent_id, before_id=None, limit=limit)
        return messages

    def _to_domain(self, m: AgentMessageModel) -> AgentMessage:
        return AgentMessage(
            id=str(m.id),
            agent_id=str(m.agent_id),
            user_id=str(m.user_id),
            role=m.role,
            content=m.content or "",
            tool_calls_json=m.tool_calls_json or "[]",
            created_at=m.created_at or "",
        )
