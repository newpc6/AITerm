import asyncio
import logging
from datetime import datetime, timezone

from app.repositories.scheduler import SchedulerRepository

logger = logging.getLogger(__name__)
repo = SchedulerRepository()
_scheduler_running = False


async def run_single_task(task_id: int):
    task = await repo.get(str(task_id))
    if not task:
        return
    log = await repo.add_log(task_id, "running")
    try:
        from app.repositories.agent import AgentRepository
        from app.repositories.model_setting import ModelConfigRepository
        from app.services.llm import LLMClient

        agent_repo = AgentRepository()
        model_repo = ModelConfigRepository()
        agent = await agent_repo.get(str(task.agent_id)) if task.agent_id else None
        model = await model_repo.get_model(agent.model_id) if agent and agent.model_id else await model_repo.get_default_model()
        if not model:
            await repo.mark_run(task_id, "failed: no model", compute_next_run(task.cron_expression))
            await repo.add_log(task_id, "failed", error="No model configured", started_at=log.started_at, finished_at=_now())
            return

        sandbox = __import__('app.services.sandbox_manager', fromlist=['SandboxManager']).SandboxManager()
        tool_service = __import__('app.services.tool_service', fromlist=['ToolService']).ToolService(sandbox_paths=sandbox.base_paths)
        user_tools = await tool_service.tool_repo.get_user_enabled_tools(user_id=int(task.user_id))
        openai_tools = []
        for t in user_tools:
            params = t.parameters.model_dump() if t.parameters else {"type": "object", "properties": {}, "required": []}
            openai_tools.append({"type": "function", "function": {"name": t.name, "description": t.description or t.name, "parameters": params}})

        messages = [{"role": "system", "content": agent.system_prompt if agent else ""}, {"role": "user", "content": task.input_message}]
        llm = LLMClient(model)
        full_content = ""
        async for chunk in llm.chat_with_tools_stream(messages, openai_tools):
            if chunk["type"] == "content":
                full_content += chunk.get("delta", "")
            elif chunk["type"] == "done":
                if chunk.get("content"):
                    full_content = chunk.get("content", full_content)

        await repo.mark_run(task_id, "success", compute_next_run(task.cron_expression))
        await repo.add_log(task_id, "success", output=full_content[:5000], started_at=log.started_at, finished_at=_now())
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        await repo.mark_run(task_id, f"failed: {str(e)[:50]}", compute_next_run(task.cron_expression))
        await repo.add_log(task_id, "failed", error=str(e)[:2000], started_at=log.started_at, finished_at=_now())


def compute_next_run(cron: str) -> str:
    try:
        from croniter import croniter
        return croniter(cron, datetime.now(timezone.utc)).get_next(datetime).isoformat()
    except Exception:
        return _now()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def start_scheduler(interval_seconds: int = 30):
    global _scheduler_running
    _scheduler_running = True
    logger.info(f"Scheduler started, scanning every {interval_seconds}s")
    while _scheduler_running:
        try:
            tasks = await repo.get_due_tasks()
            for task in tasks:
                asyncio.create_task(run_single_task(int(task.id)))
        except Exception as e:
            logger.error(f"Scheduler scan error: {e}")
        await asyncio.sleep(interval_seconds)


def stop_scheduler():
    global _scheduler_running
    _scheduler_running = False
