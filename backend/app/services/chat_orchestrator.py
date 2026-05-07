import json
import logging
import re
from datetime import datetime
from typing import AsyncGenerator, Optional, Dict, Any, List

from app.models import Node, ModelConfig, ChatStatus
from app.repositories import INodeRepository, IModelConfigRepository
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.services.llm import ChatService, LLMClient
from app.services.tool_service import ToolService
from app.services.sandbox_manager import SandboxManager
from app.services.langchain import get_skill_registry
from app.utils import now_iso

logger = logging.getLogger("aiterm")


def sanitize_unicode(text: str) -> str:
    if not text:
        return text
    return text.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')


class ChatOrchestrator:
    def __init__(
        self,
        node_repo: INodeRepository,
        model_repo: IModelConfigRepository,
        execute_service,
        settings
    ):
        self.node_repo = node_repo
        self.model_repo = model_repo
        self.execute_service = execute_service
        self.settings = settings
        self.sandbox = SandboxManager()
        self.chat_repo = ChatRepository()
        self.message_repo = MessageRepository()
        self.tool_service = ToolService(sandbox_paths=self.sandbox.base_paths)

    async def create_conversation(
        self,
        conversation_id: Optional[str],
        node_id: str,
        message: str,
        mode: str = "chat",
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not conversation_id:
            chat = await self.chat_repo.create_chat(
                title=message[:50] if message else "新对话",
                node_id=int(node_id),
                model_id=int(model_id) if model_id else None,
                model_name=None
            )
            conversation_id = chat.id

        await self.message_repo.create_message(
            chat_id=conversation_id,
            role="user",
            content=message,
            type="text"
        )

        if mode == "execute":
            return await self._create_execute_conversation(conversation_id, node_id, message, model_id)

        node = await self.node_repo.get_node(node_id)
        messages = await self.message_repo.list_messages(conversation_id, page=1, page_size=50)
        history = [{"role": m.role, "content": m.content} for m in messages]

        model_config = await self._get_model_config(model_id)
        chat_service = ChatService(
            model_config, self.settings.chat_system_prompt)

        response = await chat_service.chat(node, history, message)

        await self.message_repo.create_message(
            chat_id=conversation_id,
            role="assistant",
            content=response,
            type="text"
        )

        return {
            "conversation_id": conversation_id,
            "mode": mode,
            "model_id": model_config.id,
            "model_name": model_config.name,
            "response": response
        }

    async def _create_execute_conversation(
        self,
        conversation_id: str,
        node_id: str,
        message: str,
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        model_config = await self._get_model_config(model_id)

        await self.chat_repo.update_chat(
            conversation_id,
            mode="execute",
            request=message,
            status=ChatStatus.PENDING.value,
            progress=5,
            summary="执行操作已创建，等待规划。"
        )

        logger.info(f"Created execute conversation {conversation_id}")

        return {
            "conversation_id": conversation_id,
            "mode": "execute",
            "model_id": model_config.id,
            "model_name": model_config.name
        }

    async def stream_chat(
        self,
        chat_id: Optional[str],
        node_id: str,
        message: str,
        model_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        model_config = await self._get_model_config(model_id)

        logger.info(f"Starting stream_chat for message: {message[:50]}...")

        if not chat_id:
            chat = await self.chat_repo.create_chat(
                title=message[:50] if message else "新对话",
                node_id=int(node_id),
                model_id=int(model_config.id) if model_config.id else None,
                model_name=model_config.name,
                user_id=user_id
            )
            chat_id = chat.id

        mode = "chat"

        yield {
            "event": "conversation.meta",
            "data": {
                "chat_id": chat_id,
                "mode": mode,
                "node_id": node_id
            }
        }

        await self.message_repo.create_message(
            chat_id=chat_id,
            role="user",
            content=message,
            type="text"
        )

        if mode == "execute":
            logger.info("Entering execute mode")
            try:
                async for event in self.execute_service.execute(chat_id, node_id, message, model_config):
                    yield event
            except Exception as e:
                logger.error(f"Error streaming execute: {e}")
                error_msg = f"执行操作失败: {str(e)}"
                await self.message_repo.create_message(
                    chat_id=chat_id,
                    role="assistant",
                    content=error_msg,
                    type="error"
                )
                yield {
                    "event": "conversation.message",
                    "data": {
                        "chat_id": chat_id,
                        "type": "error",
                        "content": error_msg
                    }
                }
            return

        node = await self.node_repo.get_node(node_id)
        messages = await self.message_repo.list_messages(chat_id, page=1, page_size=50)
        history = [{"role": m.role, "content": m.content} for m in messages]

        tools = await self.tool_service.get_openai_tools()
        if tools:
            logger.info(f"Found {len(tools)} tools, using tool-enabled chat")
            async for event in self._handle_chat_with_tools(
                chat_id, model_config, node, history, message, tools
            ):
                yield event
            return

        chat_service = ChatService(
            model_config, self.settings.chat_system_prompt, self.settings.chat_history_limit)

        full_response = []
        reasoning_response = []
        reasoning_sent_done = False
        reasoning_start_time = None
        reasoning_duration = 0.0
        total_start_time = datetime.now()
        chat_usage = {}

        try:
            async for chunk in chat_service.chat_stream(node, history, message):
                if chunk["type"] == "usage":
                    chat_usage = chunk.get("usage", {})
                    continue
                if chunk["type"] == "reasoning":
                    if reasoning_start_time is None:
                        reasoning_start_time = datetime.now()
                    reasoning_response.append(chunk["content"])
                    yield {
                        "event": "conversation.reasoning",
                        "data": {
                            "chat_id": chat_id,
                            "delta": chunk["content"]
                        }
                    }
                else:
                    if chunk.get("reasoning_done") and not reasoning_sent_done and reasoning_response:
                        reasoning_sent_done = True
                        if reasoning_start_time:
                            reasoning_duration = (
                                datetime.now() - reasoning_start_time).total_seconds()
                        yield {
                            "event": "conversation.reasoning_done",
                            "data": {
                                "chat_id": chat_id,
                                "duration": reasoning_duration
                            }
                        }
                    full_response.append(chunk["content"])
                    yield {
                        "event": "conversation.delta",
                        "data": {
                            "chat_id": chat_id,
                            "delta": chunk["content"]
                        }
                    }
        except Exception as e:
            logger.error(f"Chat mode error: {e}")
            yield {
                "event": "conversation.error",
                "data": {
                    "chat_id": chat_id,
                    "error": str(e)
                }
            }
            return

        complete_response = "".join(full_response)
        complete_reasoning = "".join(reasoning_response)

        total_duration = (datetime.now() - total_start_time).total_seconds()

        if complete_reasoning:
            message_content_obj = {
                "answer": complete_response,
                "thinking": complete_reasoning,
                "reasoning_duration": round(reasoning_duration, 2),
                "total_duration": round(total_duration, 2),
            }
        else:
            message_content_obj = {
                "answer": complete_response,
                "total_duration": round(total_duration, 2),
            }

        if chat_usage:
            message_content_obj["usage"] = chat_usage

        await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=json.dumps(message_content_obj, ensure_ascii=False),
            type="text"
        )

        yield {
            "event": "conversation.done",
            "data": {
                "chat_id": chat_id,
                "reply": complete_response,
                "reasoning": complete_reasoning,
                "model_id": model_config.id,
                "model_name": model_config.name,
                "total_duration": round(total_duration, 2),
                "usage": chat_usage
            }
        }

    async def _get_model_config(self, model_id: Optional[str] = None) -> ModelConfig:
        model_config = None
        if model_id:
            model_config = await self.model_repo.get_model(model_id)
        if not model_config:
            model_config = await self.model_repo.get_default_model()

        if not model_config:
            raise ValueError("未配置模型，请先在设置页添加模型配置")

        return model_config

    async def _handle_chat_with_tools(
        self,
        chat_id: str,
        model_config: ModelConfig,
        node: Node,
        history: List[Dict[str, Any]],
        message: str,
        tools: List[Dict[str, Any]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        llm_client = LLMClient(
            model_config, debug_logging=self.settings.llm_debug_logging)
        chat_service = ChatService(
            model_config, self.settings.chat_system_prompt, self.settings.chat_history_limit)

        system_prompt = chat_service._build_system_prompt(node)

        if tools:
            tool_info_list = []
            for t in tools:
                name = t["function"]["name"]
                desc = t["function"].get("description", "")
                if desc:
                    tool_info_list.append(f"- {name}: {desc}")
                else:
                    tool_info_list.append(f"- {name}")
            tool_info = "\n".join(tool_info_list)
            system_prompt += f"\n\n你可以使用以下工具来获取信息或执行操作：\n{tool_info}\n\n当用户问题需要使用这些工具时，请直接调用工具，不要只是思考或提及工具。"

        sandbox_paths = self.sandbox.base_paths
        if sandbox_paths:
            sandbox_paths_str = ", ".join(sandbox_paths)
            sandbox_prompt = await self.sandbox.get_rules_prompt()
            sandbox_prompt = sandbox_prompt.replace(
                "{{sandbox_paths}}", sandbox_paths_str)
            system_prompt += f"\n\n{sandbox_prompt}"
            system_prompt += f"\n\n当前chat_id: {chat_id}\n"

        messages = [
            {"role": "system", "content": system_prompt}]
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ["user", "assistant"]:
                if role == "assistant" and content:
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, dict) and "answer" in parsed:
                            answer = parsed.get("answer", "")
                            iterations_data = parsed.get("iterations", [])
                            if iterations_data:
                                for iter_data in iterations_data:
                                    iter_content = iter_data.get("content", "")
                                    iter_tool_calls = iter_data.get(
                                        "tool_calls", [])
                                    iter_thinking = iter_data.get(
                                        "thinking", "")
                                    assistant_part = {"role": "assistant"}
                                    if iter_content:
                                        assistant_part["content"] = iter_content
                                    if iter_thinking:
                                        assistant_part["reasoning_content"] = iter_thinking
                                    if iter_tool_calls:
                                        assistant_part["tool_calls"] = [
                                            {
                                                "id": tc.get("id", f"call_{i}"),
                                                "type": "function",
                                                "function": {
                                                    "name": tc["name"],
                                                    "arguments": tc.get("arguments", "{}")
                                                }
                                            }
                                            for i, tc in enumerate(iter_tool_calls)
                                        ]
                                    if assistant_part.get("content") or assistant_part.get("tool_calls"):
                                        messages.append(assistant_part)
                                    for tc in iter_tool_calls:
                                        tc_id = tc.get(
                                            "id", f"call_{len(messages)}")
                                        messages.append({
                                            "role": "tool",
                                            "tool_call_id": tc_id,
                                            "content": tc.get("result", "")
                                        })
                            else:
                                messages.append(
                                    {"role": role, "content": answer})
                            continue
                    except (json.JSONDecodeError, TypeError):
                        pass
                messages.append({"role": role, "content": content})

        total_start_time = datetime.now()
        full_response = []
        iterations_info = []

        max_iterations = self.settings.max_iterations or 20
        for iteration in range(max_iterations):
            logger.info(
                f"Tool calling iteration {iteration + 1}/{max_iterations}")

            iteration_input = None
            iteration_full_input = None
            iteration_full_input = json.dumps(
                messages, ensure_ascii=False, indent=2)
            if self.settings.show_llm_input:
                iteration_input = json.dumps(
                    messages[-1], ensure_ascii=False, indent=2)
                yield {
                    "event": "conversation.iteration_start",
                    "data": {
                        "chat_id": chat_id,
                        "iteration": iteration + 1,
                        "input": iteration_input,
                        "full_input": iteration_full_input
                    }
                }

            iteration_content = ""
            iteration_reasoning = ""
            iteration_tool_calls = None
            iteration_usage = {}
            iteration_reasoning_started = False
            iteration_reasoning_duration = 0
            iteration_start_time = datetime.now()
            iteration_reasoning_start_time = None
            iteration_tool_calls_info = []

            async for chunk in llm_client.chat_with_tools_stream(messages, tools):
                if chunk["type"] == "reasoning":
                    if not iteration_reasoning_started:
                        iteration_reasoning_start_time = datetime.now()
                        iteration_reasoning_started = True
                        yield {
                            "event": "conversation.reasoning_start",
                            "data": {
                                "chat_id": chat_id,
                                "iteration": iteration + 1,
                                "timestamp": iteration_reasoning_start_time.isoformat()
                            }
                        }
                    iteration_reasoning += chunk["delta"]
                    yield {
                        "event": "conversation.reasoning",
                        "data": {
                            "chat_id": chat_id,
                            "iteration": iteration + 1,
                            "delta": chunk["delta"]
                        }
                    }
                elif chunk["type"] == "content":
                    if iteration_reasoning_started:
                        iteration_reasoning_duration = (
                            datetime.now() - iteration_reasoning_start_time).total_seconds()
                        yield {
                            "event": "conversation.reasoning_done",
                            "data": {
                                "chat_id": chat_id,
                                "iteration": iteration + 1,
                                "duration": round(iteration_reasoning_duration, 2)
                            }
                        }
                        iteration_reasoning_started = False
                    iteration_content += chunk["delta"]
                    yield {
                        "event": "conversation.delta",
                        "data": {
                            "chat_id": chat_id,
                            "iteration": iteration + 1,
                            "delta": chunk["delta"]
                        }
                    }
                elif chunk["type"] == "done":
                    iteration_tool_calls = chunk.get("tool_calls")
                    iteration_usage = chunk.get("usage", {})
                    if iteration_reasoning_started:
                        iteration_reasoning_duration = (
                            datetime.now() - iteration_reasoning_start_time).total_seconds()
                        yield {
                            "event": "conversation.reasoning_done",
                            "data": {
                                "chat_id": chat_id,
                                "iteration": iteration + 1,
                                "duration": round(iteration_reasoning_duration, 2)
                            }
                        }
                        iteration_reasoning_started = False

            full_response.append(iteration_content)
            tool_calls = iteration_tool_calls or []
            logger.info(
                f"Tool response: content={iteration_content[:100]}, tool_calls={len(tool_calls)}")

            if not tool_calls:
                iterations_info.append({
                    "thinking": iteration_reasoning,
                    "thinking_duration": round(iteration_reasoning_duration, 2) if iteration_reasoning_duration > 0 else None,
                    "thinking_start_time": iteration_reasoning_start_time.isoformat() if iteration_reasoning_start_time else None,
                    "tool_calls": [],
                    "input": iteration_input,
                    "full_input": iteration_full_input,
                    "content": iteration_content,
                    "usage": iteration_usage
                })
                break

            assistant_msg = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"]
                        }
                    }
                    for tc in tool_calls
                ]
            }
            if iteration_content:
                assistant_msg["content"] = iteration_content
            if iteration_reasoning:
                assistant_msg["reasoning_content"] = iteration_reasoning
            messages.append(assistant_msg)

            tool_results = await self.tool_service.process_tool_calls(tool_calls, chat_id)
            logger.info(f"Tool results count: {len(tool_results)}")

            for i, result in enumerate(tool_results):
                tool_call = tool_calls[i] if i < len(tool_calls) else {}
                tool_timestamp = datetime.now().isoformat()

                result_content = sanitize_unicode(result.get("content", ""))
                if result_content and len(result_content) > 10000:
                    result_content = result_content[:10000] + "... [truncated]"

                iteration_tool_calls_info.append({
                    "id": tool_call.get("id", ""),
                    "name": result["name"],
                    "arguments": tool_call.get("arguments", "{}"),
                    "result": result_content,
                    "success": "success" in result.get("content", "") and "true" in result.get("content", "").lower(),
                    "timestamp": tool_timestamp
                })

                yield {
                    "event": "conversation.tool_call",
                    "data": {
                        "chat_id": chat_id,
                        "iteration": iteration + 1,
                        "name": result["name"],
                        "arguments": tool_call.get("arguments", "{}"),
                        "result": result_content,
                        "timestamp": tool_timestamp
                    }
                }

                messages.append({
                    "role": "tool",
                    "tool_call_id": result["tool_call_id"],
                    "content": result_content
                })

            iterations_info.append({
                "thinking": iteration_reasoning,
                "thinking_duration": round(iteration_reasoning_duration, 2) if iteration_reasoning_duration > 0 else None,
                "thinking_start_time": iteration_reasoning_start_time.isoformat() if iteration_reasoning_start_time else None,
                "tool_calls": iteration_tool_calls_info,
                "input": iteration_input,
                "full_input": iteration_full_input,
                "content": iteration_content,
                "usage": iteration_usage
            })

        complete_response = "".join(full_response)
        total_duration = (datetime.now() - total_start_time).total_seconds()

        try:
            await self.message_repo.create_message_with_data(
                chat_id=chat_id,
                role="assistant",
                answer=complete_response,
                total_duration=round(total_duration, 2),
                iterations=iterations_info if iterations_info else None
            )
        except Exception as e:
            logger.error(f"Failed to save message: {e}", exc_info=True)

        yield {
            "event": "conversation.done",
            "data": {
                "chat_id": chat_id,
                "reply": complete_response,
                "model_id": model_config.id,
                "model_name": model_config.name,
                "iterations": iterations_info if iterations_info else None,
                "total_duration": round(total_duration, 2),
                "usage": iterations_info[-1].get("usage", {}) if iterations_info else {}
            }
        }

    async def _chat_with_tools(
        self,
        model_config: ModelConfig,
        messages: List[Dict[str, Any]],
        max_iterations: int = 30
    ) -> AsyncGenerator[Dict[str, Any], None]:
        llm_client = LLMClient(model_config)
        tools = await self.tool_service.get_openai_tools()

        if not tools:
            yield {"type": "content", "content": ""}
            return

        for iteration in range(max_iterations):
            logger.info(
                f"Tool calling iteration {iteration + 1}/{max_iterations}")

            response = await llm_client.chat_with_tools(messages, tools)

            if response.get("content"):
                yield {"type": "content", "content": response["content"]}

            if not response.get("tool_calls"):
                break

            messages.append({
                "role": "assistant",
                "content": response.get("content") or "",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"]
                        }
                    }
                    for tc in response["tool_calls"]
                ]
            })

            tool_results = await self.tool_service.process_tool_calls(response["tool_calls"])

            for result in tool_results:
                yield {
                    "type": "tool_call",
                    "name": result["name"],
                    "content": result["content"]
                }

                messages.append({
                    "role": "tool",
                    "tool_call_id": result["tool_call_id"],
                    "content": result["content"]
                })

        yield {"type": "done"}

    async def create_chat(
        self,
        node_id: str,
        message: str,
        model_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        model_config = await self._get_model_config(model_id)

        chat = await self.chat_repo.create_chat(
            title=message[:50] if message else "新对话",
            node_id=int(node_id),
            model_id=int(model_config.id) if model_config.id else None,
            model_name=model_config.name,
            user_id=user_id
        )

        await self.message_repo.create_message(
            chat_id=chat.id,
            role="user",
            content=message,
            type="text"
        )

        return {
            "chat_id": chat.id,
            "title": chat.title,
            "model_id": model_config.id,
            "model_name": model_config.name
        }

    async def _handle_chat_with_langchain_agent(
        self,
        chat_id: str,
        model_config: ModelConfig,
        node: Node,
        history: List[Dict[str, Any]],
        message: str,
        tools: List[Dict[str, Any]],
        skill_name: str = "general_assistant"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        from app.services.langchain.agent_manager import LangChainAgentManager

        skill_registry = get_skill_registry()
        skill_prompt = skill_registry.get_aggregated_prompt(
            [skill_name],
            self.settings.chat_system_prompt or "你是一个中文AI助手"
        )

        sandbox_paths = self.sandbox.base_paths
        if sandbox_paths:
            sandbox_prompt = await self.sandbox.get_rules_prompt()
            sandbox_prompt = sandbox_prompt.replace(
                "{{sandbox_paths}}", ", ".join(sandbox_paths))
            skill_prompt += f"\n\n{sandbox_prompt}"
            skill_prompt += f"\n\n当前chat_id: {chat_id}\n"

        agent_manager = LangChainAgentManager(
            model_config=model_config,
            tools=tools,
            system_prompt=skill_prompt,
            max_iterations=self.settings.max_iterations or 10,
            tool_service=self.tool_service,
            chat_id=chat_id,
        )

        full_response = []
        total_start_time = datetime.now()

        try:
            async for event in agent_manager.stream(message, history):
                if event["type"] == "content":
                    full_response.append(event["delta"])
                    yield {
                        "event": "conversation.delta",
                        "data": {
                            "chat_id": chat_id,
                            "delta": event["delta"],
                            "iteration": event.get("iteration", 1),
                        }
                    }
                elif event["type"] == "tool_start":
                    yield {
                        "event": "conversation.tool_call",
                        "data": {
                            "chat_id": chat_id,
                            "tool": event["tool"],
                            "input": event["input"],
                            "iteration": event.get("iteration", 1),
                        }
                    }
                elif event["type"] == "tool_end":
                    yield {
                        "event": "conversation.tool_result",
                        "data": {
                            "chat_id": chat_id,
                            "output": event["output"],
                            "iteration": event.get("iteration", 1),
                        }
                    }
                elif event["type"] == "error":
                    raise Exception(event["error"])
        except Exception as e:
            logger.error(f"LangChain agent error: {e}")
            yield {
                "event": "conversation.error",
                "data": {"chat_id": chat_id, "error": str(e)}
            }
            return

        complete_response = "".join(full_response)
        total_duration = (datetime.now() - total_start_time).total_seconds()

        await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=json.dumps({
                "answer": complete_response,
                "total_duration": round(total_duration, 2),
            }, ensure_ascii=False),
            type="text"
        )

        yield {
            "event": "conversation.done",
            "data": {
                "chat_id": chat_id,
                "reply": complete_response,
                "model_id": model_config.id,
                "model_name": model_config.name,
                "total_duration": round(total_duration, 2),
            }
        }
