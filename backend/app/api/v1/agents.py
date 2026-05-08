import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models.common import Response
from app.models.agent import Agent, AgentCreate, AgentUpdate, AgentWorkbenchRequest, AgentMessage, AgentMessagesResponse, AgentReview
from app.repositories.agent import AgentRepository
from app.repositories.agent_message import AgentMessageRepository
from app.repositories.skill import SkillRepository
from app.api.deps import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])
repo = AgentRepository()


async def _build_agent_system_prompt(agent: Agent) -> str:
    skill_repo = SkillRepository()
    parts = []

    if agent.system_prompt and agent.system_prompt.strip():
        parts.append(agent.system_prompt.strip())

    if agent.skill_ids:
        for sid in agent.skill_ids:
            skill = await skill_repo.get(str(sid))
            if not skill:
                continue
            section = f"## {skill.display_name or skill.name}"
            if skill.description and skill.description.strip():
                section += f"\n{skill.description.strip()}"
            if skill.system_prompt and skill.system_prompt.strip():
                section += f"\n\n{skill.system_prompt.strip()}"
            parts.append(section)

    if parts:
        return "\n\n".join(parts)

    from app.config import get_settings
    settings = get_settings()
    return settings.llm.chat_system_prompt


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
    update_data = {k: v for k, v in payload.model_dump().items()
                   if v is not None}
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


@router.post("/{agent_id}/submit")
async def submit_agent(agent_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    existing = await repo.get(agent_id)
    if not existing or str(existing.user_id) != user.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    await repo.submit_review(agent_id)
    return Response(data={"status": "submitted"})


@router.post("/{agent_id}/withdraw")
async def withdraw_agent(agent_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    existing = await repo.get(agent_id)
    if not existing or str(existing.user_id) != user.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    await repo.withdraw(agent_id)
    return Response(data={"status": "withdrawn"})


@router.post("/{agent_id}/review")
async def review_agent(agent_id: str, payload: AgentReview, admin=Depends(require_admin)):
    agent = await repo.review(agent_id, reviewer_id=int(admin.id), approved=payload.approved, comment=payload.comment)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return Response(data=agent.model_dump())


@router.post("/{agent_id}/install")
async def install_agent(agent_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    await repo.install(user_id=int(user.id), agent_id=int(agent_id))
    return Response(data={"status": "installed"})


@router.delete("/{agent_id}/uninstall")
async def uninstall_agent(agent_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    await repo.uninstall(user_id=int(user.id), agent_id=int(agent_id))
    return Response(data={"status": "uninstalled"})


@router.post("/workbench/run")
async def workbench_run(payload: AgentWorkbenchRequest, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)

    from app.services.sandbox_manager import SandboxManager
    from app.services.tool_service import ToolService
    from app.services.llm import LLMClient
    from app.repositories.model_setting import ModelConfigRepository
    skill_repo2 = SkillRepository()

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
                skill_tool_names = None
                if agent.skill_ids:
                    skill_tool_names = set()
                    for sid in agent.skill_ids:
                        skill = await skill_repo2.get(str(sid))
                        if skill:
                            for tn in skill.tool_names:
                                skill_tool_names.add(tn)
                openai_tools = []
                for t in user_tools:
                    if skill_tool_names is not None and t.name not in skill_tool_names:
                        continue
                    params = t.parameters.model_dump() if t.parameters else {
                        "type": "object", "properties": {}, "required": []}
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
                system_prompt = await _build_agent_system_prompt(agent)
                messages = [{"role": "system", "content": system_prompt}, {
                    "role": "user", "content": payload.message}]

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


@router.get("/{agent_id}/messages")
async def list_agent_messages(agent_id: str, before_id: str = None, limit: int = 20, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    msg_repo = AgentMessageRepository()
    messages, has_more = await msg_repo.get_messages(agent_id=int(agent_id), before_id=int(before_id) if before_id else None, limit=limit)
    return Response(data={"messages": [m.model_dump() for m in messages], "has_more": has_more})


@router.post("/{agent_id}/chat")
async def agent_chat(agent_id: str, payload: dict, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    message = payload.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="message required")

    msg_repo = AgentMessageRepository()
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    user_msg = await msg_repo.add_message(agent_id=int(agent_id), user_id=int(user.id), role="user", content=message)
    await msg_repo.add_part(message_id=int(user_msg.id), seq=0, content={"type": "input", "text": message})

    from app.services.llm import LLMClient
    from app.services.tool_service import ToolService
    from app.services.sandbox_manager import SandboxManager
    from app.repositories.model_setting import ModelConfigRepository

    class State:
        msg = None
        msg_id = 0

    state = State()

    async def event_generator():
        try:
            sandbox = SandboxManager()
            tool_service = ToolService(sandbox_paths=sandbox.base_paths)
            user_tools = await tool_service.tool_repo.get_user_enabled_tools(user_id=int(user.id))
            skill_tool_names = None
            if agent.skill_ids:
                skill_repo2 = SkillRepository()
                skill_tool_names = set()
                for sid in agent.skill_ids:
                    skill = await skill_repo2.get(str(sid))
                    if skill:
                        for tn in skill.tool_names:
                            skill_tool_names.add(tn)
            openai_tools = []
            for t in user_tools:
                if skill_tool_names is not None and t.name not in skill_tool_names:
                    continue
                params = t.parameters.model_dump() if t.parameters else {
                    "type": "object", "properties": {}, "required": []}
                openai_tools.append({
                    "type": "function",
                    "function": {"name": t.name, "description": t.description or t.display_name or t.name, "parameters": params},
                })

            model_repo = ModelConfigRepository()
            model_config = None
            if agent.model_id:
                model_config = await model_repo.get_model(agent.model_id)
            if not model_config:
                model_config = await model_repo.get_default_model()

            if not model_config:
                yield {"event": "error", "data": json.dumps({"error": "No model configured"})}
                return

            llm_client = LLMClient(model_config)

            existing = await msg_repo.get_messages(agent_id=int(agent_id), limit=20)
            system_prompt = await _build_agent_system_prompt(agent)
            llm_messages = [{"role": "system", "content": system_prompt}]
            for m in existing[0]:
                llm_messages.append({"role": m.role, "content": m.content})

            state.msg = await msg_repo.add_message(
                agent_id=int(agent_id), user_id=int(user.id), role="assistant",
                content="",
            )
            state.msg_id = int(state.msg.id)
            part_seq = 0

            all_thinking = ""
            all_answer = ""
            all_tool_calls_data = []

            # First LLM call
            thinking_first = ""
            answer_first = ""
            tool_calls_first = []

            async for chunk in llm_client.chat_with_tools_stream(llm_messages, openai_tools):
                if chunk["type"] == "reasoning":
                    thinking_first += chunk.get("delta", "")
                    yield {"event": "reasoning", "data": json.dumps({"delta": chunk.get("delta", "")})}
                elif chunk["type"] == "content":
                    answer_first += chunk.get("delta", "")
                    yield {"event": "delta", "data": json.dumps({"delta": chunk.get("delta", "")})}
                elif chunk["type"] == "done":
                    if chunk.get("content"):
                        answer_first = chunk.get("content", answer_first)
                    if chunk.get("tool_calls"):
                        tool_calls_first = chunk["tool_calls"]

            if thinking_first:
                await msg_repo.add_part(message_id=state.msg_id, seq=part_seq, content={"type": "thinking", "text": thinking_first})
                part_seq += 1
                all_thinking = thinking_first
                yield {"event": "thinking_done", "data": json.dumps({"text": thinking_first})}

            # If model wants to call tools, execute them
            if tool_calls_first:
                tc_list = [{"name": tc.get("name", ""), "arguments": tc.get(
                    "arguments", "")} for tc in tool_calls_first]
                await msg_repo.add_part(message_id=state.msg_id, seq=part_seq, content={"type": "tools", "calls": tc_list})
                part_seq += 1
                all_tool_calls_data.extend(tc_list)

                for tc in tool_calls_first:
                    yield {"event": "tool_call", "data": json.dumps({"tool": tc.get("name", ""), "args": tc.get("arguments", "")})}

                # Build assistant tool_calls message for LLM context
                assistant_tool_msg = {
                    "role": "assistant",
                    "content": answer_first or "",
                    "tool_calls": [
                        {"id": tc.get("id", "call_" + str(i)), "type": "function",
                         "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                        for i, tc in enumerate(tool_calls_first)
                    ]
                }
                if thinking_first:
                    assistant_tool_msg["reasoning_content"] = thinking_first
                llm_messages.append(assistant_tool_msg)

                # Execute tools
                tool_results = await tool_service.process_tool_calls(tool_calls_first)
                executed_tools = []
                for i, tr in enumerate(tool_results):
                    result_content = tr.get("content", "")
                    executed_tools.append({
                        "name": tr.get("name", ""),
                        "arguments": tc_list[i]["arguments"] if i < len(tc_list) else "{}",
                        "result": result_content[:2000],
                        "success": '"success": true' in result_content.lower() if result_content else False,
                    })
                    llm_messages.append({
                        "role": "tool",
                        "tool_call_id": tr.get("tool_call_id", ""),
                        "content": result_content,
                    })
                    yield {"event": "tool_result", "data": json.dumps({"tool": tr.get("name", ""), "result": result_content[:500]})}

                await msg_repo.add_part(message_id=state.msg_id, seq=part_seq, content={"type": "tools_result", "calls": executed_tools})
                part_seq += 1

                # Second LLM call with tool results
                thinking_second = ""
                answer_second = ""
                async for chunk in llm_client.chat_with_tools_stream(llm_messages, openai_tools):
                    if chunk["type"] == "reasoning":
                        thinking_second += chunk.get("delta", "")
                        yield {"event": "reasoning", "data": json.dumps({"delta": chunk.get("delta", "")})}
                    elif chunk["type"] == "content":
                        answer_second += chunk.get("delta", "")
                        yield {"event": "delta", "data": json.dumps({"delta": chunk.get("delta", "")})}
                    elif chunk["type"] == "done":
                        if chunk.get("content"):
                            answer_second = chunk.get("content", answer_second)

                if thinking_second:
                    await msg_repo.add_part(message_id=state.msg_id, seq=part_seq, content={"type": "thinking", "text": thinking_second})
                    part_seq += 1
                    all_thinking += ("\n\n" + thinking_second)

                if answer_second:
                    await msg_repo.add_part(message_id=state.msg_id, seq=part_seq, content={"type": "answer", "text": answer_second})
                    part_seq += 1
                    all_answer = answer_second
            else:
                # No tool calls, just a direct answer
                if answer_first:
                    await msg_repo.add_part(message_id=state.msg_id, seq=part_seq, content={"type": "answer", "text": answer_first})
                    part_seq += 1
                    all_answer = answer_first

            final_content = all_answer or answer_first or ""
            await msg_repo.update_message_content(message_id=state.msg_id, content=final_content)
            llm_messages.append(
                {"role": "assistant", "content": final_content})
            full_input_json = json.dumps(llm_messages, ensure_ascii=False)
            await msg_repo.update_message_full_input(message_id=state.msg_id, full_input=full_input_json)
            yield {"event": "done", "data": json.dumps({"reply": final_content})}

        except Exception as e:
            logger.error(f"Agent chat error: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())
