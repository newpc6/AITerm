import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from passlib.context import CryptContext

from app.config import get_settings
from app.api import api_router
from app.middleware import LoggingMiddleware
from app.db import init_db, async_session_maker
from app.repositories import (
    NodeRepository, UserRepository, ModelConfigRepository
)
from app.models import UserRole, UserStatus
from app.db.settings import AuthSettingsModel
from sqlalchemy import select

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("aiterm")
logger.setLevel(logging.INFO)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def ensure_bootstrap_data():
    node_repo = NodeRepository()
    nodes = await node_repo.list_nodes()
    if not nodes:
        from app.models import Node, NodeStatus
        local_node = Node(
            id="0",
            name="local",
            host="127.0.0.1",
            port=22,
            status=NodeStatus.ONLINE
        )
        await node_repo.create_node(local_node)
        logger.info("Created default local node")

    user_repo = UserRepository()
    admin_count = await user_repo.count_active_admins()
    if admin_count == 0:
        from app.models import User
        now = datetime.utcnow().isoformat()
        password_hash = pwd_context.hash("12345678")
        admin_user = User(
            id="0",
            username="admin",
            display_name="系统管理员",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            last_login_at="",
            created_at=now,
            updated_at=now
        )
        await user_repo.create_user(admin_user, password_hash)
        logger.info(
            "Created default admin user (username: admin, password: 12345678)")

    model_repo = ModelConfigRepository()
    models = await model_repo.list_models()
    if not models:
        from app.models import ModelConfig
        now = datetime.utcnow().isoformat()
        default_model = ModelConfig(
            id="0",
            name="默认模型",
            api_url="https://api.openai.com/v1",
            api_key="",
            model="gpt-4o-mini",
            temperature=0.7,
            extra_params={},
            is_default=True,
            created_at=now,
            updated_at=now
        )
        await model_repo.create_model(default_model)
        logger.info("Created default model config")

    async with async_session_maker() as session:
        result = await session.execute(select(AuthSettingsModel))
        auth_settings = result.scalar_one_or_none()
        if not auth_settings:
            auth_settings = AuthSettingsModel(
                enabled=1,
                allow_password_login=1,
                session_ttl_hours=24
            )
            session.add(auth_settings)
            await session.commit()
            logger.info("Created default auth settings (enabled=True)")
        elif auth_settings.enabled == 0:
            auth_settings.enabled = 1
            await session.commit()
            logger.info("Updated auth settings to enabled=True")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    os.makedirs(settings.data_dir, exist_ok=True)

    await init_db()

    await ensure_bootstrap_data()

    logger.info(f"AITerm server starting on port {settings.port}")
    logger.info(
        f"Database: {settings.database.driver} at {settings.database.sqlite_path}")

    yield

    logger.info("AITerm server shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AITerm API",
        description="AI 驱动的智能终端管理工具",
        version="1.0.0",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(LoggingMiddleware)

    app.include_router(api_router)

    @app.get("/health")
    async def health():
        return {"code": 0, "message": "ok", "data": {"status": "ok"}}

    dist_path = Path(__file__).parent / "dist"
    if dist_path.exists():
        MIME_TYPES = {
            ".js": "application/javascript",
            ".mjs": "application/javascript",
            ".css": "text/css",
            ".html": "text/html",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
        }

        @app.get("/assets/{file_path:path}")
        async def serve_assets(file_path: str):
            full_path = dist_path / "assets" / file_path
            if full_path.exists() and full_path.is_file():
                suffix = full_path.suffix.lower()
                media_type = MIME_TYPES.get(suffix, "application/octet-stream")
                content = full_path.read_bytes()
                return Response(content=content, media_type=media_type)
            return Response(content=b"Not found", status_code=404)

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            file_path = dist_path / full_path
            if file_path.exists() and file_path.is_file():
                suffix = file_path.suffix.lower()
                media_type = MIME_TYPES.get(suffix, "application/octet-stream")
                content = file_path.read_bytes()
                return Response(content=content, media_type=media_type)
            return FileResponse(dist_path / "index.html")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True
    )
