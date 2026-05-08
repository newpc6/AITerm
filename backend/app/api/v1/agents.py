import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models.common import Response
from app.models.agent import Agent, AgentCreate, AgentUpdate, AgentWorkbenchRequest
from app.repositories.agent import AgentRepository
from app.api.deps import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])
repo = AgentRepository()


@router.get("")
async def list_agents(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    agents = await repo.list_visible(user_id=int(user.id))
    return Response(data=[a.model_dump() for a in agents])


@router.post("")
async def create_agent(payload: AgentCreate, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    agent = await repo.create(user_id=int(user.id), **payload.model_dump())
    return Response(data=agent.model_dump())


@router.get("/{agent_id}")
async def get_agent(agent_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return Response(data=agent.model_dump())


@router.put("/{agent_id}")
async def update_agent(agent_id: str, payload: AgentUpdate, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    existing = await repo.get(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agent not found")
    if str(existing.user_id) != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Cannot edit this agent")
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    agent = await repo.update(agent_id, **update_data)
    return Response(data=agent.model_dump() if agent else None)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    existing = await repo.get(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agent not found")
    if str(existing.user_id) != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Cannot delete this agent")
    await repo.delete(agent_id)
    return Response(data={"status": "deleted"})


@router.post("/{agent_id}/clone")
async def clone_agent(agent_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    agent = await repo.clone(user_id=int(user.id), agent_id=agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return Response(data=agent.model_dump())


@router.post("/{agent_id}/default")
async def set_default_agent(agent_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    await repo.set_default(user_id=int(user.id), agent_id=agent_id)
    return Response(data={"status": "ok"})


@router.post("/workbench/run")
async def workbench_run(payload: AgentWorkbenchRequest, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)

    from app.services.sandbox_manager import SandboxManager
    from app.services.tool_service import ToolService
    from app.services.llm import LLMClient
    from app.repositories.model_setting import ModelConfigRepository

    async def event_generator():
        for agent_id_str in payload.agent_ids:
            agent = await repo.get(agent_id_str)
            if not agent:
                yield {"event": "agent.error", "data": json.dumps({"agent_id": agent_id_str, "error": "Agent not found"})}
                continue

            yield {"event": "agent.start", "data": json.dumps({"agent_id": agent_id_str, "agent_name": agent.name})}

            try:
                sandbox = SandboxManager()
                tool_service = ToolService(sandbox_paths=sandbox.base_paths)
                user_tools = await tool_service.tool_repo.get_user_enabled_tools(user_id=int(user.id))
                openai_tools = []
                for t in user_tools:
                    params = t.parameters.model_dump() if t.parameters else {"type": "object", "properties": {}, "required": []}
                    openai_tools.append({
                        "type": "function",
                        "function": {"name": t.name, "description": t.description or t.display_name or t.name, "parameters": params}
                    })

                model_repo = ModelConfigRepository()
                model_config = None
                if agent.model_id:
                    model_config = await model_repo.get_model(agent.model_id)
                if not model_config:
                    model_config = await model_repo.get_default_model()

                if not model_config:
                    yield {"event": "agent.error", "data": json.dumps({"agent_id": agent_id_str, "error": "No model configured"})}
                    yield {"event": "agent.done", "data": json.dumps({"agent_id": agent_id_str, "reply": "No model available"})}
                    continue

                llm_client = LLMClient(model_config)
                messages = [{"role": "system", "content": agent.system_prompt}, {"role": "user", "content": payload.message}]

                full_content = ""
                async for chunk in llm_client.chat_with_tools_stream(messages, openai_tools):
                    if chunk["type"] == "content":
                        full_content += chunk.get("delta", "")
                        yield {"event": "agent.delta", "data": json.dumps({"agent_id": agent_id_str, "delta": chunk.get("delta", "")})}
                    elif chunk["type"] == "reasoning":
                        yield {"event": "agent.reasoning", "data": json.dumps({"agent_id": agent_id_str, "delta": chunk.get("delta", "")})}
                    elif chunk["type"] == "done":
                        if chunk.get("content"):
                            full_content = chunk.get("content", full_content)
                        if chunk.get("tool_calls"):
                            for tc in chunk["tool_calls"]:
                                yield {"event": "agent.tool_call", "data": json.dumps({"agent_id": agent_id_str, "tool": tc.get("name", ""), "args": tc.get("arguments", "")})}
                    elif chunk["type"] == "tool_start":
                        yield {"event": "agent.tool_call", "data": json.dumps({"agent_id": agent_id_str, "tool": chunk.get("tool", ""), "args": chunk.get("input", {})})}

                yield {"event": "agent.done", "data": json.dumps({"agent_id": agent_id_str, "reply": full_content})}

            except Exception as e:
                logger.error(f"Agent {agent_id_str} workbench error: {e}")
                yield {"event": "agent.error", "data": json.dumps({"agent_id": agent_id_str, "error": str(e)})}
                yield {"event": "agent.done", "data": json.dumps({"agent_id": agent_id_str, "reply": "", "error": str(e)})}

    return EventSourceResponse(event_generator())
