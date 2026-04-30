import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy import select, delete, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import IConversationRepository
from app.models import Conversation, ConversationMessage
from app.db import async_session_maker
from app.db.conversation import ConversationMessageModel
from app.db.task import TaskModel


class ConversationRepository(IConversationRepository):
    async def list_conversations(self, page: int = 1, page_size: int = 20) -> Tuple[List[Conversation], int]:
        async with async_session_maker() as session:
            count_result = await session.execute(
                select(func.count(func.distinct(ConversationMessageModel.conversation_id)))
            )
            total = count_result.scalar() or 0

            offset = (page - 1) * page_size
            result = await session.execute(
                select(
                    ConversationMessageModel.conversation_id,
                    func.count(ConversationMessageModel.id).label('message_count'),
                    func.min(ConversationMessageModel.created_at).label('created_at'),
                    func.max(ConversationMessageModel.created_at).label('updated_at')
                )
                .group_by(ConversationMessageModel.conversation_id)
                .order_by(desc(func.max(ConversationMessageModel.created_at)))
                .offset(offset)
                .limit(page_size)
            )
            rows = result.fetchall()
            
            conversations = []
            for row in rows:
                conv_id = str(row.conversation_id)
                messages = await self.get_conversation_messages(conv_id)
                
                last_message = ""
                title = ""
                if messages:
                    last_msg = messages[-1]
                    last_message = last_msg.content[:100] if len(last_msg.content) > 100 else last_msg.content
                    first_user_msg = next((m for m in messages if m.role == "user"), None)
                    if first_user_msg:
                        title = first_user_msg.content[:50] if len(first_user_msg.content) > 50 else first_user_msg.content
                
                latest_task_id = None
                latest_node_id = None
                latest_status = None
                
                task_result = await session.execute(
                    select(TaskModel)
                    .where(TaskModel.conversation_id == int(conv_id))
                    .order_by(desc(TaskModel.created_at))
                    .limit(1)
                )
                latest_task = task_result.scalar_one_or_none()
                if latest_task:
                    latest_task_id = str(latest_task.id)
                    latest_node_id = str(latest_task.node_id)
                    latest_status = latest_task.status
                
                conversations.append(Conversation(
                    id=conv_id,
                    title=title or f"会话 {conv_id}",
                    last_message=last_message,
                    message_count=row.message_count,
                    latest_task_id=latest_task_id,
                    latest_node_id=latest_node_id,
                    latest_status=latest_status,
                    created_at=row.created_at,
                    updated_at=row.updated_at
                ))
            
            return conversations, total

    async def get_conversation_messages(self, conversation_id: str) -> List[ConversationMessage]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ConversationMessageModel)
                .where(ConversationMessageModel.conversation_id == int(conversation_id))
                .order_by(ConversationMessageModel.created_at)
            )
            models = result.scalars().all()
            return [self._to_domain(m) for m in models]

    async def append_message(self, message: ConversationMessage) -> ConversationMessage:
        async with async_session_maker() as session:
            model = ConversationMessageModel(
                conversation_id=int(message.conversation_id),
                role=message.role,
                content=message.content,
                created_at=message.created_at or datetime.utcnow().isoformat()
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def delete_conversation(self, conversation_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(ConversationMessageModel)
                .where(ConversationMessageModel.conversation_id == int(conversation_id))
            )
            await session.commit()
            return result.rowcount > 0

    async def get_next_conversation_id(self) -> int:
        async with async_session_maker() as session:
            result = await session.execute(
                select(func.max(ConversationMessageModel.conversation_id))
            )
            max_id = result.scalar()
            return (max_id or 0) + 1

    def _to_domain(self, model: ConversationMessageModel) -> ConversationMessage:
        return ConversationMessage(
            id=str(model.id),
            conversation_id=str(model.conversation_id),
            role=model.role,
            content=model.content,
            created_at=model.created_at
        )
