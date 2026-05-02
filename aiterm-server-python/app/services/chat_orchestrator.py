import json
import logging
import re
from datetime import datetime
from typing import AsyncGenerator, Optional, Dict, Any

from app.models import Node, ModelConfig, ChatStatus
from app.repositories import INodeRepository, IModelConfigRepository
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.services.llm import ChatService, LLMClient
from app.utils import now_iso

logger = logging.getLogger("aiterm")


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
        self.chat_repo = ChatRepository()
        self.message_repo = MessageRepository()

    async def detect_intent(self, message: str, model_config: ModelConfig) -> str:
        response_text = ""
        try:
            llm_client = LLMClient(model_config)
            intent_prompt = self.settings.intent_detection_prompt
            prompt = intent_prompt.replace("{user_message}", message)
            logger.info(f"Intent detection prompt: {prompt[:100]}...")

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
            logger.info(f"Intent detection: intent={intent}")
            return intent
        except json.JSONDecodeError as e:
            logger.warning(
                f"Intent detection JSON decode failed: {e}, defaulting to chat")
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
        mode = "execute" if intent == "execute" else "chat"
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
                        "conversation_id": chat_id,
                        "type": "error",
                        "content": error_msg
                    }
                }
            return

        node = await self.node_repo.get_node(node_id)
        messages = await self.message_repo.list_messages(chat_id, page=1, page_size=50)
        history = [{"role": m.role, "content": m.content} for m in messages]

        chat_service = ChatService(
            model_config, self.settings.chat_system_prompt, self.settings.chat_history_limit)

        full_response = []
        reasoning_response = []
        reasoning_sent_done = False
        reasoning_start_time = None
        reasoning_duration = 0.0
        total_start_time = datetime.now()

        try:
            async for chunk in chat_service.chat_stream(node, history, message):
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
            message_content = json.dumps({
                "answer": complete_response,
                "thinking": complete_reasoning,
                "reasoning_duration": round(reasoning_duration, 2),
                "total_duration": round(total_duration, 2),
            }, ensure_ascii=False)
        else:
            message_content = json.dumps({
                "answer": complete_response,
                "total_duration": round(total_duration, 2),
            }, ensure_ascii=False)

        await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=message_content,
            type="text"
        )

        yield {
            "event": "conversation.done",
            "data": {
                "chat_id": chat_id,
                "reply": complete_response,
                "reasoning": complete_reasoning,
                "model_id": model_config.id,
                "model_name": model_config.name
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

        intent = await self.detect_intent(message, model_config)
        mode = "execute" if intent == "execute" else "chat"

        yield {
            "event": "conversation.meta",
            "data": {
                "conversation_id": chat_id,
                "mode": mode,
                "node_id": chat.node_id
            }
        }

        if mode == "execute":
            async for event in self.execute_service.execute(chat_id, chat.node_id, message, model_config):
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
