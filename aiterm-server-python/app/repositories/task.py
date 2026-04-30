import json
from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy import select, delete, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import ITaskRepository
from app.models import Task, TaskStep, TaskStatus, TaskStepStatus
from app.db import async_session_maker
from app.db.task import TaskModel


class TaskRepository(ITaskRepository):
    async def list_tasks(self, page: int = 1, page_size: int = 20) -> Tuple[List[Task], int]:
        async with async_session_maker() as session:
            count_result = await session.execute(
                select(func.count(TaskModel.id))
            )
            total = count_result.scalar() or 0

            offset = (page - 1) * page_size
            result = await session.execute(
                select(TaskModel)
                .order_by(desc(TaskModel.created_at))
                .offset(offset)
                .limit(page_size)
            )
            models = result.scalars().all()
            return [self._to_domain(m) for m in models], total

    async def get_task(self, task_id: str) -> Optional[Task]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(TaskModel).where(TaskModel.id == int(task_id))
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def create_task(self, task: Task) -> Task:
        async with async_session_maker() as session:
            now = datetime.utcnow().isoformat()
            model = TaskModel(
                title=task.title,
                status=task.status.value if isinstance(task.status, TaskStatus) else task.status,
                progress=task.progress,
                conversation_id=int(task.conversation_id),
                node_id=int(task.node_id),
                model_id=int(task.model_id) if task.model_id else None,
                model_name=task.model_name,
                request=task.request,
                pending_command=task.pending_command,
                risk_reason=task.risk_reason,
                summary=task.summary,
                steps_json=json.dumps([s.model_dump() for s in task.steps]),
                final_result=task.final_result or "",
                input_question=task.input_question,
                input_type=task.input_type,
                input_options_json=json.dumps(task.input_options) if task.input_options else "[]",
                input_placeholder=task.input_placeholder,
                user_input=task.user_input,
                created_at=now,
                updated_at=now
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def update_task(self, task_id: str, task: Task) -> Optional[Task]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(TaskModel).where(TaskModel.id == int(task_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            
            model.title = task.title
            model.status = task.status.value if isinstance(task.status, TaskStatus) else task.status
            model.progress = task.progress
            model.model_id = int(task.model_id) if task.model_id else None
            model.model_name = task.model_name
            model.pending_command = task.pending_command
            model.risk_reason = task.risk_reason
            model.summary = task.summary
            model.steps_json = json.dumps([s.model_dump() for s in task.steps])
            model.final_result = task.final_result or ""
            model.input_question = task.input_question
            model.input_type = task.input_type
            model.input_options_json = json.dumps(task.input_options) if task.input_options else "[]"
            model.input_placeholder = task.input_placeholder
            model.user_input = task.user_input
            model.updated_at = datetime.utcnow().isoformat()
            
            await session.commit()
            return self._to_domain(model)

    async def delete_task(self, task_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(TaskModel).where(TaskModel.id == int(task_id))
            )
            await session.commit()
            return result.rowcount > 0

    async def get_latest_task_by_conversation(self, conversation_id: str) -> Optional[Task]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(TaskModel)
                .where(TaskModel.conversation_id == int(conversation_id))
                .order_by(desc(TaskModel.created_at))
                .limit(1)
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    def _to_domain(self, model: TaskModel) -> Task:
        steps = []
        try:
            steps_data = json.loads(model.steps_json) if model.steps_json else []
            for s in steps_data:
                steps.append(TaskStep(
                    index=s.get("index", 0),
                    title=s.get("title", ""),
                    status=TaskStepStatus(s.get("status", "pending")),
                    command=s.get("command", ""),
                    result_output=s.get("result_output"),
                    repair_count=s.get("repair_count", 0),
                    original_command=s.get("original_command"),
                    first_failure_output=s.get("first_failure_output"),
                    repaired_output=s.get("repaired_output"),
                    last_error=s.get("last_error"),
                    repair_reason=s.get("repair_reason"),
                    repair_suggestion=s.get("repair_suggestion"),
                    repaired_command=s.get("repaired_command")
                ))
        except:
            pass

        input_options = []
        try:
            input_options = json.loads(model.input_options_json) if model.input_options_json else []
        except:
            pass

        return Task(
            id=str(model.id),
            title=model.title,
            status=TaskStatus(model.status) if model.status else TaskStatus.PENDING,
            progress=model.progress,
            conversation_id=str(model.conversation_id),
            node_id=str(model.node_id),
            model_id=str(model.model_id) if model.model_id else None,
            model_name=model.model_name,
            request=model.request,
            pending_command=model.pending_command,
            risk_reason=model.risk_reason,
            summary=model.summary,
            steps=steps,
            final_result=model.final_result,
            input_question=model.input_question,
            input_type=model.input_type,
            input_options=input_options,
            input_placeholder=model.input_placeholder,
            user_input=model.user_input,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
