from typing import List, Dict, Any, Tuple
from datetime import datetime

from app.models import Conversation, ConversationMessage
from app.repositories import IConversationRepository


class ConversationService:
    def __init__(self, repo: IConversationRepository):
        self.repo = repo
        self._counter = 1

    def _next_id(self) -> str:
        current = self._counter
        self._counter += 1
        return str(current)

    async def list_conversations(self, page: int = 1, page_size: int = 20) -> Tuple[List[Conversation], int]:
        return await self.repo.list_conversations(page, page_size)

    async def get_messages(self, conversation_id: str) -> List[ConversationMessage]:
        return await self.repo.get_conversation_messages(conversation_id)

    async def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str
    ) -> ConversationMessage:
        message = ConversationMessage(
            id=self._next_id(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=datetime.utcnow().isoformat()
        )
        return await self.repo.append_message(message)

    async def delete_conversation(self, conversation_id: str) -> bool:
        return await self.repo.delete_conversation(conversation_id)
