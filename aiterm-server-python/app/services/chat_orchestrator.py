import logging
from typing import AsyncGenerator, Optional, Dict, Any
from datetime import datetime

from app.models import ConversationMessage, Node, ModelConfig, Task, TaskStatus
from app.repositories import IConversationRepository, INodeRepository, IModelConfigRepository, ITaskRepository
from app.services.llm import ChatService

logger = logging.getLogger("aiterm.chat_orchestrator")


class ChatOrchestrator:
    def __init__(
        self,
        conversation_repo: IConversationRepository,
        node_repo: INodeRepository,
        model_repo: IModelConfigRepository,
        task_repo: ITaskRepository,
        settings
    ):
        self.conversation_repo = conversation_repo
        self.node_repo = node_repo
        self.model_repo = model_repo
        self.task_repo = task_repo
        self.settings = settings

    async def create_conversation(
        self,
        conversation_id: Optional[str],
        node_id: str,
        message: str,
        mode: str = "chat",
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not conversation_id:
            conversation_id = str(await self.conversation_repo.get_next_conversation_id())

        await self.conversation_repo.append_message(ConversationMessage(
            id="0",
            conversation_id=conversation_id,
            role="user",
            content=message,
            created_at=datetime.utcnow().isoformat()
        ))

        if mode == "task":
            return await self._create_task_conversation(conversation_id, node_id, message, model_id)

        node = await self.node_repo.get_node(node_id)
        history = await self.conversation_repo.get_conversation_messages(conversation_id)

        model_config = await self._get_model_config(model_id)
        chat_service = ChatService(model_config, self.settings.chat_system_prompt)

        response = await chat_service.chat(node, history, message)

        await self.conversation_repo.append_message(ConversationMessage(
            id="0",
            conversation_id=conversation_id,
            role="assistant",
            content=response,
            created_at=datetime.utcnow().isoformat()
        ))

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

        logger.info(f"Created task {created_task.id} for conversation {conversation_id}")

        return {
            "conversation_id": conversation_id,
            "mode": "task",
            "task_id": created_task.id,
            "model_id": model_config.id,
            "model_name": model_config.name
        }

    async def stream_chat(
        self,
        conversation_id: Optional[str],
        node_id: str,
        message: str,
        model_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not conversation_id:
            conversation_id = str(await self.conversation_repo.get_next_conversation_id())

        yield {
            "event": "conversation.meta",
            "data": {
                "conversation_id": conversation_id,
                "mode": "chat",
                "node_id": node_id
            }
        }

        await self.conversation_repo.append_message(ConversationMessage(
            id="0",
            conversation_id=conversation_id,
            role="user",
            content=message,
            created_at=datetime.utcnow().isoformat()
        ))

        node = await self.node_repo.get_node(node_id)
        history = await self.conversation_repo.get_conversation_messages(conversation_id)

        model_config = await self._get_model_config(model_id)
        chat_service = ChatService(model_config, self.settings.chat_system_prompt)

        full_response = []
        try:
            async for chunk in chat_service.chat_stream(node, history, message):
                full_response.append(chunk)
                yield {
                    "event": "conversation.delta",
                    "data": {
                        "conversation_id": conversation_id,
                        "delta": chunk
                    }
                }
        except Exception as e:
            yield {
                "event": "conversation.error",
                "data": {
                    "conversation_id": conversation_id,
                    "error": str(e)
                }
            }
            return

        complete_response = "".join(full_response)
        await self.conversation_repo.append_message(ConversationMessage(
            id="0",
            conversation_id=conversation_id,
            role="assistant",
            content=complete_response,
            created_at=datetime.utcnow().isoformat()
        ))

        yield {
            "event": "conversation.done",
            "data": {
                "conversation_id": conversation_id,
                "reply": complete_response,
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
