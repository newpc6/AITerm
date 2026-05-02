from fastapi import APIRouter
from .health import router as health_router
from .chats import router as chats_router
from .auth import router as auth_router
from .nodes import router as nodes_router
from .users import router as users_router
from .settings import router as settings_router
from .terminal import router as terminal_router
from .tools import router as tools_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(chats_router)
api_router.include_router(auth_router)
api_router.include_router(nodes_router)
api_router.include_router(users_router)
api_router.include_router(settings_router, prefix="/settings")
api_router.include_router(terminal_router)
api_router.include_router(tools_router)

__all__ = ["api_router"]
