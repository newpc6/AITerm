import json
import logging
import re
from typing import AsyncGenerator, Optional, Dict, Any
from datetime import datetime

from app.models import Node, ModelConfig, Task, TaskStatus
from app.repositories import INodeRepository, IModelConfigRepository, ITaskRepository
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.services.llm import ChatService, LLMClient

logger = logging.getLogger("aiterm.chat_orchestrator")


class ChatOrchestrator:
    def __init__(
        self,
        node_repo: INodeRepository,
        model_repo: IModelConfigRepository,
        task_repo: ITaskRepository,
        task_service,
        settings
    ):
        self.node_repo = node_repo
        self.model_repo = model_repo
        self.task_repo = task_repo
        self.task_service = task_service
        self.settings = settings
        self.chat_repo = ChatRepository()
        self.message_repo = MessageRepository()

    async def detect_intent(self, message: str, model_config: ModelConfig) -> str:
        response_text = ""
        try:
            llm_client = LLMClient(model_config)
            intent_prompt = self.settings.intent_detection_prompt
            prompt = intent_prompt.replace("{user_message}", message)
            logger.info(f"Intent detection prompt: {prompt[:100]}...")
            logger.info(
                f"Intent detection using model: {model_config.model}, api_url: {model_config.api_url}")

            response = await llm_client.chat([
                {"role": "user", "content": prompt}
            ], temperature=0.1)
            logger.info(f"Intent detection raw response: {repr(response)}")

            response_text = response.strip()
            if response_text.startswith("```"):
                json_match = re.search(
                    r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    response_text = json_match.group(1)

            result = json.loads(response_text)
            intent = result.get("intent", "chat")
            logger.info(
                f"Intent detection: message='{message[:50]}...', intent={intent}")
            return intent
        except json.JSONDecodeError as e:
            logger.warning(
                f"Intent detection JSON decode failed: {e}, response: {repr(response_text)}, defaulting to chat")
            return "chat"
        except Exception as e:
            logger.warning(f"Intent detection failed: {e}, defaulting to chat")
            return "chat"

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

        if mode == "task":
            return await self._create_task_conversation(conversation_id, node_id, message, model_id)

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

    async def _create_task_conversation(
        self,
        conversation_id: str,
        node_id: str,
        message: str,
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        model_config = await self._get_model_config(model_id)
        node = await self.node_repo.get_node(node_id)
        node_label = node.name if node else f"节点 {node_id}"

        now = datetime.utcnow().isoformat()
        task = Task(
            id="0",
            title=f"任务: {message[:50]}",
            status=TaskStatus.PENDING,
            progress=0,
            conversation_id=conversation_id,
            node_id=node_id,
            model_id=model_config.id,
            model_name=model_config.name,
            request=message,
            summary=f"任务已创建，等待模型基于节点 {node_label} 生成执行计划。",
            steps=[],
            created_at=now,
            updated_at=now
        )
        created_task = await self.task_repo.create_task(task)

        logger.info(
            f"Created task {created_task.id} for conversation {conversation_id}")

        return {
            "conversation_id": conversation_id,
            "mode": "task",
            "task_id": created_task.id,
            "model_id": model_config.id,
            "model_name": model_config.name
        }

    async def stream_chat(
        self,
        chat_id: Optional[str],
        node_id: str,
        message: str,
        model_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        model_config = await self._get_model_config(model_id)

        logger.info(f"Starting stream_chat for message: {message[:50]}...")

        if not chat_id:
            chat = await self.chat_repo.create_chat(
                title=message[:50] if message else "新对话",
                node_id=int(node_id),
                model_id=int(model_config.id) if model_config.id else None,
                model_name=model_config.name
            )
            chat_id = chat.id

        intent = await self.detect_intent(message, model_config)
        mode = "task" if intent == "execute" else "chat"
        logger.info(f"Detected intent: {intent}, mode: {mode}")

        yield {
            "event": "conversation.meta",
            "data": {
                "conversation_id": chat_id,
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

        if mode == "task":
            logger.info(f"Entering task mode, calling _stream_task")
            try:
                async for event in self._stream_task(chat_id, node_id, message, model_config):
                    yield event
            except Exception as e:
                logger.error(f"Error streaming task: {e}")
                yield {
                    "event": "conversation.message",
                    "data": {
                        "conversation_id": chat_id,
                        "type": "error",
                        "content": f"执行操作失败: {str(e)}"
                    }
                }
            return

        node = await self.node_repo.get_node(node_id)
        messages = await self.message_repo.list_messages(chat_id, page=1, page_size=50)
        history = [{"role": m.role, "content": m.content} for m in messages]

        logger.info(f"Chat mode: starting chat_stream for chat {chat_id}")
        logger.info(
            f"Chat mode: node_id={node_id}, node={node.name if node else 'None'}")
        logger.info(f"Chat mode: history length={len(history)}")

        chat_service = ChatService(
            model_config, self.settings.chat_system_prompt, self.settings.chat_history_limit)

        logger.info(
            f"Chat mode: chat_service created with model={model_config.model}")

        full_response = []
        try:
            chunk_count = 0
            async for chunk in chat_service.chat_stream(node, history, message):
                chunk_count += 1
                full_response.append(chunk)
                logger.info(f"Chat mode: yielding delta chunk #{chunk_count}")
                yield {
                    "event": "conversation.delta",
                    "data": {
                        "conversation_id": chat_id,
                        "delta": chunk
                    }
                }
            logger.info(f"Chat mode: received {chunk_count} chunks")
        except Exception as e:
            logger.error(f"Chat mode error: {e}")
            yield {
                "event": "conversation.error",
                "data": {
                    "conversation_id": chat_id,
                    "error": str(e)
                }
            }
            return

        complete_response = "".join(full_response)
        await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=complete_response,
            type="text"
        )

        yield {
            "event": "conversation.done",
            "data": {
                "conversation_id": chat_id,
                "reply": complete_response,
                "model_id": model_config.id,
                "model_name": model_config.name
            }
        }

    async def _stream_task(
        self,
        chat_id: str,
        node_id: str,
        message: str,
        model_config: ModelConfig
    ) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            node = await self.node_repo.get_node(node_id)
            node_label = node.name if node else f"节点 {node_id}"

            now = datetime.utcnow().isoformat()
            task = Task(
                id="0",
                title=f"执行操作: {message[:50]}",
                status=TaskStatus.PENDING,
                progress=0,
                conversation_id=chat_id,
                node_id=node_id,
                model_id=model_config.id,
                model_name=model_config.name,
                request=message,
                summary=f"正在基于节点 {node_label} 生成执行计划。",
                steps=[],
                created_at=now,
                updated_at=now
            )
            created_task = await self.task_repo.create_task(task)
            task_id = created_task.id

            logger.info(f"Created execution {task_id} for chat {chat_id}")

            yield {
                "event": "conversation.task_created",
                "data": {
                    "conversation_id": chat_id,
                    "task_id": task_id
                }
            }

            async for event in self.task_service.execute_task(task_id, chat_id):
                yield event
        except Exception as e:
            logger.error(f"Error in _stream_task: {e}")
            yield {
                "event": "conversation.message",
                "data": {
                    "conversation_id": chat_id,
                    "type": "error",
                    "content": f"执行操作失败: {str(e)}"
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

    async def create_chat(
        self,
        node_id: str,
        message: str,
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        model_config = await self._get_model_config(model_id)

        chat = await self.chat_repo.create_chat(
            title=message[:50] if message else "新对话",
            node_id=int(node_id),
            model_id=int(model_config.id) if model_config.id else None,
            model_name=model_config.name
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

    async def continue_chat(
        self,
        chat_id: str,
        message: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        chat = await self.chat_repo.get_chat(chat_id)
        if not chat:
            yield {
                "event": "conversation.error",
                "data": {"error": "chat not found"}
            }
            return

        model_config = await self._get_model_config(chat.model_id)

        await self.message_repo.create_message(
            chat_id=chat_id,
            role="user",
            content=message,
            type="text"
        )

        yield {
            "event": "conversation.meta",
            "data": {
                "conversation_id": chat_id,
                "mode": "chat",
                "node_id": chat.node_id
            }
        }

        intent = await self.detect_intent(message, model_config)
        mode = "task" if intent == "execute" else "chat"

        if mode == "task":
            async for event in self._stream_task(chat_id, chat.node_id, message, model_config):
                yield event
        else:
            node = await self.node_repo.get_node(chat.node_id)
            messages = await self.message_repo.list_messages(chat_id, page=1, page_size=50)
            history = [{"role": m.role, "content": m.content}
                       for m in messages]

            chat_service = ChatService(
                model_config, self.settings.chat_system_prompt, self.settings.chat_history_limit)

            full_response = []
            try:
                async for chunk in chat_service.chat_stream(node, history, message):
                    full_response.append(chunk)
                    yield {
                        "event": "conversation.delta",
                        "data": {
                            "conversation_id": chat_id,
                            "delta": chunk
                        }
                    }
            except Exception as e:
                logger.error(f"Chat error: {e}")
                yield {
                    "event": "conversation.error",
                    "data": {"error": str(e)}
                }
                return

            complete_response = "".join(full_response)
            await self.message_repo.create_message(
                chat_id=chat_id,
                role="assistant",
                content=complete_response,
                type="text"
            )

            yield {
                "event": "conversation.done",
                "data": {
                    "conversation_id": chat_id,
                    "reply": complete_response,
                    "model_id": model_config.id,
                    "model_name": model_config.name
                }
            }
