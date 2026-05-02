from typing import Optional
from fastapi import Depends, Header, HTTPException

from app.config import get_settings
from app.repositories import (
    NodeRepository, TaskRepository,
    UserRepository, SessionRepository, ModelConfigRepository,
    GlobalSettingsRepository, AuthSettingsRepository
)
from app.services import (
    NodeService, TaskService,
    AuthService, UserService, ChatOrchestrator,
    ModelConfigService, GlobalSettingsService
)


def get_node_repository() -> NodeRepository:
    return NodeRepository()


def get_task_repository() -> TaskRepository:
    return TaskRepository()


def get_user_repository() -> UserRepository:
    return UserRepository()


def get_session_repository() -> SessionRepository:
    return SessionRepository()


def get_model_config_repository() -> ModelConfigRepository:
    return ModelConfigRepository()


def get_global_settings_repository() -> GlobalSettingsRepository:
    return GlobalSettingsRepository()


def get_auth_settings_repository() -> AuthSettingsRepository:
    return AuthSettingsRepository()


async def get_global_settings(
    repo: GlobalSettingsRepository = Depends(get_global_settings_repository)
):
    return await repo.get_settings()


async def get_node_service(
    repo: NodeRepository = Depends(get_node_repository)
) -> NodeService:
    return NodeService(repo)


async def get_task_service(
    task_repo: TaskRepository = Depends(get_task_repository),
    node_repo: NodeRepository = Depends(get_node_repository),
    model_repo: ModelConfigRepository = Depends(get_model_config_repository),
    settings=Depends(get_global_settings)
) -> TaskService:
    return TaskService(task_repo, node_repo, model_repo, settings)


async def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
    auth_settings_repo: AuthSettingsRepository = Depends(
        get_auth_settings_repository)
) -> AuthService:
    return AuthService(user_repo, session_repo, auth_settings_repo)


async def get_user_service(
    repo: UserRepository = Depends(get_user_repository)
) -> UserService:
    return UserService(repo)


async def get_model_config_service(
    repo: ModelConfigRepository = Depends(get_model_config_repository)
) -> ModelConfigService:
    return ModelConfigService(repo)


async def get_global_settings_service(
    repo: GlobalSettingsRepository = Depends(get_global_settings_repository)
) -> GlobalSettingsService:
    return GlobalSettingsService(repo)


async def get_chat_orchestrator(
    node_repo: NodeRepository = Depends(get_node_repository),
    model_repo: ModelConfigRepository = Depends(get_model_config_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
    task_service: TaskService = Depends(get_task_service),
    settings=Depends(get_global_settings)
) -> ChatOrchestrator:
    return ChatOrchestrator(node_repo, model_repo, task_repo, task_service, settings)


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    auth_service: AuthService = Depends(get_auth_service)
):
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]
    return await auth_service.validate_session(token)


async def get_current_user(
    user=Depends(get_current_user_optional)
):
    settings = get_settings()
    if not settings.database:
        return user

    return user


async def require_admin(
    user=Depends(get_current_user)
):
    if user and user.role == "admin":
        return user
    raise HTTPException(status_code=403, detail="Admin access required")
