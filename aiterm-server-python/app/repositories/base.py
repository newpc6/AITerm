from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from app.models import (
    Node, NodeCreate, NodeUpdate,
    Task, TaskCreate, TaskUpdate, TaskStep,
    Conversation, ConversationMessage,
    User, UserCreate, UserUpdate,
    Session,
    ModelConfig, ModelConfigCreate, ModelConfigUpdate,
    GlobalSettings, GlobalSettingsUpdate,
    AuthSettings, AuthSettingsUpdate
)


class INodeRepository(ABC):
    @abstractmethod
    async def list_nodes(self) -> List[Node]:
        pass

    @abstractmethod
    async def get_node(self, node_id: str) -> Optional[Node]:
        pass

    @abstractmethod
    async def create_node(self, node: Node) -> Node:
        pass

    @abstractmethod
    async def update_node(self, node_id: str, node: Node) -> Optional[Node]:
        pass

    @abstractmethod
    async def delete_node(self, node_id: str) -> bool:
        pass


class ITaskRepository(ABC):
    @abstractmethod
    async def list_tasks(self) -> List[Task]:
        pass

    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[Task]:
        pass

    @abstractmethod
    async def create_task(self, task: Task) -> Task:
        pass

    @abstractmethod
    async def update_task(self, task_id: str, task: Task) -> Optional[Task]:
        pass

    @abstractmethod
    async def delete_task(self, task_id: str) -> bool:
        pass

    @abstractmethod
    async def get_latest_task_by_conversation(self, conversation_id: str) -> Optional[Task]:
        pass


class IConversationRepository(ABC):
    @abstractmethod
    async def list_conversations(self) -> List[Conversation]:
        pass

    @abstractmethod
    async def get_conversation_messages(self, conversation_id: str) -> List[ConversationMessage]:
        pass

    @abstractmethod
    async def append_message(self, message: ConversationMessage) -> ConversationMessage:
        pass

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> bool:
        pass

    @abstractmethod
    async def get_next_conversation_id(self) -> int:
        pass


class IUserRepository(ABC):
    @abstractmethod
    async def list_users(self) -> List[User]:
        pass

    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[User]:
        pass

    @abstractmethod
    async def get_user_by_username(self, username: str) -> Optional[User]:
        pass

    @abstractmethod
    async def create_user(self, user: User, password_hash: str) -> User:
        pass

    @abstractmethod
    async def update_user(self, user_id: str, user: User) -> Optional[User]:
        pass

    @abstractmethod
    async def delete_user(self, user_id: str) -> bool:
        pass

    @abstractmethod
    async def update_password_hash(self, user_id: str, password_hash: str) -> bool:
        pass

    @abstractmethod
    async def update_last_login(self, user_id: str) -> bool:
        pass

    @abstractmethod
    async def count_active_admins(self) -> int:
        pass


class ISessionRepository(ABC):
    @abstractmethod
    async def get_session(self, token: str) -> Optional[Session]:
        pass

    @abstractmethod
    async def create_session(self, session: Session) -> Session:
        pass

    @abstractmethod
    async def delete_session(self, token: str) -> bool:
        pass

    @abstractmethod
    async def delete_user_sessions(self, user_id: str) -> int:
        pass


class IModelConfigRepository(ABC):
    @abstractmethod
    async def list_models(self) -> List[ModelConfig]:
        pass

    @abstractmethod
    async def get_model(self, model_id: str) -> Optional[ModelConfig]:
        pass

    @abstractmethod
    async def get_default_model(self) -> Optional[ModelConfig]:
        pass

    @abstractmethod
    async def create_model(self, model: ModelConfig) -> ModelConfig:
        pass

    @abstractmethod
    async def update_model(self, model_id: str, model: ModelConfig) -> Optional[ModelConfig]:
        pass

    @abstractmethod
    async def delete_model(self, model_id: str) -> bool:
        pass

    @abstractmethod
    async def set_default_model(self, model_id: str) -> bool:
        pass


class IGlobalSettingsRepository(ABC):
    @abstractmethod
    async def get_settings(self) -> GlobalSettings:
        pass

    @abstractmethod
    async def update_settings(self, settings: GlobalSettings) -> GlobalSettings:
        pass


class IAuthSettingsRepository(ABC):
    @abstractmethod
    async def get_settings(self) -> AuthSettings:
        pass

    @abstractmethod
    async def update_settings(self, settings: AuthSettings) -> AuthSettings:
        pass
