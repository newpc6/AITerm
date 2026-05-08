import logging
from typing import List, Optional

from sqlalchemy import select, delete, and_
from app.db import async_session_maker
from app.db.scheduler import ScheduledTaskModel, ScheduledTaskLogModel
from app.db.agent import AgentModel
from app.db.user import UserModel
from app.models.scheduler import ScheduledTask, ScheduledTaskLog
from app.utils import now_iso

logger = logging.getLogger(__name__)


class SchedulerRepository:

    async def list_tasks(self, user_id: int, is_admin: bool = False) -> List[ScheduledTask]:
        async with async_session_maker() as session:
            if is_admin:
                result = await session.execute(
                    select(ScheduledTaskModel).order_by(
                        ScheduledTaskModel.name)
                )
            else:
                result = await session.execute(
                    select(ScheduledTaskModel).where(
                        ScheduledTaskModel.user_id == user_id).order_by(ScheduledTaskModel.name)
                )
            return await self._to_task_list(result.scalars().all(), session)

    async def get(self, task_id: str) -> Optional[ScheduledTask]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ScheduledTaskModel).where(
                    ScheduledTaskModel.id == int(task_id))
            )
            m = result.scalar_one_or_none()
            if not m:
                return None
            tasks = await self._to_task_list([m], session)
            return tasks[0] if tasks else None

    async def create(self, user_id: int, **kwargs) -> ScheduledTask:
        now = now_iso()
        async with async_session_maker() as session:
            model = ScheduledTaskModel(
                user_id=user_id,
                name=kwargs.get("name", ""),
                description=kwargs.get("description", ""),
                agent_id=int(kwargs["agent_id"]) if kwargs.get(
                    "agent_id") else None,
                input_message=kwargs.get("input_message", ""),
                enabled=1 if kwargs.get("enabled", True) else 0,
                cron_expression=kwargs.get("cron_expression", "0 8 * * *"),
                node_id=int(kwargs["node_id"]) if kwargs.get(
                    "node_id") else None,
                max_retries=kwargs.get("max_retries", 0),
                timeout_seconds=kwargs.get("timeout_seconds", 300),
                created_at=now, updated_at=now,
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            tasks = await self._to_task_list([model], session)
            return tasks[0] if tasks else None

    async def update(self, task_id: str, **kwargs) -> Optional[ScheduledTask]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ScheduledTaskModel).where(
                    ScheduledTaskModel.id == int(task_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            for key, value in kwargs.items():
                if value is None:
                    continue
                if key == "agent_id" and value:
                    setattr(model, key, int(value))
                elif key == "node_id" and value:
                    setattr(model, key, int(value))
                elif key == "enabled":
                    setattr(model, key, 1 if value else 0)
                elif hasattr(model, key):
                    setattr(model, key, value)
            model.updated_at = now_iso()
            await session.commit()
            await session.refresh(model)
            tasks = await self._to_task_list([model], session)
            return tasks[0] if tasks else None

    async def delete(self, task_id: str) -> bool:
        async with async_session_maker() as session:
            await session.execute(delete(ScheduledTaskLogModel).where(ScheduledTaskLogModel.task_id == int(task_id)))
            result = await session.execute(delete(ScheduledTaskModel).where(ScheduledTaskModel.id == int(task_id)))
            await session.commit()
            return result.rowcount > 0

    async def get_due_tasks(self) -> List[ScheduledTask]:
        """Return enabled tasks whose next_run_at <= now or not set."""
        now = now_iso()
        async with async_session_maker() as session:
            result = await session.execute(
                select(ScheduledTaskModel).where(
                    and_(ScheduledTaskModel.enabled == 1)
                )
            )
            due = []
            for m in result.scalars().all():
                if m.next_run_at and m.next_run_at <= now:
                    due.append(m)
                elif not m.next_run_at:
                    due.append(m)
            return await self._to_task_list(due, session)

    async def mark_run(self, task_id: int, last_result: str, next_run_at: str):
        async with async_session_maker() as session:
            result = await session.execute(
                select(ScheduledTaskModel).where(
                    ScheduledTaskModel.id == task_id)
            )
            m = result.scalar_one_or_none()
            if m:
                m.last_run_at = now_iso()
                m.last_result = last_result
                m.next_run_at = next_run_at
                m.updated_at = now_iso()
                await session.commit()

    async def add_log(self, task_id: int, status: str, output: str = "", error: str = "", started_at: str = None, finished_at: str = None) -> ScheduledTaskLog:
        now = now_iso()
        async with async_session_maker() as session:
            log = ScheduledTaskLogModel(
                task_id=task_id, status=status, output=output, error=error,
                started_at=started_at or now, finished_at=finished_at, created_at=now,
            )
            session.add(log)
            await session.commit()
            await session.refresh(log)
        return ScheduledTaskLog(id=str(log.id), task_id=str(log.task_id), status=log.status, output=log.output, error=log.error, started_at=log.started_at, finished_at=log.finished_at, created_at=log.created_at)

    async def list_logs(self, task_id: str, limit: int = 20) -> List[ScheduledTaskLog]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ScheduledTaskLogModel).where(ScheduledTaskLogModel.task_id == int(
                    task_id)).order_by(ScheduledTaskLogModel.id.desc()).limit(limit)
            )
            return [ScheduledTaskLog(id=str(m.id), task_id=str(m.task_id), status=m.status, output=m.output, error=m.error, started_at=m.started_at, finished_at=m.finished_at, created_at=m.created_at) for m in result.scalars().all()]

    async def _to_task_list(self, models, session) -> List[ScheduledTask]:
        agent_ids = set()
        user_ids = set()
        for m in models:
            if m.agent_id:
                agent_ids.add(m.agent_id)
            user_ids.add(m.user_id)
        agent_map = {}
        if agent_ids:
            ar = await session.execute(select(AgentModel).where(AgentModel.id.in_(list(agent_ids))))
            agent_map = {a.id: a.name for a in ar.scalars().all()}
        user_map = {}
        if user_ids:
            ur = await session.execute(select(UserModel).where(UserModel.id.in_(list(user_ids))))
            user_map = {u.id: u.username for u in ur.scalars().all()}
        result = []
        for m in models:
            result.append(ScheduledTask(
                id=str(m.id), user_id=str(m.user_id),
                username=user_map.get(m.user_id, ""),
                name=m.name,
                description=m.description or "", agent_id=str(m.agent_id) if m.agent_id else None,
                agent_name=agent_map.get(m.agent_id, ""), input_message=m.input_message,
                enabled=bool(m.enabled), cron_expression=m.cron_expression,
                node_id=str(m.node_id) if m.node_id else None,
                max_retries=m.max_retries or 0, timeout_seconds=m.timeout_seconds or 300,
                last_run_at=m.last_run_at, last_result=m.last_result, next_run_at=m.next_run_at,
                created_at=m.created_at or "", updated_at=m.updated_at or "",
            ))
        return result
